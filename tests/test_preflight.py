from __future__ import annotations

from agent_env_doctor.models import Verdict
from agent_env_doctor.preflight import check_task, resolve_task


def test_missing_task_metadata_blocks_even_without_docker(tmp_path):
    (tmp_path / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")

    report = check_task(str(tmp_path))

    assert report.verdict is Verdict.BLOCKED
    assert any(item.check == "Terminal-Bench task format" for item in report.findings)


def test_invalid_task_metadata_blocks(tmp_path):
    (tmp_path / "task.yaml").write_text("instruction: [unterminated", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")

    report = check_task(str(tmp_path))

    assert report.verdict is Verdict.BLOCKED
    assert any(item.check == "task metadata" for item in report.findings)


def test_resolve_task_accepts_task_id_from_checkout(tmp_path, monkeypatch):
    task = tmp_path / "tasks" / "hello-world"
    task.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert resolve_task("hello-world") == task


def test_docker_failure_prefers_docker_info_as_reproduction(tmp_path):
    (tmp_path / "task.yaml").write_text("instruction: hello", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM alpine:3.20\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()

    report = check_task(str(tmp_path))

    assert report.verdict is Verdict.BLOCKED
    assert report.reproduce == "docker info"
