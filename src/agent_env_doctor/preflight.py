"""Local checks for a Terminal-Bench task before an agent is executed."""

from __future__ import annotations

import os
import shutil
import shlex
import socket
import subprocess
from os import PathLike
from pathlib import Path

import yaml

from .docker_runner import DockerRunner, image_tag_for
from .models import DiagnosticReport, Finding, Severity, Verdict

LOW_DISK_BYTES = 10 * 1024**3


def resolve_task(task: str | PathLike[str]) -> Path:
    """Resolve either a local task directory or a task id inside a checkout."""
    candidate = Path(task).expanduser()
    if candidate.is_dir():
        return candidate.resolve()

    task_id = str(task)
    search_roots = [
        Path.cwd() / "tasks",
        Path.cwd() / "original-tasks",
        Path.cwd() / "dataset",
    ]
    for root in search_roots:
        task_dir = root / task_id
        if task_dir.is_dir():
            return task_dir.resolve()
    raise FileNotFoundError(
        f"Task directory or task id not found: {task_id}. Pass a local task directory, or run "
        "from a Terminal-Bench checkout containing tasks/<task-id>."
    )


def _docker_available() -> tuple[bool, str]:
    if not shutil.which("docker"):
        return False, "Docker CLI was not found on PATH."
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, f"Docker daemon could not be queried: {error}."
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        return False, detail[-1] if detail else "Docker daemon is unavailable."
    return True, f"Docker daemon is available (server {result.stdout.strip()})."


def _load_task_metadata(task_dir: Path) -> tuple[dict[str, object] | None, str | None]:
    metadata_path = task_dir / "task.yaml"
    if not metadata_path.is_file():
        return None, None
    try:
        content = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        return None, str(error)
    return content if isinstance(content, dict) else {}, None


def _write_artifact(directory: Path | None, name: str, content: str) -> str | None:
    if directory is None:
        return None
    directory.mkdir(parents=True, exist_ok=True)
    artifact = directory / name
    artifact.write_text(content + ("" if content.endswith("\n") else "\n"), encoding="utf-8")
    return str(artifact)


def _host_resource_findings(task_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        free_disk = shutil.disk_usage(task_dir).free
    except OSError as error:
        findings.append(
            Finding(
                severity=Severity.WARN,
                check="host disk space",
                message=f"Could not determine free disk space: {error}",
            )
        )
    else:
        free_gib = free_disk / 1024**3
        severity = Severity.WARN if free_disk < LOW_DISK_BYTES else Severity.PASS
        message = f"{free_gib:.1f} GiB free on the task filesystem."
        if severity == Severity.WARN:
            message += " Less than the 10 GiB preflight threshold."
        findings.append(Finding(severity=severity, check="host disk space", message=message))

    cpu_count = os.cpu_count()
    if cpu_count is None:
        findings.append(
            Finding(
                severity=Severity.WARN,
                check="host CPU",
                message="Could not determine the available CPU count.",
            )
        )
    else:
        findings.append(
            Finding(
                severity=Severity.PASS,
                check="host CPU",
                message=f"Detected {cpu_count} logical CPUs.",
            )
        )
    return findings


def _port_findings(required_ports: tuple[int, ...]) -> list[Finding]:
    findings: list[Finding] = []
    for port in required_ports:
        if not 1 <= port <= 65535:
            findings.append(
                Finding(
                    severity=Severity.FAIL,
                    check="required host port",
                    message=f"Port {port} is outside the valid range 1-65535.",
                )
            )
            continue
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as error:
            findings.append(
                Finding(
                    severity=Severity.FAIL,
                    check="required host port",
                    message=f"Port {port} cannot be bound on 127.0.0.1: {error}.",
                    reproduce=f"lsof -nP -iTCP:{port} -sTCP:LISTEN",
                )
            )
        else:
            findings.append(
                Finding(
                    severity=Severity.PASS,
                    check="required host port",
                    message=f"Port {port} is available on 127.0.0.1.",
                )
            )
        finally:
            probe.close()
    return findings


def _execute_build_checks(
    task_dir: Path,
    findings: list[Finding],
    artifacts_dir: Path | None,
    timeout_seconds: int,
    keep_image: bool,
    required_commands: tuple[str, ...],
    runner: DockerRunner,
) -> None:
    image_tag = image_tag_for(task_dir)
    built = False
    try:
        build_result = runner.build(task_dir, image_tag)
        build_evidence = _write_artifact(artifacts_dir, "docker-build.log", build_result.output)
        build_message = "Docker image built successfully."
        if build_result.timed_out:
            build_message = f"Docker image build timed out after {timeout_seconds} seconds."
        elif build_result.returncode:
            build_message = f"Docker image build failed with exit code {build_result.returncode}."
        findings.append(
            Finding(
                severity=Severity.PASS if build_result.returncode == 0 else Severity.FAIL,
                check="Docker image build",
                message=build_message,
                evidence=[build_evidence] if build_evidence else [],
                reproduce=(
                    f"docker build -f {shlex.quote(str(task_dir / 'Dockerfile'))} "
                    f"{shlex.quote(str(task_dir))}"
                ),
            )
        )
        if build_result.returncode:
            return
        built = True

        smoke_result = runner.smoke(image_tag)
        smoke_evidence = _write_artifact(artifacts_dir, "docker-smoke.log", smoke_result.output)
        smoke_message = "Container shell smoke test completed successfully."
        if smoke_result.timed_out:
            smoke_message = f"Container shell smoke test timed out after {timeout_seconds} seconds."
        elif smoke_result.returncode:
            smoke_message = f"Container shell smoke test failed with exit code {smoke_result.returncode}."
        findings.append(
            Finding(
                severity=Severity.PASS if smoke_result.returncode == 0 else Severity.FAIL,
                check="container shell smoke test",
                message=smoke_message,
                evidence=[smoke_evidence] if smoke_evidence else [],
                reproduce=(
                    f"docker run --rm --network none --entrypoint /bin/sh {image_tag} -lc true"
                ),
            )
        )
        if smoke_result.returncode:
            return

        for index, command in enumerate(required_commands, start=1):
            escaped_command = shlex.quote(command)
            command_result = runner.smoke(image_tag, f"command -v {escaped_command}")
            command_evidence = _write_artifact(
                artifacts_dir, f"required-command-{index}.log", command_result.output
            )
            command_message = f"Required command `{command}` is available in the task image."
            if command_result.timed_out:
                command_message = f"Required command check for `{command}` timed out after {timeout_seconds} seconds."
            elif command_result.returncode:
                command_message = f"Required command `{command}` is not available in the task image."
            findings.append(
                Finding(
                    severity=Severity.PASS if command_result.returncode == 0 else Severity.FAIL,
                    check="required command",
                    message=command_message,
                    evidence=[command_evidence] if command_evidence else [],
                    reproduce=(
                        f"docker run --rm --network none --entrypoint /bin/sh {image_tag} -lc "
                        f"{shlex.quote(f'command -v {escaped_command}')}"
                    ),
                )
            )
    finally:
        if built and not keep_image:
            cleanup_result = runner.remove_image(image_tag)
            cleanup_evidence = _write_artifact(
                artifacts_dir, "docker-cleanup.log", cleanup_result.output
            )
            findings.append(
                Finding(
                    severity=Severity.PASS if cleanup_result.returncode == 0 else Severity.WARN,
                    check="temporary image cleanup",
                    message=(
                        "Removed temporary task image."
                        if cleanup_result.returncode == 0
                        else "Could not remove the temporary task image."
                    ),
                    evidence=[cleanup_evidence] if cleanup_evidence else [],
                )
            )


def check_task(
    task: str,
    *,
    build: bool = False,
    build_timeout: int = 300,
    artifacts_dir: Path | None = None,
    keep_image: bool = False,
    required_commands: tuple[str, ...] = (),
    required_ports: tuple[int, ...] = (),
    docker_runner: DockerRunner | None = None,
) -> DiagnosticReport:
    """Inspect a Terminal-Bench task, optionally building and smoke-testing its image."""
    if build_timeout <= 0:
        raise ValueError("build_timeout must be greater than zero")
    if not build and required_commands:
        raise ValueError("--require-command requires --build")
    if not build and artifacts_dir:
        raise ValueError("--artifacts-dir requires --build")
    if not build and keep_image:
        raise ValueError("--keep-image requires --build")
    invalid_commands = [
        command
        for command in required_commands
        if not command or command.startswith("-") or any(char.isspace() for char in command)
    ]
    if invalid_commands:
        raise ValueError("--require-command accepts one executable name or path at a time")
    task_dir = resolve_task(task)
    artifacts_path = artifacts_dir.expanduser().resolve() if artifacts_dir else None
    findings: list[Finding] = []
    metadata, yaml_error = _load_task_metadata(task_dir)

    if yaml_error:
        findings.append(
            Finding(
                severity=Severity.FAIL,
                check="task metadata",
                message=f"task.yaml is not valid YAML: {yaml_error}",
                evidence=[str(task_dir / "task.yaml")],
            )
        )
    elif metadata is None:
        findings.append(
            Finding(
                severity=Severity.FAIL,
                check="Terminal-Bench task format",
                message="Missing task.yaml; this is not an official Terminal-Bench task directory.",
            )
        )
    else:
        findings.append(
            Finding(
                severity=Severity.PASS,
                check="Terminal-Bench task format",
                message="Found readable task.yaml.",
                evidence=[str(task_dir / "task.yaml")],
            )
        )
        if not isinstance(metadata.get("instruction"), str) or not metadata["instruction"].strip():
            findings.append(
                Finding(
                    severity=Severity.FAIL,
                    check="task instruction",
                    message="task.yaml does not contain a non-empty instruction.",
                    evidence=[str(task_dir / "task.yaml")],
                )
            )
        else:
            findings.append(
                Finding(
                    severity=Severity.PASS,
                    check="task instruction",
                    message="Found a non-empty task instruction.",
                    evidence=[str(task_dir / "task.yaml")],
                )
            )

    dockerfile = task_dir / "Dockerfile"
    if dockerfile.is_file():
        findings.append(
            Finding(
                severity=Severity.PASS,
                check="Docker build context",
                message="Found Dockerfile.",
                evidence=[str(dockerfile)],
                reproduce=(
                    f"docker build -f {shlex.quote(str(dockerfile))} {shlex.quote(str(task_dir))}"
                ),
            )
        )
    else:
        findings.append(
            Finding(
                severity=Severity.FAIL,
                check="Docker build context",
                message="Missing Dockerfile required for a local task image build.",
            )
        )

    tests_dir = task_dir / "tests"
    if tests_dir.is_dir():
        findings.append(
            Finding(
                severity=Severity.PASS,
                check="verifier assets",
                message="Found tests directory; verifier execution is not run by this pre-alpha release.",
                evidence=[str(tests_dir)],
            )
        )
    else:
        findings.append(
            Finding(
                severity=Severity.WARN,
                check="verifier assets",
                message="No tests directory was found; verifier health cannot be checked.",
            )
        )

    findings.extend(_host_resource_findings(task_dir))
    findings.extend(_port_findings(tuple(required_ports)))
    docker_ok, docker_message = _docker_available()
    findings.append(
        Finding(
            severity=Severity.PASS if docker_ok else Severity.FAIL,
            check="Docker daemon",
            message=docker_message,
            reproduce=None if docker_ok else "docker info",
        )
    )

    if build and docker_ok and dockerfile.is_file():
        _execute_build_checks(
            task_dir,
            findings,
            artifacts_path,
            build_timeout,
            keep_image,
            tuple(required_commands),
            docker_runner or DockerRunner(build_timeout),
        )
    elif build and docker_ok:
        findings.append(
            Finding(
                severity=Severity.SKIP,
                check="Docker execution checks",
                message="Skipped because the task has no Dockerfile.",
            )
        )

    failures = [finding for finding in findings if finding.severity == Severity.FAIL]
    if failures:
        return DiagnosticReport.from_path(
            task_dir,
            Verdict.BLOCKED,
            "The task cannot be evaluated locally until the failed preflight checks are resolved.",
            findings,
            artifacts_path,
        )
    return DiagnosticReport.from_path(
        task_dir,
        Verdict.READY,
            "The task passes the currently implemented local structural and Docker availability checks.",
            findings,
            artifacts_path,
        )
