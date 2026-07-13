# Contributing to agent-env-doctor

Thanks for considering a contribution to `agent-env-doctor`.

The project is pre-alpha. Its first milestone is a local Python CLI that diagnoses whether a Terminal-Bench evaluation failure is attributable to the agent, task environment, verifier, or incomplete evidence. The current scope is the official Terminal-Bench task format only.

## Before You Start

- Read the project scope and pre-alpha CLI contract in `README.md`.
- Search existing issues before opening a new one.
- For a substantial change, open an issue first so maintainers can confirm that it fits the initial scope.
- Do not include credentials, tokens, private task content, or unredacted logs in issues, pull requests, or commits.

## Good Early Contributions

- Redacted examples of Terminal-Bench environment failures.
- Fixture proposals for the verdicts: `READY`, `BLOCKED`, `INFRA_FAILURE`, `VERIFIER_FAILURE`, `AGENT_FAILURE`, and `INCONCLUSIVE`.
- Precise feedback on the task-artifact contract and attribution rules.
- Documentation corrections and clarity improvements.

## Development and Tests

The pre-alpha CLI and test suite are available. Use a virtual environment and run:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
.venv/bin/python -m pytest
```

Contributions that add implementation should include focused tests for their behavior. Tests and fixtures must be deterministic and must not require private data, credentials, or a network connection unless the test explicitly verifies an isolated integration boundary.

## Pull Requests

- Keep each pull request narrowly focused.
- Explain the problem, the evidence used for any attribution rule, and the affected verdicts.
- Update documentation when the public behavior, task contract, or report schema changes.
- Run the available test suite before requesting review.
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).

By submitting a contribution, you agree that it may be licensed under the [Apache License 2.0](LICENSE).
