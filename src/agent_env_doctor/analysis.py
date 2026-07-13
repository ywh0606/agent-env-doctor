"""Conservative attribution for local terminal-agent run artifacts."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as element_tree
from pathlib import Path

from .models import DiagnosticReport, Finding, Severity, Verdict

INFRA_PATTERNS = (
    "no space left on device",
    "cannot connect to the docker daemon",
    "docker daemon",
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


def _read_text_files(run_dir: Path) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".log", ".txt", ".out", ".err"}:
            continue
        try:
            files.append((path, _redact(path.read_text(encoding="utf-8", errors="replace"))))
        except OSError:
            continue
    return files


def _junit_result(path: Path) -> tuple[int, int, str | None]:
    try:
        root = element_tree.parse(path).getroot()
    except element_tree.ParseError as error:
        return 0, 0, f"Invalid JUnit XML: {error}"
    suites = [root] if root.tag == "testsuite" else list(root.findall(".//testsuite"))
    try:
        tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
        failures = sum(
            int(suite.attrib.get("failures", "0")) + int(suite.attrib.get("errors", "0"))
            for suite in suites
        )
    except ValueError as error:
        return 0, 0, f"Invalid JUnit counters: {error}"
    return tests, failures, None


def _json_status(path: Path) -> str | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    records = payload if isinstance(payload, list) else [payload]
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in ("verdict", "status", "result", "outcome"):
            value = record.get(key)
            if isinstance(value, str):
                return value.lower()
    return None


def _contains_any(text: str, patterns: tuple[str, ...]) -> str | None:
    lower = text.lower()
    return next((pattern for pattern in patterns if pattern in lower), None)


def analyze_run(run_directory: str) -> DiagnosticReport:
    """Classify evidence without assuming a specific agent harness."""
    run_dir = Path(run_directory).expanduser().resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    findings: list[Finding] = []
    text_files = _read_text_files(run_dir)
    for path, content in text_files:
        for verdict, patterns, label in (
            (Verdict.INFRA_FAILURE, INFRA_PATTERNS, "infrastructure failure"),
            (Verdict.VERIFIER_FAILURE, VERIFIER_PATTERNS, "verifier failure"),
        ):
            match = _contains_any(content, patterns)
            if match:
                findings.append(
                    Finding(
                        severity=Severity.FAIL,
                        check=label,
                        message=f"Observed `{match}` in log output.",
                        evidence=[str(path)],
                    )
                )
                return DiagnosticReport.from_path(
                    run_dir,
                    verdict,
                    f"The run contains evidence of {label}; it should not be scored as an agent failure.",
                    findings,
                )

    junit_paths = sorted(run_dir.rglob("*.xml"))
    valid_junit = False
    for path in junit_paths:
        tests, failures, error = _junit_result(path)
        if error:
            findings.append(
                Finding(
                    severity=Severity.FAIL,
                    check="JUnit results",
                    message=error,
                    evidence=[str(path)],
                )
            )
            return DiagnosticReport.from_path(
                run_dir,
                Verdict.VERIFIER_FAILURE,
                "The verifier output cannot be parsed as JUnit XML.",
                findings,
            )
        if tests:
            valid_junit = True
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
                return DiagnosticReport.from_path(
                    run_dir,
                    Verdict.AGENT_FAILURE,
                    "Verifier results are present and report failed tests after no infrastructure or verifier failure was found.",
                    findings,
                )

    statuses = [(path, _json_status(path)) for path in sorted(run_dir.rglob("*.json"))]
    for path, status in statuses:
        if status in {"infra_failure", "infrastructure_failure", "environment_failure"}:
            findings.append(Finding(severity=Severity.FAIL, check="run result", message=f"JSON reports `{status}`.", evidence=[str(path)]))
            return DiagnosticReport.from_path(run_dir, Verdict.INFRA_FAILURE, "Run metadata reports an infrastructure failure.", findings)
        if status in {"verifier_failure", "verifier_error"}:
            findings.append(Finding(severity=Severity.FAIL, check="run result", message=f"JSON reports `{status}`.", evidence=[str(path)]))
            return DiagnosticReport.from_path(run_dir, Verdict.VERIFIER_FAILURE, "Run metadata reports a verifier failure.", findings)
        if status in {"agent_failure", "failed", "failure"}:
            findings.append(Finding(severity=Severity.FAIL, check="run result", message=f"JSON reports `{status}`.", evidence=[str(path)]))
            return DiagnosticReport.from_path(run_dir, Verdict.AGENT_FAILURE, "Run metadata reports an agent failure.", findings)

    if valid_junit:
        findings.append(
            Finding(
                severity=Severity.PASS,
                check="verifier result",
                message="JUnit evidence passed; no failure attribution is required.",
            )
        )
        return DiagnosticReport.from_path(
            run_dir,
            Verdict.READY,
            "The available verifier evidence passed and no infrastructure failure was detected.",
            findings,
        )

    agent_log = next((path for path, content in text_files if _contains_any(content, AGENT_PATTERNS)), None)
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
    return DiagnosticReport.from_path(
        run_dir,
        Verdict.INCONCLUSIVE,
        "Available artifacts do not provide enough evidence to attribute this run reliably.",
        findings,
    )
