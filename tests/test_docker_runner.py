from __future__ import annotations

import subprocess

from agent_env_doctor.docker_runner import DockerRunner, image_tag_for


def test_image_tag_is_docker_safe_and_unique(tmp_path):
    task = tmp_path / "A task with spaces!"
    task.mkdir()

    first = image_tag_for(task)
    second = image_tag_for(task)

    assert first.startswith("agent-env-doctor/a-task-with-spaces:")
    assert first != second


def test_runner_returns_unavailable_docker_as_command_result(monkeypatch):
    def raise_os_error(*args, **kwargs):
        raise OSError("docker not found")

    monkeypatch.setattr("agent_env_doctor.docker_runner.subprocess.run", raise_os_error)

    result = DockerRunner().run(["info"])

    assert result.returncode == 127
    assert "docker not found" in result.output


def test_smoke_disables_network_and_uses_shell(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(arguments, **kwargs):
        calls.append(arguments)
        return subprocess.CompletedProcess(arguments, 0, stdout="ok", stderr="")

    monkeypatch.setattr("agent_env_doctor.docker_runner.subprocess.run", fake_run)

    result = DockerRunner().smoke("agent-env-doctor/task:123", "command -v pytest")

    assert result.returncode == 0
    assert calls == [
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "/bin/sh",
            "agent-env-doctor/task:123",
            "-lc",
            "command -v pytest",
        ]
    ]


def test_runner_converts_timeout_to_diagnostic_result(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("docker", 5, output=b"partial output", stderr=b"timed out")

    monkeypatch.setattr("agent_env_doctor.docker_runner.subprocess.run", raise_timeout)

    result = DockerRunner(timeout_seconds=5).run(["build", "."])

    assert result.returncode == 124
    assert result.timed_out is True
    assert "partial output" in result.output
    assert "timed out" in result.output
