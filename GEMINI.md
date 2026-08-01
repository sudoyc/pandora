# Pandora Project Context

## Project Overview
Pandora is a daemon-first, cross-platform gallery browser and downloader optimized for CLI JSON/NDJSON and generic Agent Pack workflows. Provider-neutral contracts isolate the daemon from upstream-specific adapters; the built-in ExHentai adapter is one implementation. The project also includes a daemon-backed CLI, the multi-agent docs under `docs/agent/`, a Hermes skill as one packaged consumer, an optional Web frontend, and an archived Rust TUI.

*Note: `ARCHITECTURE.md` points to the canonical library under `docs/architecture/`. The Android reference-project research is historical material under `docs/archive/reference/`.*

### Architecture
- **Provider layer (Python)**: `GalleryProvider` contracts define application-facing models and behavior; each `pandora_daemon/providers/<id>/` adapter owns stateless upstream HTTP, parsing, and model translation.
- **pandora-daemon (Python/FastAPI)**: Selects a provider and owns sessions, provider-qualified state, caching, SQLite persistence, downloads, and image proxying. All frontends MUST communicate through its REST/WebSocket contract.
- **Agent Pack + CLI workflows**: Primary integration surface for agents and scripts. Use `docs/agent/` for reusable context/snippets/schemas, and use CLI `health --json`, `config --json`, `readiness --json`, `status --json`, REST, and WebSocket/NDJSON events for machine operations.
- **pandora-tui (Rust)**: Archived/frozen. Do not improve or extend it; keep only as historical REST/WS consumer reference.
- **Web Frontend**: Optional human UI, lower priority than daemon/CLI/Agent Pack contracts.

### Core Principles
- **No Direct Access:** Frontends NEVER access provider adapters or upstream services directly. All traffic is routed through `pandora-daemon`.
- **Stateless Adapters:** Upstream HTTP/parser implementations are stateless; credentials, cache, database, queues, and libraries are managed by `pandora-daemon`.
- **Database Driven:** History, favorites, bookmarks, and tag caching are persisted in an SQLite database managed by the daemon.

## Current Status
- **Provider layer**: Provider-neutral contracts, deterministic built-in registration, an isolated ExHentai adapter, and provider-qualified workspaces are implemented and fixture-tested.
- **pandora-daemon**: Core service implemented with public REST/CLI/WS v1 preserved; current reliability work is tracked in `docs/roadmap.md`.
- **Agent Pack/CLI contracts**: Generic multi-agent context, workflows, snippets, schemas, and daemon-backed machine commands live under `docs/agent/`; Hermes skill consumes them as one package.
- **pandora-tui**: Archived/frozen.
- **Web Frontend**: Optional WIP.

## Agent Readiness Checks

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
```

Run these commands in order. Readiness exit 1 is a structured upstream
not-ready result; `connect_error` means the daemon is unreachable.

## API Documentation Quick Links
- **REST Endpoints:**
  - `GET /api/health`: minimal daemon health/capability probe (no credentials or local paths)
  - `GET /api/config`: public daemon config with credentials omitted and proxy secrets redacted
  - `GET /api/readiness`: read-only authenticated upstream capability checks
  - `GET /api/history`: Browsing history
  - `GET /api/local-favorites`: Local favorites
  - `GET /api/bookmarks`: Reading progress
  - `GET /api/quick-search`: Saved search presets
  - `GET /api/filters`: Filter rules
- **Provider and API Details:** See `docs/api_reference.md` and `docs/providers/exhentai.md`.

## Important Design Decisions
- **Images:** All images are cached locally with SHA256 keys by the daemon. Frontends should load images via the daemon proxy to avoid rate limits and utilize local caching.
- **Thumbnails:** Support both `gdtm` (CSS sprite cropping) and `gdtl` (individual images) modes. The daemon provides necessary metadata for sprite cropping.
- **Downloads:** Managed entirely by the daemon. Frontends can submit URLs and monitor progress via WebSockets.

## Next Steps
1. Keep daemon REST and CLI JSON/NDJSON contracts stable and covered by tests.
2. Keep `docs/agent/` as the generic multi-agent pack; any Hermes/plugin/toolset wrapper must remain thin and daemon-backed.
3. Treat Web as optional and TUI as archived/frozen.
