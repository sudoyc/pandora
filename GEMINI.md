# Pandora Project Context

## Project Overview
Pandora is a daemon-first ExHentai/E-Hentai browser and downloader optimized for CLI JSON/NDJSON and generic Agent Pack workflows. It consists of the reusable Python API library (`exhentai_api`), the local FastAPI daemon (`pandora-daemon`), a daemon-backed CLI, the multi-agent docs under `docs/agent/`, a Hermes skill as one packaged consumer, an optional Web frontend, and an archived Rust TUI.

*Note: `ARCHITECTURE.md` points to the canonical library under `docs/architecture/`. The Android reference-project research is historical material under `docs/archive/reference/`.*

### Architecture
- **exhentai_api (Python)**: The core, stateless abstraction over the ExHentai site.
- **pandora-daemon (Python/FastAPI)**: The intermediary that handles sessions, caching, database persistence (SQLite), download management, and provides a proxy for images. It runs a REST + WebSocket API on `localhost:7860`. All frontends MUST communicate with ExHentai through this daemon.
- **Agent Pack + CLI workflows**: Primary integration surface for agents and scripts. Use `docs/agent/` for reusable context/snippets/schemas, and use CLI `health --json`, `config --json`, `readiness --json`, `status --json`, REST, and WebSocket/NDJSON events for machine operations.
- **pandora-tui (Rust)**: Archived/frozen. Do not improve or extend it; keep only as historical REST/WS consumer reference.
- **Web Frontend**: Optional human UI, lower priority than daemon/CLI/Agent Pack contracts.

### Core Principles
- **No Direct Access:** Frontends NEVER access ExHentai directly. All traffic is routed through `pandora-daemon`.
- **Stateless API:** `exhentai_api` is purely functional; state (cookies, cache) is managed by `pandora-daemon`.
- **Database Driven:** History, favorites, bookmarks, and tag caching are persisted in an SQLite database managed by the daemon.

## Current Status
- **exhentai_api**: Core surface implemented and fixture-tested; upstream compatibility remains ongoing maintenance.
- **pandora-daemon**: Core service implemented; current reliability work is tracked in `docs/roadmap.md`.
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
- **Python API Details:** See `docs/api_reference.md` and `docs/exhentai_api_usage.md`.

## Important Design Decisions
- **Images:** All images are cached locally with SHA256 keys by the daemon. Frontends should load images via the daemon proxy to avoid rate limits and utilize local caching.
- **Thumbnails:** Support both `gdtm` (CSS sprite cropping) and `gdtl` (individual images) modes. The daemon provides necessary metadata for sprite cropping.
- **Downloads:** Managed entirely by the daemon. Frontends can submit URLs and monitor progress via WebSockets.

## Next Steps
1. Keep daemon REST and CLI JSON/NDJSON contracts stable and covered by tests.
2. Keep `docs/agent/` as the generic multi-agent pack; any Hermes/plugin/toolset wrapper must remain thin and daemon-backed.
3. Treat Web as optional and TUI as archived/frozen.
