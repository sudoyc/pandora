# Pandora Hermes Integration

Pandora is Hermes-ready through the repo-shipped skill at `.agents/skills/pandora/SKILL.md` and the daemon-backed `pandora` CLI. This document defines the boundary for current agent use and future thin plugin/toolset work.

## Integration Shape

Use skill/docs first. There is no in-repo Hermes plugin or toolset package today, and none is required for the current contract.

Allowed integration surfaces:

- `pandora` CLI commands with `--json` or `--ndjson`.
- `pandora_daemon.cli` via `uv run python -m pandora_daemon.cli ...` from a checkout.
- Daemon REST endpoints under `http://127.0.0.1:7860/api/...`.
- Daemon WebSocket events from `WS /ws`.

Forbidden integration surfaces:

- Direct Hermes calls into `exhentai_api` for user workflows.
- A second credential, session, cache, bookmark, library, or download state store.
- Automatic translated-tag resolution inside Pandora or a wrapper.
- Parsing human-oriented CLI output when JSON/NDJSON is available.

Future Hermes plugin/toolset code, if added, should be a thin wrapper around the allowed surfaces. It may package command invocation and JSON parsing, but business logic and ambiguous decisions stay in the agent.

## Daemon Lifecycle

Start the daemon from the repository root:

```bash
uv run python -m pandora_daemon
```

Default base URL:

```text
http://127.0.0.1:7860
```

Readiness checks:

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

`health --json` is the minimal safe probe. `config --json` omits credentials and redacts proxy secrets, but local non-secret paths may appear.

## Machine-Mode Failures

When `--json` or `--ndjson` is set, CLI failures use a stable envelope:

```json
{"ok": false, "error": {"code": "connect_error", "message": "Cannot connect to daemon at http://127.0.0.1:7860"}}
```

Known error codes include `connect_error`, `http_error`, `invalid_gallery_target`, `usage_error`, `websocket_error`, and `websocket_dependency_missing`.

## Scheme A Search

Pandora deliberately exposes primitive tag operations. It does not automatically rewrite Chinese or other translated text into ExHentai tag syntax.

Agent flow:

1. Check tag database status.
2. Refresh the tag database if stale or unloaded.
3. Ask for suggestions using translated or original text.
4. Let the agent choose a candidate.
5. Search with the selected ExHentai tag syntax.

Copy-pasteable example:

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json   # if stale or unloaded
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

Do not replace this with `search "丝袜" --search-tags` unless the user explicitly wants a literal tag query.

## Download Orchestration

Prefer `download run --ndjson` for Hermes. It attaches to WebSocket first, submits the download, emits `download_submitted` or `download_already_queued`, then watches until a terminal event.

```bash
uv run python -m pandora_daemon.cli download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
```

Follow-up inspection:

```bash
uv run python -m pandora_daemon.cli download list --json
uv run python -m pandora_daemon.cli download pages 123 --json
uv run python -m pandora_daemon.cli library list --json
```

Terminal watcher events:

- `download_complete` exits 0.
- `download_complete_with_errors` exits 1.
- `download_error` exits 1.
- `download_cancelled` exits 1.
- `download_paused` exits 1.
- `download_auth_failed` exits 1.

Daemon WebSocket events use `event` as the discriminator, not `type`.

## Contract Safety

- `gallery --json` redacts `api_uid` and `api_key`.
- `download pages --json` reports public page state `completed` instead of the internal `done` value.
- `search --category` is a Pandora include bitmask; the daemon converts it upstream.
- Credentials live in `~/.config/pandora/config.toml` and must not be copied into prompts, logs, docs, or plugin state.
