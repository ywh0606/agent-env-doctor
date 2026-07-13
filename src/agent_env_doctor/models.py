"""Portable models for diagnostic findings and reports."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    INFRA_FAILURE = "INFRA_FAILURE"
    VERIFIER_FAILURE = "VERIFIER_FAILURE"
    AGENT_FAILURE = "AGENT_FAILURE"
    INCONCLUSIVE = "INCONCLUSIVE"


class Severity(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


class Finding(BaseModel):
    severity: Severity
    check: str
    message: str
    evidence: list[str] = Field(default_factory=list)
    reproduce: str | None = None


class DiagnosticReport(BaseModel):
    subject: str
    verdict: Verdict
    summary: str
    findings: list[Finding] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    reproduce: str | None = None
    source_directory: str | None = None
    artifacts_directory: str | None = None

    @classmethod
    def from_path(
        cls,
        path: Path,
        verdict: Verdict,
        summary: str,
        findings: list[Finding],
        artifacts_directory: Path | None = None,
    ) -> "DiagnosticReport":
        evidence = sorted({item for finding in findings for item in finding.evidence})
        reproduce = next(
            (
                finding.reproduce
                for finding in findings
                if finding.severity == Severity.FAIL and finding.reproduce
            ),
            next((finding.reproduce for finding in findings if finding.reproduce), None),
        )
        return cls(
            subject=path.name,
            verdict=verdict,
            summary=summary,
            findings=findings,
            evidence=evidence,
            reproduce=reproduce,
            source_directory=str(path),
            artifacts_directory=str(artifacts_directory) if artifacts_directory else None,
        )
