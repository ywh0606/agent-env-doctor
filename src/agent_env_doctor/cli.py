"""Command-line entry point."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from .analysis import analyze_run
from .preflight import check_task
from .render import markdown

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Terminal-Bench environment preflight and failure attribution.",
)


def _write_report(report, output: Path | None, format_name: str) -> None:
    content = markdown(report) if format_name == "markdown" else report.model_dump_json(indent=2) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
    typer.echo(content, nl=False)


@app.command()
def check(
    task: str = typer.Argument(..., help="Task directory or task id from a local Terminal-Bench checkout."),
    format: str = typer.Option("markdown", "--format", case_sensitive=False, help="markdown or json."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional path for the report."),
) -> None:
    """Check a Terminal-Bench task and local Docker availability."""
    if format not in {"markdown", "json"}:
        raise typer.BadParameter("format must be markdown or json")
    try:
        _write_report(check_task(task), output, format)
    except FileNotFoundError as error:
        raise typer.BadParameter(str(error)) from error


@app.command()
def analyze(
    run_directory: str = typer.Argument(..., help="Directory containing agent run artifacts."),
    format: str = typer.Option("markdown", "--format", case_sensitive=False, help="markdown or json."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional path for the report."),
) -> None:
    """Analyze local artifacts from a completed agent run."""
    if format not in {"markdown", "json"}:
        raise typer.BadParameter("format must be markdown or json")
    try:
        _write_report(analyze_run(run_directory), output, format)
    except FileNotFoundError as error:
        raise typer.BadParameter(str(error)) from error


@app.command()
def report(
    run_directory: str = typer.Argument(..., help="Directory containing agent run artifacts."),
    format: str = typer.Option("markdown", "--format", case_sensitive=False, help="markdown or json."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional path for the report."),
) -> None:
    """Render a fresh CI-friendly report from a run directory."""
    analyze(run_directory=run_directory, format=format, output=output)
