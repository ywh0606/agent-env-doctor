from __future__ import annotations

from agent_env_doctor.analysis import MAX_LOG_BYTES, analyze_run
from agent_env_doctor.models import Verdict


def test_detects_infrastructure_failure_from_log(tmp_path):
    (tmp_path / "docker.log").write_text("fatal: no space left on device", encoding="utf-8")

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.INFRA_FAILURE
    assert "no space left on device" in report.findings[0].message


def test_detects_verifier_failure_from_invalid_junit(tmp_path):
    (tmp_path / "results.xml").write_text("<testsuite", encoding="utf-8")

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE


def test_detects_verifier_failure_from_invalid_junit_counter(tmp_path):
    (tmp_path / "results.xml").write_text(
        '<testsuite tests="unknown" failures="0" errors="0" />', encoding="utf-8"
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE


def test_detects_agent_failure_from_json_records_after_first_record(tmp_path):
    (tmp_path / "results.json").write_text(
        '[{"status":"passed"},{"status":"failed"}]', encoding="utf-8"
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.AGENT_FAILURE
    assert any("JSON reports `failed`" in finding.message for finding in report.findings)


def test_detects_agent_failure_from_junit(tmp_path):
    (tmp_path / "results.xml").write_text(
        '<testsuite tests="2" failures="1" errors="0" />', encoding="utf-8"
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.AGENT_FAILURE


def test_detects_ready_from_passing_junit(tmp_path):
    (tmp_path / "results.xml").write_text(
        '<testsuite tests="2" failures="0" errors="0" />', encoding="utf-8"
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.READY


def test_uses_inconclusive_when_evidence_is_missing(tmp_path):
    (tmp_path / "agent.log").write_text("agent failed to find a solution", encoding="utf-8")

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.INCONCLUSIVE


def test_verifier_failure_is_not_hidden_by_another_failed_junit_file(tmp_path):
    (tmp_path / "failed.xml").write_text(
        '<testsuite tests="1" failures="1" errors="0" />', encoding="utf-8"
    )
    (tmp_path / "broken.xml").write_text("<testsuite", encoding="utf-8")

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE
    assert len(report.findings) == 2


def test_docker_documentation_text_does_not_override_passing_junit(tmp_path):
    (tmp_path / "agent.log").write_text(
        "The agent inspected Docker daemon documentation.", encoding="utf-8"
    )
    (tmp_path / "results.xml").write_text(
        '<testsuite tests="1" failures="0" errors="0" />', encoding="utf-8"
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.READY


def test_junit_without_executed_tests_is_a_verifier_failure(tmp_path):
    (tmp_path / "results.xml").write_text(
        '<testsuite errors="1" failures="0" />', encoding="utf-8"
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE


def test_large_log_is_bounded_and_reported(tmp_path):
    (tmp_path / "run.log").write_bytes(b"x" * (MAX_LOG_BYTES + 1))

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.INCONCLUSIVE
    assert any(finding.check == "log scan limit" for finding in report.findings)
