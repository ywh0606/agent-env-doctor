# agent-env-doctor

**Pre-alpha** - A Terminal-Bench environment preflight and failure-attribution tool for terminal agents.

[中文文档](README.zh-CN.md) | [Terminal-Bench](https://github.com/harbor-framework/terminal-bench) | [Harbor Framework](https://harborframework.com/)

`agent-env-doctor` is a local developer tool that answers a question benchmark scores alone cannot answer:

> Did the agent fail the task, or did the task environment fail the agent?

It will inspect a Terminal-Bench task before evaluation, analyze artifacts after a run, and produce evidence-backed Markdown or JSON reports. The goal is to make terminal-agent evaluations reproducible and their failures attributable.

## Status

This repository is **pre-alpha**. A local Python CLI is available from source for early feedback. Its checks and artifact parsers are deliberately conservative, cover only part of the planned MVP, and may change before `0.1.0`. Do not use a pre-alpha verdict as the sole basis for a published benchmark result.

The project is licensed under [Apache-2.0](LICENSE).

### Run From Source

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"

# Run from a Terminal-Bench checkout, or pass an absolute task directory.
.venv/bin/agent-env-doctor check hello-world
.venv/bin/agent-env-doctor analyze /path/to/agent-run --format json
```

`check` currently validates task structure, Dockerfile/test asset presence, and Docker CLI/daemon availability. `analyze` currently recognizes JUnit XML, JSON status fields, and selected infrastructure/verifier log signals. It does not yet build images, start containers, or execute verifier smoke tests.

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

## Planned CLI Contract

The following pre-alpha interfaces are available from source. Their behavior may change before `0.1.0`:

```bash
# Check a Terminal-Bench task and its local execution environment.
agent-env-doctor check <task-id-or-directory>

# Analyze a completed agent run directory.
agent-env-doctor analyze <run-directory>

# Render a fresh CI-friendly analysis from a run directory.
agent-env-doctor report <run-directory> --format markdown|json
```

These commands do not execute an agent. They inspect task and run artifacts, then surface whether the result can be trusted as an agent evaluation.

## Planned Verdicts

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
- JUnit XML, JSON status fields, and selected text-log signals for attribution.
- Markdown or JSON reports with evidence paths and a Docker build reproduction command when available.

Planned but not yet implemented:

- Docker daemon availability, image build, and container startup.
- Task files, volume mounts, permissions, and required environment variables.
- Host resources such as disk, memory, CPU, and required ports.
- Task network expectations and observable network failures.
- Required commands and runtime dependencies in the task image.
- A verifier smoke test independent of an agent run.
- JUnit XML, JSON/JSONL results, Docker logs, and task artifacts for attribution.

## Example Output

The following is illustrative output from the current report schema; exact wording may change during pre-alpha:

```text
Task: repair-ci-config
Verdict: BLOCKED

[PASS] Required task files are present
[PASS] Found Dockerfile
[PASS] Found tests directory
[FAIL] Docker CLI was not found on PATH

Why this is not an agent failure:
  Docker is unavailable, so no agent received a runnable environment.

Reproduce:
  docker info

Evidence:
  tasks/repair-ci-config/task.yaml
```

## Illustrative GitHub Actions Summary

This is a planned CI summary format; GitHub Actions publishing is not implemented yet:

```markdown
## agent-env-doctor: evaluation attribution

| Verdict | Tasks |
| --- | ---: |
| READY | 76 |
| BLOCKED | 8 |
| VERIFIER_FAILURE | 4 |
| AGENT_FAILURE | 12 |

Agent score: 42 / 76 evaluable tasks (55.3%)

Top blocking cause: Docker daemon unavailable on 5 evaluation workers.
Evidence: `artifacts/agent-env-doctor/report.json`
```

## Technical Direction

The MVP is expected to be a local-first Python CLI:

- [Typer](https://typer.tiangolo.com/) for the command-line interface.
- [Rich](https://rich.readthedocs.io/) for terminal reports.
- [Pydantic](https://docs.pydantic.dev/) for task, run, and report models.
- [Docker SDK for Python](https://docker-py.readthedocs.io/) for environment inspection.
- Standard XML parsing or a JUnit parser for result files.
- `pytest` for the tool's own test suite.

The report format should remain portable and local: human-readable Markdown plus machine-readable JSON. Cloud collection, credentials, and hosted dashboards are out of scope for v1.

## Roadmap

- [x] Define a local Terminal-Bench task-directory adapter and generic run-artifact adapter.
- [ ] Implement Docker image builds, container startup, mounts, resources, dependencies, and verifier smoke tests.
- [x] Implement conservative evidence-based verdict classification.
- [x] Emit terminal, JSON, and Markdown reports.
- [ ] Publish a GitHub Actions summary from CI.
- [x] Add fixture-driven tests for all verdict categories.

## Privacy and Safety

Terminal tasks and logs can contain paths, environment variables, command output, and credentials. The intended MVP will run locally and should redact known secret patterns in generated reports. Do not publish task artifacts or reports until they have been reviewed for sensitive information.

## Contributing

Contributions are welcome. Useful early contributions include Terminal-Bench fixture examples, failure-mode reports, and review of the attribution model. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

Please open an issue or discussion with a minimal reproducible task, logs with secrets removed, the expected verdict, and the observed verdict.

## References

- [Terminal-Bench](https://github.com/harbor-framework/terminal-bench): benchmark tasks for agents operating in the terminal.
- [Harbor Framework](https://harborframework.com/): the framework ecosystem behind Terminal-Bench.
