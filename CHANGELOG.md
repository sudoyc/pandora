# Changelog

All notable changes to Pandora are recorded here. The version in
`pyproject.toml` is the release version source of truth.

## [Unreleased]

### Added

- Add three persistent Web themes, responsive desktop/mobile gallery layouts, and grid/list density controls.
- Add advanced gallery search with tag suggestions, category/rating/page filters, and structured recent-search history.
- Add a deterministic provider registry, provider-neutral domain contract, and a 23-endpoint replacement-provider architecture benchmark.

### Changed

- Separate deterministic fixture checks from credentialed live usability acceptance and require decoded browser image pixels for release evidence.
- Use cursor-based near-end prefetch for homepage, search, and watched feeds, with deduplication and explicit completion states.
- Move the built-in ExHentai HTTP/parser implementation behind a nested adapter and isolate non-default provider databases, download state, and libraries while preserving default paths and public contract v1.

### Fixed

- Support current thumbnail and H@H image delivery through TUN fake-IP DNS, required referrer headers, a shared bounded connection pool, and one retry for transient transport failures.
- Suppress stale WebSocket errors emitted after React effect cleanup.
- Reject zero-byte image responses before they can enter the image cache.
- Reject unsafe provider IDs, unregistered defaults, and factory identity mismatches before selecting a persistent provider workspace.

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
