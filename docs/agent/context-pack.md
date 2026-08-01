# Pandora Agent Context Pack

Use these blocks as copy-pasteable context for any automation agent. Add narrower snippets from [`snippets/`](snippets/) when the task needs a specialized role.

## Base Context

```text
You are operating Pandora, a local gallery browser and downloader through a selected provider adapter.

Pandora's durable state belongs only to pandora-daemon: credentials, session, cache, SQLite data, bookmarks, filters, download queue, and local library. Do not create or persist a second state layer.

Use only daemon-backed integration surfaces: CLI JSON/NDJSON, daemon REST, and daemon WebSocket. From a checkout, prefer commands like `uv run python -m pandora_daemon.cli health --json`. If Pandora is installed, `pandora health --json` is equivalent.

Do not import provider adapters for user workflows, access an upstream directly, parse human CLI output when machine output exists, or copy credentials into prompts/logs/plugin state.

For translated tag search, use Scheme A: check tag DB status, refresh if stale or unloaded, ask for suggestions, choose a candidate with evidence, then search the selected ExHentai tag syntax with `--search-tags`. Do not auto-rewrite translated text into a tag query.
```

## Readiness Context

```text
Before work, verify daemon readiness with:
`uv run python -m pandora_daemon.cli health --json`
`uv run python -m pandora_daemon.cli config --json`
`uv run python -m pandora_daemon.cli readiness --json`
`uv run python -m pandora_daemon.cli status --json`
For search/tag tasks, also run:
`uv run python -m pandora_daemon.cli tags status --json`

Run those four commands in order. `readiness --json` exit 1 is a structured
upstream not-ready result; `connect_error` means the daemon is unreachable. Do
not read or expose credential files.
```

## Download Context

```text
For downloads, prefer `uv run python -m pandora_daemon.cli download run <url|gid> [token] --ndjson`. It connects to WebSocket before submitting, emits `download_submitted` or `download_already_queued`, then watches terminal events.

Treat these terminal events as completion for the current automation step:
success: `download_complete` exits 0.
failure/non-success: `download_complete_with_errors`, `download_error`, `download_cancelled`, `download_paused`, and `download_auth_failed` exit 1.

Inspect follow-up state with `download pages <gid> --json`, `download list --json`, `download report --json`, and `library list --json`. The consistency report is read-only; use its issue codes instead of scanning daemon files. When the user requests recovery, preview `download repair <gid> --json` or `download forget <gid> --json`, inspect `actions`, then repeat with `--apply`. Recovery never deletes library files.
```

## Bug Fix Context

```text
When a deployed bot or agent shows a bug, triage the failing layer first, then add a regression test before changing the implementation. Prefer the narrowest reproducible command in CLI or daemon form, and validate the real bot/deployment path after local checks.
```

## State Boundary Context

```text
Pandora agents are consumers, not state owners. Never persist credentials, sessions, cache indexes, bookmarks, filters, library metadata, or download task state outside pandora-daemon. Thin plugins may cache only ephemeral command results needed for the current response.
```
