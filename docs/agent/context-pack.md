# Pandora Agent Context Pack

Use these blocks as copy-pasteable context for any automation agent. Add narrower snippets from [`snippets/`](snippets/) when the task needs a specialized role.

## Base Context

```text
You are operating Pandora, a local ExHentai/E-Hentai browser and downloader.

Pandora's durable state belongs only to pandora-daemon: credentials, session, cache, SQLite data, bookmarks, filters, download queue, and local library. Do not create or persist a second state layer.

Use only daemon-backed integration surfaces: CLI JSON/NDJSON, daemon REST, and daemon WebSocket. From a checkout, prefer commands like `uv run python -m pandora_daemon.cli health --json`. If Pandora is installed, `pandora health --json` is equivalent.

Do not import `exhentai_api` for user workflows, scrape ExHentai directly, parse human CLI output when machine output exists, or copy credentials into prompts/logs/plugin state.

For translated tag search, use Scheme A: check tag DB status, refresh if stale or unloaded, ask for suggestions, choose a candidate with evidence, then search the selected ExHentai tag syntax with `--search-tags`. Do not auto-rewrite translated text into a tag query.
```

## Readiness Context

```text
Before work, verify daemon readiness with:
`uv run python -m pandora_daemon.cli health --json`
`uv run python -m pandora_daemon.cli config --json`
`uv run python -m pandora_daemon.cli status --json`
For search/tag tasks, also run:
`uv run python -m pandora_daemon.cli tags status --json`

If the daemon is unreachable, report the machine error and start or request startup according to the host agent's permissions. Do not read or expose credential files.
```

## Download Context

```text
For downloads, prefer `uv run python -m pandora_daemon.cli download run <url|gid> [token] --ndjson`. It connects to WebSocket before submitting, emits `download_submitted` or `download_already_queued`, then watches terminal events.

Treat these terminal events as completion for the current automation step:
success: `download_complete` exits 0.
failure/non-success: `download_complete_with_errors`, `download_error`, `download_cancelled`, `download_paused`, and `download_auth_failed` exit 1.

Inspect follow-up state with `download pages <gid> --json`, `download list --json`, and `library list --json`.
```

## State Boundary Context

```text
Pandora agents are consumers, not state owners. Never persist credentials, sessions, cache indexes, bookmarks, filters, library metadata, or download task state outside pandora-daemon. Thin plugins may cache only ephemeral command results needed for the current response.
```
