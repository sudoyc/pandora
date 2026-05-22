---
name: pandora
description: Use when operating or modifying Pandora via agents: daemon lifecycle, CLI JSON/NDJSON workflows, download state handling, and repository verification.
version: 1.0.0
author: Pandora maintainers
license: MIT
compatibility: Pandora repository root with uv, git, optional npm/cargo.
metadata:
  hermes:
    tags: [pandora, cli, daemon, agent-workflow, downloads]
    related_skills: [github-pr-workflow, test-driven-development]
allowed-tools: Bash(uv:*), Bash(git:*), Bash(cargo:*), Bash(npm:*)
---

# Pandora Agent Skill

## Overview

Pandora is a local ExHentai/E-Hentai browser and downloader with a daemon-first, CLI/Hermes-friendly architecture. This skill is for agents that need to inspect, operate, test, or extend Pandora without relying on a human clicking through a UI.

Priority for agent work:

1. Prefer daemon REST/CLI workflows with JSON or NDJSON output.
2. Keep `exhentai_api` stateless.
3. Treat Hermes skills/plugins as thin wrappers around daemon REST or CLI JSON/NDJSON.
4. Keep frontends thin: they call daemon REST + WebSocket only.
5. Do not bypass the daemon from CLI/Web or any future plugin.
6. Treat `pandora-tui/` as archived/frozen; do not improve it.

## Architecture Contract

```text
exhentai_api (stateless Python library)
        -> pandora-daemon (FastAPI + SQLite + cache + downloads)
        -> consumers (Python CLI, Hermes skill/plugin, optional React web)
```

Layer rules:

- `exhentai_api`: HTTP requests, HTML parsing, models. No config, cache, DB, UI, or local state.
- `pandora-daemon`: credentials, session, cache, SQLite DB, downloads, local library, config.
- Consumers/agents: render or automate user actions by calling daemon REST/WS/CLI.
- `pandora-tui/`: archived historical REST/WS consumer reference only.
- Web/TUI/client-cache work is not the bot-first path; defer it unless explicitly requested.

## Starting and Verifying the Daemon

From repository root:

```bash
uv run python -m pandora_daemon
```

Default daemon base URL:

```text
http://127.0.0.1:7860
```

Basic health-style checks for agents:

- `health --json` is a minimal capability probe; it intentionally omits credentials and local filesystem paths.
- `config --json` returns local-agent-safe runtime config: credentials are omitted and proxy secrets are redacted, but local non-secret paths may appear.
- Credentials may include optional `ipb_pass_hash`; leave it unset when the current session does not require it.

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli status --json
```

If the CLI reports it cannot connect, start the daemon first or pass:

```bash
--daemon-url http://127.0.0.1:7860
```

Deployment details, readiness checks, systemd examples, and smoke tests live in `docs/deployment.md`.

## CLI Commands for Agents

Use JSON/NDJSON when scripting or delegating.

When `--json` or `--ndjson` is set and a command fails, the CLI emits a stable machine-facing envelope:

```json
{"ok": false, "error": {"code": "connect_error", "message": "Cannot connect to daemon at http://127.0.0.1:7860"}}
```

Current tested error codes:

- `connect_error`
- `http_error`
- `invalid_gallery_target`
- `usage_error`
- `websocket_error`
- `websocket_dependency_missing`

Browse/read-only commands:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli search "keyword" --page 0 --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
uv run python -m pandora_daemon.cli popular --json
uv run python -m pandora_daemon.cli toplist --tl 15 --json
uv run python -m pandora_daemon.cli watched --page 0 --json
uv run python -m pandora_daemon.cli gallery "https://exhentai.org/g/123/abcdef0123/" --json
uv run python -m pandora_daemon.cli gallery 123 abcdef0123 --json
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json
uv run python -m pandora_daemon.cli tags suggest "artist" --json
uv run python -m pandora_daemon.cli library list --json
uv run python -m pandora_daemon.cli favorites list --json   # all favorites (`slot=-1`)
```

Download commands:

```bash
uv run python -m pandora_daemon.cli download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
uv run python -m pandora_daemon.cli download run 123 abcdef0123 --ndjson
uv run python -m pandora_daemon.cli download add "https://exhentai.org/g/123/abcdef0123/" --json
uv run python -m pandora_daemon.cli download add 123 abcdef0123 --json
uv run python -m pandora_daemon.cli download list --json
uv run python -m pandora_daemon.cli download watch 123 --ndjson
uv run python -m pandora_daemon.cli download pages 123 --json
uv run python -m pandora_daemon.cli download cancel 123 --json
uv run python -m pandora_daemon.cli download resume 123 --json
uv run python -m pandora_daemon.cli download retry 123 --json
```

Prefer `download run --ndjson` for bots. It attaches to WebSocket before submitting `/api/downloads`, emits `download_submitted`, then watches events until a terminal event. If the daemon returns HTTP 409 for an already-active duplicate task, `run` emits `download_already_queued` and continues watching instead of failing. Use `download add` + `download watch` only when split control is intentional; a watcher attached later can miss early events.

Machine output safety:

- `gallery` CLI output redacts `api_uid` and `api_key` by default.
- `download pages --json` maps internal page state `done` to public state `completed`.

Search/tag scheme A:

- The CLI and daemon expose primitive interfaces only; they do not automatically rewrite Chinese or other translated text into ExHentai tag queries.
- Agent flow: `tags status --json`, `tags refresh --json` if stale or unloaded, `tags suggest "丝袜" --json`, choose a candidate such as `female:stockings`, then `search "female:stockings" --search-tags --json`.
- Advanced search flags include `--category INT`, `--min-rating INT`, `--search-name`, `--search-tags`, `--search-description`, `--search-torrent`, `--search-low-power-tags`, `--disable-language-filter`, `--show-expunged`, `--min-pages INT`, and `--max-pages INT`.
- `--category` is a Pandora include bitmask; the daemon converts it to ExHentai's exclude bitmask upstream.

Legacy human-friendly aliases remain available:

```bash
pandora download <url>
pandora dl <url>
pandora status
```

## Download Event Contract

WebSocket path:

```text
WS /ws
```

Daemon event discriminator is `event`, not `type`.

Terminal download events:

```json
{"event":"download_complete","gid":"123","path":"..."}
{"event":"download_complete_with_errors","gid":"123","failed_pages":[7]}
{"event":"download_error","gid":"123","error":"..."}
{"event":"download_cancelled","gid":"123"}
{"event":"download_paused","gid":"123","reason":"image_limit"}
{"event":"download_auth_failed","gid":"123","error":"..."}
```

CLI watcher exit semantics:

- `download_complete`: exit 0
- `download_complete_with_errors`: exit 1
- `download_error`: exit 1
- `download_cancelled`: exit 1
- `download_paused`: exit 1
- `download_auth_failed`: exit 1

## Download State Rules

Preserve these invariants when changing `pandora_daemon/download.py`:

- Concurrent duplicate submits for the same active `gid` must be rejected.
- A queued task becomes `downloading` before actual gallery work begins.
- State writes should be atomic (`.tmp` + replace), not partial direct writes.
- Persisted `page_states` JSON keys must load back as integer page numbers.
- Existing page files on disk count as completed during resume/retry.
- `completed_with_errors`, `paused`, `failed`, and `cancelled` are terminal from an agent watcher perspective.

## Verification Commands

Before committing daemon/CLI/agent changes:

```bash
uv run python -m pytest tests/pandora_daemon/test_cli.py -q
uv run python -m pytest tests/pandora_daemon/test_routes_config.py tests/pandora_daemon/test_agent_contracts.py -q
uv run python -m pytest tests/pandora_daemon/test_download.py tests/pandora_daemon/test_download_concurrency.py -q
uv run python -m pytest -q
git diff --check
```

Do not change `pandora-tui/` for normal agent work. It is archived/frozen and excluded from default verification.

If Web changed, defer unless the current task explicitly includes Web; when included, verify:

```bash
cd pandora-web && npm run lint && npm run build
```

## Git Hygiene

- Stage explicit files only; never blindly `git add .`.
- Keep Web WIP out of CLI/agent commits unless requested.
- Do not commit generated outputs: `node_modules`, `dist`, downloaded galleries, caches, binaries.
- Do not commit local credentials or `~/.config/pandora/config.toml`.

## Common Pitfalls

1. Wrong WS discriminator: daemon sends `event`, not `type`.
2. Treating `download_paused` as non-terminal leaves CLI/agents hanging.
3. JSON persistence turns dict keys into strings; convert `page_states` keys back to `int` on load.
4. Existing page files must update progress counters, or resumed downloads under-report completion.
5. Web work is not the default priority for agent automation; prefer CLI/daemon/Hermes first.
6. TUI work is not active; preserve it only as archived reference unless explicitly instructed otherwise.
7. On Arch/PEP-668 environments use `uv`; do not install dependencies with global `pip`.

## Verification Checklist

- [ ] Daemon/CLI behavior has regression tests when changed.
- [ ] `uv run python -m pytest -q` passes.
- [ ] `git diff --check` passes.
- [ ] Commit contains only the intended CLI/daemon/agent files.
- [ ] Commit message lists each meaningful behavior change.
