# Pandora Project Context

## Project Overview
Pandora is a completely self-contained suite of applications for browsing, searching, and downloading from ExHentai. It consists of a reusable Python API library (`exhentai_api`), a local backend daemon (`pandora-daemon`) running FastAPI, a terminal UI in Rust (`pandora-tui`), and a planned Web frontend.

*Note: The `ARCHITECTURE.md` file in the project root is a detailed research report on the `Ehviewer_CN_SXJ` Android application, which serves as the reference implementation and inspiration for Pandora's API and data models.*

### Architecture
- **exhentai_api (Python)**: The core, stateless abstraction over the ExHentai site.
- **pandora-daemon (Python/FastAPI)**: The intermediary that handles sessions, caching, database persistence (SQLite), download management, and provides a proxy for images. It runs a REST + WebSocket API on `localhost:7860`. All frontends MUST communicate with ExHentai through this daemon.
- **pandora-tui (Rust)**: Terminal frontend. Development is currently suspended.
- **Web Frontend**: (Planned/In Progress) The next phase of development.

### Core Principles
- **No Direct Access:** Frontends NEVER access ExHentai directly. All traffic is routed through `pandora-daemon`.
- **Stateless API:** `exhentai_api` is purely functional; state (cookies, cache) is managed by `pandora-daemon`.
- **Database Driven:** History, favorites, bookmarks, and tag caching are persisted in an SQLite database managed by the daemon.

## Current Status
- **exhentai_api**: Completed. (22 API methods, 17 model types, 11 parsers, fully tested).
- **pandora-daemon**: Completed. (Proxy, SQLite DB, Background prefetch, Download manager, WebSocket events).
- **pandora-tui**: Suspended.
- **Web Frontend**: **Current objective.**

## Technical Stack for Web Frontend (Recommended Defaults)
- **Frontend Framework**: React (TypeScript) or Angular.
- **Styling**: Vanilla CSS is preferred for maximum flexibility. Avoid TailwindCSS unless specifically requested.
- **Backend API**: Interact exclusively with the local `pandora-daemon` via REST/WebSocket endpoints at `http://127.0.0.1:7860`.

## API Documentation Quick Links
- **REST Endpoints:**
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
1. Design and plan the Web frontend architecture using `enter_plan_mode`.
2. Ensure the UI design is modern, rich, and visually appealing, utilizing platform-native primitives.
3. Validate API interactions with the existing `pandora-daemon`.
