# Pandora Project Context

## Project Overview
Pandora is a daemon-first ExHentai/E-Hentai browser and downloader optimized for CLI JSON/NDJSON and Hermes agent/plugin workflows. It consists of the reusable Python API library (`exhentai_api`), the local FastAPI daemon (`pandora-daemon`), a daemon-backed CLI, an optional Web frontend, and an archived Rust TUI.

*Note: The `ARCHITECTURE.md` file in the project root is a detailed research report on the `Ehviewer_CN_SXJ` Android application, which serves as the reference implementation and inspiration for Pandora's API and data models.*

### Architecture
- **exhentai_api (Python)**: The core, stateless abstraction over the ExHentai site.
- **pandora-daemon (Python/FastAPI)**: The intermediary that handles sessions, caching, database persistence (SQLite), download management, and provides a proxy for images. It runs a REST + WebSocket API on `localhost:7860`. All frontends MUST communicate with ExHentai through this daemon.
- **CLI / Hermes workflows**: Primary integration surface for agents and scripts. Use `health --json`, `config --json`, REST, and WebSocket/NDJSON events.
- **pandora-tui (Rust)**: Archived/frozen. Do not improve or extend it; keep only as historical REST/WS consumer reference.
- **Web Frontend**: Optional human UI, lower priority than daemon/CLI/Hermes contracts.

### Core Principles
- **No Direct Access:** Frontends NEVER access ExHentai directly. All traffic is routed through `pandora-daemon`.
- **Stateless API:** `exhentai_api` is purely functional; state (cookies, cache) is managed by `pandora-daemon`.
- **Database Driven:** History, favorites, bookmarks, and tag caching are persisted in an SQLite database managed by the daemon.

## Current Status
- **exhentai_api**: Completed. (22 API methods, 17 model types, 11 parsers, fully tested).
- **pandora-daemon**: Completed. (Proxy, SQLite DB, Background prefetch, Download manager, WebSocket events).
- **CLI/Hermes contracts**: **Current objective.**
- **pandora-tui**: Archived/frozen.
- **Web Frontend**: Optional WIP.

## Agent Readiness Checks

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli status --json
```

## API Documentation Quick Links
- **REST Endpoints:**
  - `GET /api/health`: minimal daemon health/capability probe (no credentials or local paths)
  - `GET /api/config`: public daemon config with credentials omitted and proxy secrets redacted
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
2. Package common flows in the Hermes skill/plugin layer without exposing credentials.
3. Treat Web as optional and TUI as archived/frozen.
