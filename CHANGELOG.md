# Changelog

All notable changes to Pandora are recorded here. The version in
`pyproject.toml` is the release version source of truth.

## [Unreleased]

## [0.2.0] - 2026-07-25

### Added

- Daemon-backed CLI JSON/NDJSON and Agent Pack workflows.
- Structured readiness and machine contract version 1.
- Versioned, recoverable download state with consistency reporting and explicit repair operations.
- Repository-wide local and hosted CI checks.
- Python wheel and source-distribution release candidate workflow.

### Changed

- Download lifecycle state, terminal events, REST errors, and CLI exits now use documented public contracts.

### Security

- Public machine surfaces and service logs omit credentials, proxy secrets, download tokens, and local paths.
