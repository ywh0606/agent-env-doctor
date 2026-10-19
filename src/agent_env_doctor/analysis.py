"""Conservative attribution for local terminal-agent run artifacts."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as element_tree
from pathlib import Path

from .models import DiagnosticReport, Finding, Severity, Verdict

MAX_LOG_BYTES = 1_000_000
TEXT_SUFFIXES = {".log", ".txt", ".out", ".err"}
INFRA_PATTERNS = (
    "no space left on device",
    "cannot connect to the docker daemon",
    "port is already allocated",
    "address already in use",
    "permission denied while trying to connect to the docker daemon",
    "mount failed",
    "out of memory",
    "oomkilled",
)
VERIFIER_PATTERNS = (
    "verifier failed",
    "verifier error",
    "pytest internal error",
    "junit parse error",
    "collection errors",
    "no tests ran",
)
AGENT_PATTERNS = (
    "agent failed",
    "agent_failure",
    "task failed",
    "tests failed",
    "assertionerror",
)
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[=:]\s*[^\s]+"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
)


def _redact(value: str) -> str:
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _read_text_files(run_dir: Path) -> list[tuple[Path, str, bool]]:
    """Read a bounded prefix of each candidate log to keep analysis local and predictable."""
    files: list[tuple[Path, str, bool]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            with path.open("rb") as file:
                raw = file.read(MAX_LOG_BYTES + 1)
        except OSError:
            continue
        truncated = len(raw) > MAX_LOG_BYTES
        files.append(
            (
                path,
                _redact(raw[:MAX_LOG_BYTES].decode("utf-8", errors="replace")),
                truncated,
            )
        )
    return files


def _junit_result(path: Path) -> tuple[int, int, str | None]:
    try:
        root = element_tree.parse(path).getroot()
    except (OSError, element_tree.ParseError) as error:
        return 0, 0, f"Invalid JUnit XML: {error}"
    suites = [root] if root.tag == "testsuite" else list(root.findall(".//testsuite"))
    if not suites:
        return 0, 0, "JUnit XML contains no testsuite elements."
    try:
        tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
        failures = sum(
            int(suite.attrib.get("failures", "0")) + int(suite.attrib.get("errors", "0"))
            for suite in suites
        )
    except ValueError as error:
        return 0, 0, f"Invalid JUnit counters: {error}"
    if tests <= 0:
        return 0, 0, "JUnit XML reports no executed tests."
    return tests, failures, None


def _json_statuses(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    records = payload if isinstance(payload, list) else [payload]
    statuses: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in ("verdict", "status", "result", "outcome"):
            value = record.get(key)
            if isinstance(value, str):
                status = value.lower()
                if status not in statuses:
                    statuses.append(status)
    return statuses


def _contains_any(text: str, patterns: tuple[str, ...]) -> str | None:
    lower = text.lower()
    return next((pattern for pattern in patterns if pattern in lower), None)


def _report_for_verdict(
    run_dir: Path, verdict: Verdict, findings: list[Finding]
) -> DiagnosticReport:
    summaries = {
        Verdict.INFRA_FAILURE: "The run contains infrastructure-failure evidence and should not be scored as an agent failure.",
        Verdict.VERIFIER_FAILURE: "The run contains invalid or failed verifier evidence and cannot be attributed to the agent.",
        Verdict.AGENT_FAILURE: "Verifier or run-result evidence reports an agent failure without higher-priority environment evidence.",
        Verdict.READY: "The available verifier evidence passed and no failure evidence was detected.",
        Verdict.INCONCLUSIVE: "Available artifacts do not provide enough evidence to attribute this run reliably.",
    }
    return DiagnosticReport.from_path(run_dir, verdict, summaries[verdict], findings)


def analyze_run(run_directory: str) -> DiagnosticReport:
    """Classify evidence without assuming a specific agent harness.

    Evidence is collected before classification. The stable precedence is
    INFRA_FAILURE, VERIFIER_FAILURE, AGENT_FAILURE, READY, then INCONCLUSIVE.
    """
    run_dir = Path(run_directory).expanduser().resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    findings: list[Finding] = []
    evidence_verdicts: set[Verdict] = set()
    text_files = _read_text_files(run_dir)
    for path, content, truncated in text_files:
        if truncated:
            findings.append(
                Finding(
                    severity=Severity.WARN,
                    check="log scan limit",
                    message=f"Only the first {MAX_LOG_BYTES} bytes of this log were scanned.",
                    evidence=[str(path)],
                )
            )
        for verdict, patterns, label in (
            (Verdict.INFRA_FAILURE, INFRA_PATTERNS, "infrastructure failure"),
            (Verdict.VERIFIER_FAILURE, VERIFIER_PATTERNS, "verifier failure"),
        ):
            match = _contains_any(content, patterns)
            if match:
                evidence_verdicts.add(verdict)
                findings.append(
                    Finding(
                        severity=Severity.FAIL,
                        check=label,
                        message=f"Observed `{match}` in log output.",
                        evidence=[str(path)],
                    )
                )

    junit_passed = False
    for path in sorted(run_dir.rglob("*.xml")):
        tests, failures, error = _junit_result(path)
        if error:
            evidence_verdicts.add(Verdict.VERIFIER_FAILURE)
            findings.append(
                Finding(
                    severity=Severity.FAIL,
                    check="JUnit results",
                    message=error,
                    evidence=[str(path)],
                )
            )
            continue
        severity = Severity.FAIL if failures else Severity.PASS
        findings.append(
            Finding(
                severity=severity,
                check="JUnit results",
                message=f"Parsed {tests} tests with {failures} failures or errors.",
                evidence=[str(path)],
            )
        )
        if failures:
            evidence_verdicts.add(Verdict.AGENT_FAILURE)
        else:
            junit_passed = True

    status_verdicts = {
        "infra_failure": Verdict.INFRA_FAILURE,
        "infrastructure_failure": Verdict.INFRA_FAILURE,
        "environment_failure": Verdict.INFRA_FAILURE,
        "verifier_failure": Verdict.VERIFIER_FAILURE,
        "verifier_error": Verdict.VERIFIER_FAILURE,
        "agent_failure": Verdict.AGENT_FAILURE,
        "failed": Verdict.AGENT_FAILURE,
        "failure": Verdict.AGENT_FAILURE,
    }
    for path in sorted(run_dir.rglob("*.json")):
        for status in _json_statuses(path):
            verdict = status_verdicts.get(status)
            if verdict:
                evidence_verdicts.add(verdict)
                findings.append(
                    Finding(
                        severity=Severity.FAIL,
                        check="run result",
                        message=f"JSON reports `{status}`.",
                        evidence=[str(path)],
                    )
                )

    for verdict in (
        Verdict.INFRA_FAILURE,
        Verdict.VERIFIER_FAILURE,
        Verdict.AGENT_FAILURE,
    ):
        if verdict in evidence_verdicts:
            return _report_for_verdict(run_dir, verdict, findings)
    if junit_passed:
        findings.append(
            Finding(
                severity=Severity.PASS,
                check="verifier result",
                message="JUnit evidence passed; no failure attribution is required.",
            )
        )
        return _report_for_verdict(run_dir, Verdict.READY, findings)

    agent_log = next(
        (path for path, content, _ in text_files if _contains_any(content, AGENT_PATTERNS)), None
    )
    if agent_log:
        findings.append(
            Finding(
                severity=Severity.WARN,
                check="agent log",
                message="An agent failure signal exists, but no healthy verifier result confirms attribution.",
                evidence=[str(agent_log)],
            )
        )
    else:
        findings.append(
            Finding(
                severity=Severity.WARN,
                check="run artifacts",
                message="No parsable JUnit result or recognized run status was found.",
            )
        )
    return _report_for_verdict(run_dir, Verdict.INCONCLUSIVE, findings)
