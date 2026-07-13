from __future__ import annotations

from agent_env_doctor.models import DiagnosticReport, Finding, Severity, Verdict
from agent_env_doctor.render import markdown


def test_markdown_includes_verdict_evidence_and_reproduction():
    report = DiagnosticReport(
        subject="example",
        verdict=Verdict.BLOCKED,
        summary="Docker is unavailable.",
        findings=[
            Finding(
                severity=Severity.FAIL,
                check="Docker daemon",
                message="not found",
                evidence=["docker.log"],
                reproduce="docker info",
            )
        ],
        evidence=["docker.log"],
        reproduce="docker info",
    )

    rendered = markdown(report)

    assert "`BLOCKED`" in rendered
    assert "`docker.log`" in rendered
    assert "docker info" in rendered
