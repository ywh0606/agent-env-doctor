from __future__ import annotations

import pytest

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


def test_junit_nested_suite_uses_aggregate_counters_once(tmp_path):
    (tmp_path / "results.xml").write_text(
        '<testsuites tests="3" failures="1" errors="0">'
        '<testsuite tests="3" failures="1" errors="0">'
        '<testsuite tests="3" failures="1" errors="0" />'
        '</testsuite></testsuites>',
        encoding="utf-8",
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.AGENT_FAILURE
    assert any(
        "Parsed 3 tests with 1 failures or errors." in finding.message
        for finding in report.findings
    )


def test_junit_without_executed_tests_is_a_verifier_failure(tmp_path):
    (tmp_path / "results.xml").write_text(
        '<testsuite errors="1" failures="0" />', encoding="utf-8"
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE


@pytest.mark.parametrize(
    "xml",
    [
        '<testsuite tests="3" skipped="3" failures="0" errors="0" />',
        '<testsuites tests="3" skipped="3" failures="0" errors="0">'
        '<testsuite tests="3" skipped="3" failures="0" errors="0" />'
        '</testsuites>',
        '<testsuites><testsuite tests="1" skipped="1" />'
        '<testsuite tests="2" skipped="2" /></testsuites>',
    ],
)
def test_all_skipped_junit_is_a_verifier_failure(tmp_path, xml):
    (tmp_path / "results.xml").write_text(xml, encoding="utf-8")

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE
    assert any("no executed tests" in finding.message for finding in report.findings)


@pytest.mark.parametrize(
    "xml",
    [
        '<testsuite tests="3" skipped="2" />',
        '<testsuites tests="3" skipped="2"><testsuite tests="3" skipped="2" /></testsuites>',
        '<testsuites><testsuite tests="2" skipped="2" />'
        '<testsuite tests="1" /></testsuites>',
    ],
)
def test_junit_counts_only_executed_tests(tmp_path, xml):
    (tmp_path / "results.xml").write_text(xml, encoding="utf-8")

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.READY
    assert any(
        "Parsed 1 tests with 0 failures or errors." in finding.message
        for finding in report.findings
    )


@pytest.mark.parametrize(
    "counters",
    [
        'tests="-1"',
        'tests="3" failures="-1" errors="1"',
        'tests="3" errors="-1" failures="1"',
        'tests="3" skipped="-1"',
        'tests="3" skipped="unknown"',
        'tests="3" skipped="4"',
        'tests="1" failures="2"',
        'tests="1" errors="2"',
        'tests="3" skipped="2" failures="1" errors="1"',
    ],
)
def test_invalid_junit_counters_are_a_verifier_failure(tmp_path, counters):
    (tmp_path / "results.xml").write_text(f"<testsuite {counters} />", encoding="utf-8")

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE
    assert any("Invalid JUnit counters" in finding.message for finding in report.findings)


def test_negative_junit_counters_cannot_cancel_between_suites(tmp_path):
    (tmp_path / "results.xml").write_text(
        '<testsuites><testsuite tests="1" failures="1" />'
        '<testsuite tests="1" failures="-1" /></testsuites>',
        encoding="utf-8",
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE


def test_all_skipped_junit_takes_priority_over_other_passing_evidence(tmp_path):
    (tmp_path / "passed.xml").write_text('<testsuite tests="1" />', encoding="utf-8")
    (tmp_path / "skipped.xml").write_text(
        '<testsuite tests="1" skipped="1" />', encoding="utf-8"
    )
    (tmp_path / "results.json").write_text('{"status":"failed"}', encoding="utf-8")

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.VERIFIER_FAILURE


def test_skipped_tests_do_not_hide_executed_failures(tmp_path):
    (tmp_path / "results.xml").write_text(
        '<testsuite tests="3" skipped="2" failures="1" />', encoding="utf-8"
    )

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.AGENT_FAILURE
    assert any(
        "Parsed 1 tests with 1 failures or errors." in finding.message
        for finding in report.findings
    )


def test_large_log_is_bounded_and_reported(tmp_path):
    (tmp_path / "run.log").write_bytes(b"x" * (MAX_LOG_BYTES + 1))

    report = analyze_run(str(tmp_path))

    assert report.verdict is Verdict.INCONCLUSIVE
    assert any(finding.check == "log scan limit" for finding in report.findings)
