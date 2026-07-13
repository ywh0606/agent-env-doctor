"""Local checks for a Terminal-Bench task before an agent is executed."""

from __future__ import annotations

import shutil
import subprocess
from os import PathLike
from pathlib import Path

import yaml

from .models import DiagnosticReport, Finding, Severity, Verdict


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


def check_task(task: str) -> DiagnosticReport:
    """Inspect an official Terminal-Bench task directory without running an agent."""
    task_dir = resolve_task(task)
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
                reproduce=f"docker build -f {dockerfile} {task_dir}",
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

    docker_ok, docker_message = _docker_available()
    findings.append(
        Finding(
            severity=Severity.PASS if docker_ok else Severity.FAIL,
            check="Docker daemon",
            message=docker_message,
            reproduce=None if docker_ok else "docker info",
        )
    )

    failures = [finding for finding in findings if finding.severity == Severity.FAIL]
    if failures:
        return DiagnosticReport.from_path(
            task_dir,
            Verdict.BLOCKED,
            "The task cannot be evaluated locally until the failed preflight checks are resolved.",
            findings,
        )
    return DiagnosticReport.from_path(
        task_dir,
        Verdict.READY,
        "The task passes the currently implemented local structural and Docker availability checks.",
        findings,
    )
