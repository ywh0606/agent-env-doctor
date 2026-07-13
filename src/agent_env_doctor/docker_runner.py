"""Small, subprocess-based Docker execution boundary for preflight checks."""

from __future__ import annotations

import re
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    output: str
    timed_out: bool = False


class DockerRunner:
    """Build and smoke-test task images without coupling core logic to a Docker SDK."""

    def __init__(self, timeout_seconds: int = 300) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, arguments: list[str], timeout_seconds: int | None = None) -> CommandResult:
        try:
            completed = subprocess.run(
                ["docker", *arguments],
                capture_output=True,
                text=True,
                timeout=timeout_seconds or self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            output = _combined_output(error.stdout, error.stderr)
            return CommandResult(returncode=124, output=output, timed_out=True)
        except OSError as error:
            return CommandResult(returncode=127, output=str(error))
        return CommandResult(
            returncode=completed.returncode,
            output=_combined_output(completed.stdout, completed.stderr),
        )

    def build(self, task_dir: Path, image_tag: str) -> CommandResult:
        return self.run(["build", "--tag", image_tag, "--file", str(task_dir / "Dockerfile"), str(task_dir)])

    def smoke(self, image_tag: str, command: str | None = None) -> CommandResult:
        shell_command = command or "true"
        return self.run(
            ["run", "--rm", "--network", "none", "--entrypoint", "/bin/sh", image_tag, "-lc", shell_command]
        )

    def remove_image(self, image_tag: str) -> CommandResult:
        return self.run(["image", "rm", "--force", image_tag])


def image_tag_for(task_dir: Path) -> str:
    """Return a Docker-safe temporary tag that is unique to one doctor invocation."""
    slug = re.sub(r"[^a-z0-9]+", "-", task_dir.name.lower()).strip("-") or "task"
    return f"agent-env-doctor/{slug}:{uuid.uuid4().hex[:12]}"


def _combined_output(stdout: str | bytes | None, stderr: str | bytes | None) -> str:
    parts: list[str] = []
    for value in (stdout, stderr):
        if not value:
            continue
        if isinstance(value, bytes):
            parts.append(value.decode("utf-8", errors="replace"))
        else:
            parts.append(value)
    return "\n".join(parts).strip()
