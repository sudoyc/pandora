# Pandora

A cross-platform local gallery service for browsing, search, downloads, and offline libraries through a daemon, CLI, and Agent Pack.

## Architecture

```
GalleryProvider adapters           -- upstream-specific HTTP and parsing
        |
pandora-daemon (FastAPI)           -- provider selection, state, cache, downloads
        | REST + WebSocket (localhost:7860)
        |-- CLI                    -- daemon-backed JSON/NDJSON workflow
        |-- Agent Pack             -- generic daemon-backed agent workflows
        |   |-- Hermes skill       -- first packaged consumer
        |   +-- thin wrappers      -- optional future consumers
        +-- Web frontend           -- optional browser UI, work in progress
```

**Design principle:** frontends and agents never access provider adapters or upstream services directly. All requests go through the daemon, which owns provider selection, sessions, caching, downloads, and rate limiting. Agent/bot workflows should prefer the generic [Pandora Agent Pack](docs/agent/README.md) and CLI JSON/NDJSON contract over Web/TUI/client-cache work.

## Documentation

- [Documentation index](docs/README.md)
- [Current system architecture](docs/architecture/system-overview.md)
- [Architecture decisions](docs/architecture/decisions.md)
- [Development roadmap](docs/roadmap.md)
- [Long-running unattended development](docs/development/unattended-development.md)
- [Executable work program](docs/development/work-program.md)
- [Release process and rollback](docs/development/release-process.md)
- [Long-running goal prompt](docs/development/goal-prompt.md)
- [Changelog](CHANGELOG.md)
- [Historical documentation](docs/archive/README.md)

## Agent Pack

Pandora's canonical agent-facing integration is the [Pandora Agent Pack](docs/agent/README.md). It documents reusable context, contracts, workflows, snippets, JSON schemas, and safety boundaries for Hermes, OpenCode, Codex, Claude, MCP-style wrappers, shell scripts, and future thin plugins.

Hermes is one packaged consumer through `.agents/skills/pandora/SKILL.md`; see [Hermes integration](docs/hermes_integration.md) for Hermes-specific packaging notes. There is no separate in-repo Hermes plugin/toolset package yet.

The agent boundary is intentionally thin:

- Agents and wrappers consume `pandora` CLI JSON/NDJSON commands or daemon REST/WebSocket endpoints.
- They must not bypass `pandora-daemon` for auth, cache, download queue, session, bookmark, or library state.
- They must not import provider adapters or their upstream implementation for user workflows.
- Prefer machine output (`--json`, `--ndjson`) over parsing human text.
- Keep complex or ambiguous choices in the agent; Pandora exposes primitives.

Scheme A for translated tag search is preserved. Agents run `tags status --json`, refresh if needed, call `tags suggest "丝袜" --json`, choose a candidate such as `female:stockings`, then search with `pandora search "female:stockings" --search-tags --json`. Pandora does not automatically resolve translated text into tag queries.

## Components

### Built-in ExHentai provider

The built-in adapter keeps its stateless HTTP client, parsers, and upstream models under `pandora_daemon.providers.exhentai.upstream`. Its 22 API methods, 17 model types, and 11 parsers are fixture-tested against the Android reference project; live upstream compatibility remains an explicit maintenance concern.

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

FastAPI service orchestrating the selected `GalleryProvider` and owning all persistent application state.

- **Image proxy** — all image types cached with SHA256 keys, LRU eviction (2 GB default)
- **SQLite database** — browsing history, local favorites, reading bookmarks, saved searches, gallery filters, tag cache. Auto-triggers on gallery view and page prefetch
- **Server-side prefetch** — background prefetch of surrounding pages during reading
- **Thumb cropping** — CSS sprite cropping for gdtm-mode thumbnails, on-demand preview page loading
- **Download manager** — complete offline gallery clones (metadata + cover + thumbs + pages), resume support, WebSocket progress events
- **Library API** — browse downloaded galleries, serve local files
- **Tag suggest/maintenance** — versioned EhTagTranslation database, ETag-aware refresh, substring search with prefix-first ranking
- **Config** — TOML-based provider selection and credentials (`~/.config/pandora/config.toml`)

30+ REST endpoints, WebSocket real-time events. The default provider retains SQLite at `~/.config/pandora/pandora.db`; non-default providers use provider-qualified database, download-state, and library paths.

### Rust TUI (Archived/Frozen)

The Rust TUI in `pandora-tui/` is archived and no longer maintained. It is kept as a historical/reference REST/WebSocket consumer and must not receive feature work or polish.

- Three-pane layout: gallery list with covers | thumbnail grid | metadata panel
- Reader mode with full-size page viewing (kitty/sixel/halfblocks protocol)
- Event-driven rendering — `tokio::select!` main loop, zero CPU when idle
- In-memory page cache with sliding-window preload (LRU, ±10 local / ±3 online)
- vim-style navigation, search with category filter + tag autocomplete (debounced)
- Downloaded gallery browsing via Library API (local file serving)
- WebSocket real-time download progress

### CLI

```bash
pandora download <url>              # legacy: submit download, monitor progress
pandora dl <url>                    # alias
pandora download run <url|gid> [token] --ndjson
pandora download add <url|gid> [token]
pandora download list --json
pandora download report --json
pandora download repair <gid> [--apply] --json
pandora download forget <gid> [--apply] --json
pandora download watch [gid] --ndjson
pandora download cancel <gid>
pandora download resume <gid>
pandora download retry <gid>
pandora download pages <gid>
pandora health --json
pandora config --json
pandora readiness --json
pandora status --json
pandora search "keyword" --page 0 --json
pandora search "female:stockings" --search-tags --json
pandora gallery <url|gid> [token] --json
pandora library list --json
pandora tags status --json
pandora tags refresh --json
pandora tags suggest "artist" --json
pandora favorites list --json      # all favorites (`slot=-1`)
pandora popular --json
pandora toplist --tl 15 --json
pandora watched --page 0 --json
```

Commands accept `--daemon-url http://127.0.0.1:7860`, `--timeout 30`, and `--json` on request/response style commands. `download run --ndjson` is the preferred bot path because it attaches to WebSocket first, submits the task, emits `download_submitted` or `download_already_queued`, and watches terminal WebSocket events. `download add` plus `download watch` remains available, but a late watcher can miss earlier events. In machine mode, CLI failures use a stable envelope like `{"ok": false, "error": {"code": "connect_error", "message": "..."}}`.

Bootstrap diagnostics run in this order: `health`, `config`, `readiness`, then
`status`. A `readiness --json` exit code of 1 is a structured upstream not-ready
result; inspect its JSON instead of treating it as a daemon connection failure.

Agent search uses scheme A intentionally: the CLI does not resolve ambiguous translated text into ExHentai tag queries. Agents should check `pandora tags status --json`, refresh if stale or unloaded, inspect `pandora tags suggest "丝袜" --json`, choose a candidate such as `female:stockings`, then call `pandora search "female:stockings" --search-tags --json`. Search also exposes primitive advanced flags including `--category` (include bitmask), `--min-rating`, `--search-name`, `--search-description`, `--search-torrent`, `--search-low-power-tags`, `--disable-language-filter`, `--show-expunged`, `--min-pages`, and `--max-pages`.

`pandora gallery ...` redacts daemon-only `api_uid` and `api_key` fields by default. Public gallery machine surfaces expose user-facing metadata and route identifiers such as `gid` and `token`. Public download machine surfaces expose download state, not daemon-internal helper fields such as `viewer_urls`, `thumb_urls`, `thumb_sprites`, download-task `token`, or local output directory/path values. `pandora download pages ... --json` reports public page states such as `completed` instead of the internal `done` value.

`pandora download report --json` performs a read-only comparison of registered
terminal tasks with library metadata and page files. Inspect `consistent` and
the issue codes; an inconsistent report is still a successful command response.
`download repair` and `download forget` default to a no-write preview. Pass
`--apply` only after inspecting the returned actions. Repair registers one
complete unregistered library entry; forget removes inactive task state while
leaving metadata, pages, and directories untouched.

## Quick Start

### 1. Install the verified wheel

```bash
PANDORA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}/pandora"
uv venv --python 3.12 "$PANDORA_HOME/venv"
uv pip install --python "$PANDORA_HOME/venv/bin/python" \
  --link-mode copy /path/to/pandora-VERSION-py3-none-any.whl
```

The wheel is Pandora's default runtime distribution. Source-checkout `uv run`
commands are for development; see the [deployment guide](docs/deployment.md) for
the artifact boundary and service setup.

### 2. Configure credentials

```bash
# Edit ~/.config/pandora/config.toml
# Select the built-in provider and set its session cookies:
#   [provider]
#   id = "exhentai"
#   [provider.credentials]
#   igneous = "..."
#   ipb_member_id = "..."
#   ipb_pass_hash = "..."  # Optional; leave empty if unused.
```

### 3. Start daemon

```bash
"$PANDORA_HOME/venv/bin/pandora-daemon"
# Listening on http://127.0.0.1:7860
```

### 4. Use the CLI

```bash
# Agent/script readiness checks
"$PANDORA_HOME/venv/bin/pandora" health --json
"$PANDORA_HOME/venv/bin/pandora" config --json
"$PANDORA_HOME/venv/bin/pandora" readiness --json
"$PANDORA_HOME/venv/bin/pandora" status --json

# CLI
"$PANDORA_HOME/venv/bin/pandora" search "keyword" --json
"$PANDORA_HOME/venv/bin/pandora" download run "https://exhentai.org/g/12345/abcdef0123/" --ndjson
```

The optional Web consumer is not bundled in the wheel. Run it separately from
a source checkout with `cd pandora-web && npm run dev` when needed.

See [`docs/deployment.md`](docs/deployment.md) for daemon startup, readiness checks, systemd user-service setup, CLI smoke tests, and config safety notes. See [`docs/agent/README.md`](docs/agent/README.md) for generic agent workflows and [`docs/hermes_integration.md`](docs/hermes_integration.md) for Hermes-specific packaging guidance.

## Development

From a clean checkout with `uv`, Node.js, and npm installed, run the complete
local gate with one command:

```bash
uv run --frozen python scripts/check.py
```

The checker verifies `uv.lock`, installs and audits the exact Web dependency
tree, checks release metadata, tracked Markdown links and Agent JSON Schemas,
runs all Python tests, runs Web unit/browser tests, lint, and build, and
finishes with `git diff --check`. Each stage prints its own `[CHECK]`, `[PASS]`,
or `[FAIL]` label so a failure identifies the specific gate. Use the narrower
command printed for a stage when iterating on a failure.

This deterministic suite proves repository contracts and fixture behavior; it
does not prove that the current authenticated upstream and image CDN are
usable. Before an upstream-facing release, start the candidate daemon with a
read-only live session and run `npm --prefix pandora-web run test:live`. The
acceptance model and non-substitution rules are documented in
[testing and usability acceptance](docs/development/testing.md).

When exercising the daemon directly from a development checkout, keep the same
canonical diagnostic order as the installed CLI:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
```

The repeatable internal artifact and rollback procedure is documented in
[`docs/development/release-process.md`](docs/development/release-process.md).

## API Reference

Start from the [`docs/` index](docs/README.md). Provider contracts, the daemon REST API, CLI surface, and built-in adapter developer reference live in [`docs/api_reference.md`](docs/api_reference.md). Deployment and agent/CLI operations are documented in [`docs/deployment.md`](docs/deployment.md) and [`docs/agent/README.md`](docs/agent/README.md). Hermes-specific packaging guidance lives in [`docs/hermes_integration.md`](docs/hermes_integration.md).

## License

Private project.
