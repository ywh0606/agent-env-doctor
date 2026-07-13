# agent-env-doctor

**Pre-alpha** - A Terminal-Bench environment preflight and failure-attribution tool for terminal agents.

[中文文档](README.zh-CN.md) | [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) | [Harbor Framework](https://harborframework.com/)

`agent-env-doctor` is a local developer tool that answers a question benchmark scores alone cannot answer:

> Did the agent fail the task, or did the task environment fail the agent?

It will inspect a Terminal-Bench task before evaluation, analyze artifacts after a run, and produce evidence-backed Markdown or JSON reports. The goal is to make terminal-agent evaluations reproducible and their failures attributable.

## Status

This repository is **pre-alpha**. Version `0.2.0a1` is available from source for early feedback. Its checks and artifact parsers are deliberately conservative, cover only part of the planned MVP, and may change before the first stable release. Do not use a pre-alpha verdict as the sole basis for a published benchmark result.

The project is licensed under [Apache-2.0](LICENSE).

### Run From Source

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"

# Run from a Terminal-Bench checkout, or pass an absolute task directory.
.venv/bin/agent-env-doctor check hello-world

# Opt in to an image build and a shell smoke container.
.venv/bin/agent-env-doctor check hello-world --build --artifacts-dir artifacts/doctor

# Also verify commands inside the built image. Repeat --require-command as needed.
.venv/bin/agent-env-doctor check hello-world --build \
  --require-command pytest \
  --require-command git

# Check local bind availability for required host ports. Repeat --require-port as needed.
.venv/bin/agent-env-doctor check hello-world \
  --require-port 3000 \
  --require-port 8080
.venv/bin/agent-env-doctor analyze /path/to/agent-run --format json
```

By default, `check` validates task structure, Dockerfile/test asset presence, Docker CLI/daemon availability, host disk/CPU conditions, and any requested local port bindings. The static checks do not build an image or start a container. With `--build`, it builds the task image, starts a shell smoke container with `--network none`, and can verify each requested `--require-command` inside that image. `analyze` recognizes JUnit XML, JSON status fields, and selected infrastructure/verifier log signals. It collects evidence before classifying it, with the precedence `INFRA_FAILURE`, `VERIFIER_FAILURE`, `AGENT_FAILURE`, `READY`, then `INCONCLUSIVE`; it scans at most 1 MB from each text log.

## The Problem

A Terminal-Bench run can fail for reasons unrelated to an agent's ability:

| Signal | Wrong conclusion | Evidence-based conclusion |
| --- | --- | --- |
| Docker image cannot build | The agent failed | The task is blocked before the agent can act |
| Required verifier command is absent | The agent did not fix the task | The task image does not satisfy its execution contract |
| A container exits from disk exhaustion | The new agent version regressed | Evaluation infrastructure failed |
| Environment and verifier are healthy, final tests fail | Infrastructure is unreliable | The agent did not complete this task |

Without this distinction, teams can report misleading pass rates, investigate the wrong regression, or publish benchmark tasks that cannot be evaluated reliably.

## Who It Is For

- **Agent framework developers** comparing prompt, model, tool, or runtime changes.
- **Model and agent researchers** who need repeatable, auditable benchmark results.
- **Terminal-Bench maintainers and task contributors** validating a task before it is shared.
- **Engineering teams** operating internal terminal-agent evaluation pipelines.

## Scope

The first MVP is intentionally narrow: it will support the official [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) task format only.

It is not:

- A benchmark or leaderboard.
- An agent framework or an agent runner.
- A general Docker operations platform.
- A hosted observability product or a replacement for trace platforms.

## Intended Workflow

```text
Terminal-Bench task + local Docker environment
                    |
                    v
             1. Preflight check
                    |
                    v
          2. Agent run artifact analysis
                    |
                    v
      3. Markdown / JSON diagnostic report
```

1. **Preflight** verifies whether a task is evaluable before an agent run.
2. **Analysis** classifies the outcome using task metadata, container logs, verifier results, and run artifacts.
3. **Reporting** records the verdict, supporting evidence, and a minimal reproduction command.

## CLI Contract

The following pre-alpha interfaces are available from source. Their behavior may change before the first stable release:

```bash
# Run static checks only (the default).
agent-env-doctor check <task-id-or-directory>

# Opt in to Docker build and shell smoke checks.
agent-env-doctor check <task-id-or-directory> --build \
  [--build-timeout <seconds>] \
  [--artifacts-dir <directory>] \
  [--keep-image] \
  [--require-command <command>]... \
  [--require-port <port>]...

# Analyze a completed agent run directory.
agent-env-doctor analyze <run-directory>

# Render a fresh CI-friendly analysis from a run directory.
agent-env-doctor report <run-directory> --format markdown|json
```

These commands do not execute an agent. They inspect task and run artifacts, then surface whether the result can be trusted as an agent evaluation.

`--build` is intentionally opt-in because it executes local Docker work. `--artifacts-dir`, `--keep-image`, and `--require-command` require `--build`; each `--require-command` value is one executable name or path. Build and smoke output is written to `--artifacts-dir` when supplied. The temporary image is removed after the check by default; pass `--keep-image` to retain it for investigation. `--build-timeout` bounds each Docker operation, and `--require-command` may be repeated to check commands in the smoke container. `--require-port` may be repeated and tests whether each port can be bound locally on `127.0.0.1`; it does not start a service. Smoke containers run with `--network none`, but Docker image builds may require network access.

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `READY` | The task environment and verifier are healthy enough to begin evaluation. |
| `BLOCKED` | A preflight problem such as an image build, dependency, permission, or network failure prevents evaluation. |
| `INFRA_FAILURE` | Evaluation infrastructure failed during a run, such as container startup, mounts, ports, or resource exhaustion. |
| `VERIFIER_FAILURE` | The verifier is broken, unstable, or cannot determine the task result. |
| `AGENT_FAILURE` | Environment and verifier evidence are healthy, but the agent did not complete the task. |
| `INCONCLUSIVE` | Required logs or artifacts are missing, so attribution is not reliable. |

## MVP Checks

Implemented in the pre-alpha release:

- Readable `task.yaml`, a non-empty `instruction`, a Dockerfile, and test asset presence.
- Docker CLI and daemon availability.
- Host disk and CPU checks; low disk capacity is reported as a warning.
- Optional Docker image build and shell smoke container checks through `check --build`.
- Optional repeated command checks inside the built image through `--require-command`.
- Optional repeated local host-port bind checks through `--require-port`.
- Smoke containers run with Docker networking disabled (`--network none`).
- Captured Docker build and smoke output when `--artifacts-dir` is supplied.
- Temporary build-image cleanup by default, with `--keep-image` available for debugging.
- JUnit XML, JSON status fields, and selected text-log signals for attribution.
- Markdown or JSON reports with evidence paths and a Docker build reproduction command when available.

Planned but not yet implemented:

- Task files, volume mounts, permissions, and required environment variables.
- Host memory checks.
- Task network expectations and observable network failures.
- A verifier smoke test independent of an agent run.
- JSONL results, Docker logs, and additional task artifacts for attribution.

## Current Implementation

This pre-alpha is a local-first Python CLI built with:

- [Typer](https://typer.tiangolo.com/) for the command-line interface.
- [Pydantic](https://docs.pydantic.dev/) for task, run, and report models.
- [PyYAML](https://pyyaml.org/) for task metadata.
- A small subprocess-based Docker CLI boundary for builds, smoke checks, and cleanup.
- Standard-library XML parsing for JUnit result files.
- `pytest` for the tool's own test suite.

The report format should remain portable and local: human-readable Markdown plus machine-readable JSON. Cloud collection, credentials, and hosted dashboards are out of scope for v1.

## Roadmap

- [x] Define a local Terminal-Bench task-directory adapter and generic run-artifact adapter.
- [x] Add opt-in Docker image builds, isolated shell smoke containers, required-command/port checks, and build artifacts.
- [ ] Implement mounts, permissions, environment checks, host memory, network expectations, and verifier smoke tests.
- [x] Implement conservative evidence-based verdict classification.
- [x] Emit terminal, JSON, and Markdown reports.
- [ ] Publish a GitHub Actions summary from CI.
- [x] Add fixture-driven tests for all verdict categories.

## Privacy and Safety

Terminal tasks and logs can contain paths, environment variables, command output, and credentials. The intended MVP will run locally and should redact known secret patterns in generated reports. Do not publish task artifacts or reports until they have been reviewed for sensitive information.

`check --build` executes the task's Docker build instructions on the local machine. Run it only for task definitions you trust: image builds may access the network and execute build-time commands. The subsequent smoke containers are run with `--network none`, but that isolation does not apply to the build stage.

## Contributing

Contributions are welcome. Useful early contributions include Terminal-Bench fixture examples, failure-mode reports, and review of the attribution model. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Please open an issue or discussion with a minimal reproducible task, logs with secrets removed, the expected verdict, and the observed verdict.

## References

- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench): benchmark tasks for agents operating in the terminal.
- [Harbor Framework](https://harborframework.com/): the framework ecosystem behind Terminal-Bench.
