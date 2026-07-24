---
name: pandora
description: "Use when operating or modifying Pandora via agents: daemon lifecycle, CLI JSON/NDJSON workflows, download state handling, and repository verification."
version: 1.0.0
author: Pandora maintainers
license: MIT
compatibility: Pandora repository root with uv, git, optional npm/cargo.
metadata:
  hermes:
    tags: [pandora, cli, daemon, agent-workflow, downloads]
    related_skills: [github-pr-workflow, test-driven-development]
allowed-tools: "Bash(uv:*), Bash(git:*), Bash(cargo:*), Bash(npm:*)"
---

# Pandora Agent Skill

## Overview

Pandora is a local ExHentai/E-Hentai browser and downloader with a daemon-first, Agent Pack-friendly architecture. This skill is for agents that need to inspect, operate, test, or extend Pandora without relying on a human clicking through a UI.

The canonical generic agent documentation is the Pandora Agent Pack under `docs/agent/`. This Hermes skill is one packaged consumer of that Agent Pack, not the source of truth and not a state layer. There is no separate Hermes plugin or toolset package to import today; use the `pandora` CLI entrypoint from `pyproject.toml` or the daemon REST/WebSocket contract directly.

Agent Pack references:

- `docs/agent/README.md` — overview and workflow index.
- `docs/agent/context-pack.md` — copy-pasteable base context blocks.
- `docs/agent/contract.md` — CLI/REST/WebSocket machine contract.
- `docs/agent/safety.md` — credential, privacy, mutation, and state boundaries.
- `docs/agent/workflows/` — bootstrap, search, tag resolution, gallery inspection, downloads, library, failure recovery.
- `docs/agent/snippets/` — standalone prompt snippets for different agent roles.
- `docs/agent/schemas/` — lightweight JSON Schemas for common machine envelopes.

Long-running repository development references:

- `docs/development/unattended-development.md` — autonomy boundaries, checkpoints, verification, Git, and stop rules.
- `docs/development/work-program.md` — executable work packages, dependencies, current state, and completion evidence.
- `docs/development/goal-prompt.md` — copy-pasteable persistent goal prompt for completing the program.

Priority for agent work:

1. Prefer daemon REST/CLI workflows with JSON or NDJSON output.
2. Keep `exhentai_api` stateless.
3. Treat Hermes skills/plugins as thin wrappers around the generic Agent Pack, daemon REST, or CLI JSON/NDJSON.
4. Keep frontends thin: they call daemon REST + WebSocket only.
5. Do not bypass the daemon from CLI/Web or any future plugin.
6. Treat `pandora-tui/` as archived/frozen; do not improve it.

## Architecture Contract

```text
exhentai_api (stateless Python library)
        -> pandora-daemon (FastAPI + SQLite + cache + downloads)
        -> consumers (Python CLI, Agent Pack, Hermes skill/plugin, optional React web)
```

Layer rules:

- `exhentai_api`: HTTP requests, HTML parsing, models. No config, cache, DB, UI, or local state.
- `pandora-daemon`: credentials, session, cache, SQLite DB, downloads, local library, config.
- Consumers/agents: render or automate user actions by calling daemon REST/WS/CLI.
- `pandora-tui/`: archived historical REST/WS consumer reference only.
- Web/TUI/client-cache work is not the bot-first path; defer it unless explicitly requested.

Future Hermes plugin/toolset boundary:

- Wrap `pandora` CLI JSON/NDJSON commands or daemon REST/WebSocket endpoints only, following `docs/agent/`.
- Do not import `exhentai_api` from Hermes code for auth, browse, search, cache, or downloads.
- Do not create a second stateful layer for credentials, sessions, cache, queue, bookmarks, or library state.
- Keep ambiguous decisions in the agent. Pandora exposes primitives and stable machine output.

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

Hermes session bootstrap, based on `docs/agent/workflows/bootstrap.md`:

1. Confirm the repository root and use `uv`; do not use global `pip`.
2. Start the daemon if it is not already running: `uv run python -m pandora_daemon`.
3. Probe readiness with `health --json`, `config --json`, and `status --json`.
4. For search agents, also run `tags status --json` before translated-tag workflows.
5. Omit `--daemon-url` when the daemon is on the default URL; pass the actual daemon URL only when it is non-default.

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

Upstream REST failures use the sanitized shape
`{"error":"session","detail":"Upstream session is invalid"}`. Stable core
classifications are `auth`, `session`, `upstream`, `parse`, and `network`; branch
on `error`, not `detail`. Full semantics and the schema live in
`docs/agent/contract.md`.

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
uv run python -m pandora_daemon.cli library export-pdf 123 --password "PDF_PASSWORD" --json
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

Copy-pasteable scheme A example:

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json   # if stale or unloaded
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

Do not collapse this into `search "丝袜" --search-tags`; that would be an untranslated literal tag query, not automatic translated-tag resolution.

Legacy human-friendly aliases remain available:

```bash
pandora download <url>
pandora dl <url>
pandora status
```

## Download Event Contract

The full generic contract lives in `docs/agent/contract.md` and `docs/agent/schemas/download-event.schema.json`.

WebSocket path:

```text
WS /ws
```

Daemon event discriminator is `event`, not `type`.

Terminal download events:

```json
{"event":"download_complete","gid":"123"}
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

Library PDF export hook summary:

- CLI entry: `library export-pdf <gid> --password "PDF_PASSWORD" --json`
- REST entry: `POST /api/library/{gid}/export/pdf`
- Hook events: `pdf_export_started`, `pdf_export_complete`, `pdf_export_error`
- `pdf_export_complete` is the success signal for bots.
- Password handling and full hook contract live in `docs/agent/contract.md` and `docs/agent/workflows/library.md`.

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
5. Web work is not the default priority for agent automation; prefer CLI/daemon/Agent Pack workflows first.
6. TUI work is not active; preserve it only as archived reference unless explicitly instructed otherwise.
7. On Arch/PEP-668 environments use `uv`; do not install dependencies with global `pip`.

## Verification Checklist

- [ ] Daemon/CLI behavior has regression tests when changed.
- [ ] `uv run python -m pytest -q` passes.
- [ ] `git diff --check` passes.
- [ ] Commit contains only the intended CLI/daemon/agent files.
- [ ] Commit message lists each meaningful behavior change.
