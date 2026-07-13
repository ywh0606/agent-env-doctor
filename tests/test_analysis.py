from __future__ import annotations

from agent_env_doctor.analysis import analyze_run
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
