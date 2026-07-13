"""Render reports without requiring a hosted service."""

from __future__ import annotations

from .models import DiagnosticReport


def markdown(report: DiagnosticReport) -> str:
    lines = [
        "# agent-env-doctor report",
        "",
        f"**Subject:** `{report.subject}`  ",
        f"**Verdict:** `{report.verdict.value}`",
        "",
        report.summary,
        "",
        "## Findings",
        "",
        "| Status | Check | Detail |",
        "| --- | --- | --- |",
    ]
    for finding in report.findings:
        detail = finding.message.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {finding.severity.value} | {finding.check} | {detail} |")

    if report.evidence:
        lines.extend(["", "## Evidence", ""])
        lines.extend(f"- `{path}`" for path in report.evidence)
    if report.artifacts_directory:
        lines.extend(["", "## Artifacts", "", f"- `{report.artifacts_directory}`"])
    if report.reproduce:
        lines.extend(["", "## Reproduce", "", "```bash", report.reproduce, "```"])
    return "\n".join(lines) + "\n"
