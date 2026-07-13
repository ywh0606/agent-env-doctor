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
    build: bool = typer.Option(False, "--build", help="Build the task image and run container smoke checks."),
    build_timeout: int = typer.Option(300, "--build-timeout", min=1, help="Timeout in seconds for each Docker operation."),
    artifacts_dir: Path | None = typer.Option(None, "--artifacts-dir", help="Directory for Docker command logs."),
    keep_image: bool = typer.Option(False, "--keep-image", help="Keep the temporary image after a successful build."),
    require_command: list[str] = typer.Option([], "--require-command", help="Command that must exist in the built image; repeatable."),
    require_port: list[int] = typer.Option([], "--require-port", help="Host port that must be available; repeatable."),
) -> None:
    """Check a Terminal-Bench task and optionally execute Docker smoke checks."""
    if format not in {"markdown", "json"}:
        raise typer.BadParameter("format must be markdown or json")
    try:
        _write_report(
            check_task(
                task,
                build=build,
                build_timeout=build_timeout,
                artifacts_dir=artifacts_dir,
                keep_image=keep_image,
                required_commands=tuple(require_command),
                required_ports=tuple(require_port),
            ),
            output,
            format,
        )
    except (FileNotFoundError, ValueError) as error:
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
