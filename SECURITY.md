# Security Policy

## Supported Versions

`agent-env-doctor` is pre-alpha and does not yet have a released package or supported-version line.

## Reporting a Vulnerability

At the time this policy was added, no private vulnerability-reporting channel has been configured. Do not disclose a vulnerability, credentials, private task content, or proof-of-concept that could harm users in a public issue or pull request.

Before the first public release, maintainers should enable GitHub private vulnerability reporting or publish a monitored security contact, then update this document with that reporting route and an expected response window.

## Handling Sensitive Data

The intended tool will inspect local task definitions and evaluation artifacts. Those inputs can include filesystem paths, environment variables, command output, and secrets. Contributors and users should redact sensitive material before sharing diagnostics outside their local environment.
