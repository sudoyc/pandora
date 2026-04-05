# Pandora

Open the box. Browse, search, and download from ExHentai — daemon + multi-frontend.

## Architecture

```
exhentai_api (Python library)     -- stateless, reusable
        |
pandora-daemon (FastAPI)          -- session, cache, download, image proxy
        | REST + WebSocket (localhost:7860)
        |-- Rust TUI (ratatui)    -- terminal with image preview
        |-- Web frontend          -- browser, planned
        +-- CLI                   -- download + status
```

**Design principle:** frontends never access ExHentai directly. All requests go through the daemon, which handles session, caching, and rate limiting.

## Components

### exhentai_api

Async Python library. 22 API methods, 17 model types, 11 parsers, 110 tests. Fully aligned with the Android EhViewer reference project.

| Category | Methods |
|----------|---------|
| Browse | `get_homepage`, `search`, `get_popular`, `get_toplist`, `get_watched` |
| Gallery | `get_gallery_details`, `get_image_url`, `get_gallery_token` |
| Interaction | `comment_gallery`, `vote_comment`, `rate_gallery` |
| Favorites | `get_favorites`, `add_favorite`, `modify_favorites` |
| Resources | `get_torrent_list`, `get_archive_list`, `download_archive` |
| Tags | `get_mytags`, `add_tag`, `delete_tag` |
| User | `get_home_detail`, `reset_image_limit`, `get_profile` |
| Search | `image_search` (SHA1-based) |

### pandora-daemon

FastAPI service wrapping `exhentai_api`. 297 tests.

- **Image proxy** — all image types cached with SHA256 keys, LRU eviction (2 GB default)
- **SQLite database** — browsing history, local favorites, reading bookmarks, saved searches, gallery filters, tag cache. Auto-triggers on gallery view and page prefetch
- **Server-side prefetch** — background prefetch of surrounding pages during reading
- **Thumb cropping** — CSS sprite cropping for gdtm-mode thumbnails, on-demand preview page loading
- **Download manager** — complete offline gallery clones (metadata + cover + thumbs + pages), resume support, WebSocket progress events
- **Library API** — browse downloaded galleries, serve local files
- **Tag suggest** — EhTagTranslation database (~15K tags), substring search with prefix-first ranking
- **Config** — TOML-based (`~/.config/pandora/config.toml`)

30+ REST endpoints, WebSocket real-time events. SQLite persistence (`~/.config/pandora/pandora.db`).

### Rust TUI

Terminal frontend built with ratatui + ratatui-image. 21 source files, 16 tests.

- Three-pane layout: gallery list with covers | thumbnail grid | metadata panel
- Reader mode with full-size page viewing (kitty/sixel/halfblocks protocol)
- Event-driven rendering — `tokio::select!` main loop, zero CPU when idle
- In-memory page cache with sliding-window preload (LRU, ±10 local / ±3 online)
- vim-style navigation, search with category filter + tag autocomplete (debounced)
- Downloaded gallery browsing via Library API (local file serving)
- WebSocket real-time download progress

### CLI

```bash
pandora dl <url>    # submit download, monitor progress with rich progress bars
pandora status      # check download queue (active/completed/failed)
```

## Quick Start

### 1. Configure credentials

```bash
# Edit ~/.config/pandora/config.toml
# Set your ExHentai session cookies:
#   [credentials]
#   igneous = "..."
#   ipb_member_id = "..."
```

### 2. Start daemon

```bash
uv run python -m pandora_daemon
# Listening on http://127.0.0.1:7860
```

### 3. Use a frontend

```bash
# TUI
cd pandora-tui && cargo run --release

# CLI
uv run python -m pandora_daemon.cli dl "https://exhentai.org/g/12345/abctoken/"
```

## Development

```bash
# Python tests (407)
uv run pytest tests/ -v

# Rust TUI tests (16)
cd pandora-tui && cargo test

# Build optimized TUI binary
cd pandora-tui && cargo build --release
```

## API Reference

Full daemon REST API and `exhentai_api` method reference in [`docs/`](docs/).

## License

Private project.
