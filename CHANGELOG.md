# Changelog

All notable changes to `agent-env-doctor` are documented in this file.

## 0.2.0a1 - Pre-alpha

### Added

- Opt-in Docker image builds and shell smoke-container checks through `check --build`.
- `--build-timeout`, `--artifacts-dir`, `--keep-image`, and repeatable `--require-command` / `--require-port` options for `check`.
- Host disk and CPU preflight checks. Low available disk is reported as a warning.
- Local host-port bind checks and Docker-network-disabled smoke containers.
- Docker build and smoke output capture when an artifacts directory is requested.

### Changed

- Temporary images created for build checks are removed by default.
