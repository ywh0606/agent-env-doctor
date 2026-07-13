from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import socket

import pytest

from agent_env_doctor.docker_runner import CommandResult
from agent_env_doctor.models import Verdict
from agent_env_doctor.preflight import check_task


@dataclass
class FakeDockerRunner:
    build_result: CommandResult = field(default_factory=lambda: CommandResult(0, "build output"))
    smoke_results: list[CommandResult] = field(default_factory=list)
    cleanup_result: CommandResult = field(default_factory=lambda: CommandResult(0, "cleanup output"))
    calls: list[tuple[str, str | None]] = field(default_factory=list)

    def build(self, task_dir: Path, image_tag: str) -> CommandResult:
        self.calls.append(("build", image_tag))
        return self.build_result

    def smoke(self, image_tag: str, command: str | None = None) -> CommandResult:
        self.calls.append(("smoke", command))
        return self.smoke_results.pop(0) if self.smoke_results else CommandResult(0, "smoke output")

    def remove_image(self, image_tag: str) -> CommandResult:
        self.calls.append(("remove_image", image_tag))
        return self.cleanup_result


def _task_directory(tmp_path: Path) -> Path:
    tmp_path.mkdir(parents=True)
    (tmp_path / "task.yaml").write_text("instruction: hello", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    return tmp_path


def _docker_is_available(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent_env_doctor.preflight._docker_available",
        lambda: (True, "Docker daemon is available (server test)."),
    )


def test_build_smoke_and_required_command_are_reported(tmp_path, monkeypatch):
    _docker_is_available(monkeypatch)
    runner = FakeDockerRunner()
    artifacts = tmp_path / "artifacts"

    report = check_task(
        str(_task_directory(tmp_path / "task")),
        build=True,
        artifacts_dir=artifacts,
        required_commands=("python3",),
        docker_runner=runner,
    )

    assert report.verdict is Verdict.READY
    assert report.artifacts_directory == str(artifacts.resolve())
    assert (artifacts / "docker-build.log").read_text(encoding="utf-8") == "build output\n"
    assert (artifacts / "docker-smoke.log").read_text(encoding="utf-8") == "smoke output\n"
    assert (artifacts / "required-command-1.log").is_file()
    assert [name for name, _ in runner.calls] == ["build", "smoke", "smoke", "remove_image"]


def test_failed_build_blocks_and_does_not_start_a_container(tmp_path, monkeypatch):
    _docker_is_available(monkeypatch)
    runner = FakeDockerRunner(build_result=CommandResult(1, "package not found"))

    report = check_task(str(_task_directory(tmp_path / "task")), build=True, docker_runner=runner)

    assert report.verdict is Verdict.BLOCKED
    assert [name for name, _ in runner.calls] == ["build"]
    assert any(finding.check == "Docker image build" for finding in report.findings)


def test_missing_required_command_blocks_and_cleans_up(tmp_path, monkeypatch):
    _docker_is_available(monkeypatch)
    runner = FakeDockerRunner(
        smoke_results=[CommandResult(0, ""), CommandResult(1, "command not found")]
    )

    report = check_task(
        str(_task_directory(tmp_path / "task")),
        build=True,
        required_commands=("not-installed",),
        docker_runner=runner,
    )

    assert report.verdict is Verdict.BLOCKED
    assert [name for name, _ in runner.calls] == ["build", "smoke", "smoke", "remove_image"]
    assert any("not available" in finding.message for finding in report.findings)


def test_keep_image_skips_cleanup(tmp_path, monkeypatch):
    _docker_is_available(monkeypatch)
    runner = FakeDockerRunner()

    report = check_task(
        str(_task_directory(tmp_path / "task")),
        build=True,
        keep_image=True,
        docker_runner=runner,
    )

    assert report.verdict is Verdict.READY
    assert "remove_image" not in [name for name, _ in runner.calls]


def test_required_port_reports_conflict(tmp_path, monkeypatch):
    _docker_is_available(monkeypatch)
    socket_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    socket_listener.bind(("127.0.0.1", 0))
    port = socket_listener.getsockname()[1]
    try:
        report = check_task(str(_task_directory(tmp_path / "task")), required_ports=(port,))
    finally:
        socket_listener.close()

    assert report.verdict is Verdict.BLOCKED
    assert any(finding.check == "required host port" for finding in report.findings)


def test_required_port_reports_available_port(tmp_path, monkeypatch):
    _docker_is_available(monkeypatch)
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    report = check_task(str(_task_directory(tmp_path / "task")), required_ports=(port,))

    port_finding = next(finding for finding in report.findings if finding.check == "required host port")
    assert port_finding.severity.value == "PASS"
    assert "available" in port_finding.message


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"required_commands": ("pytest",)}, "--require-command requires --build"),
        ({"artifacts_dir": Path("artifacts")}, "--artifacts-dir requires --build"),
        ({"keep_image": True}, "--keep-image requires --build"),
        (
            {"build": True, "required_commands": ("pytest -q",)},
            "--require-command accepts one executable name or path at a time",
        ),
        (
            {"build": True, "required_commands": ("-pytest",)},
            "--require-command accepts one executable name or path at a time",
        ),
    ],
)
def test_docker_execution_options_have_clear_contract(tmp_path, kwargs, message):
    with pytest.raises(ValueError, match=message):
        check_task(str(_task_directory(tmp_path / "task")), **kwargs)
