# Failure Recovery Workflow

Use this workflow to classify machine-mode failures without bypassing the daemon.

## Machine Error Envelope

```json
{"ok": false, "error": {"code": "connect_error", "message": "Cannot connect to daemon at http://127.0.0.1:7860"}}
```

Preserve `error.code` and `error.message` when reporting failures.

## `connect_error`

Meaning: CLI cannot reach the daemon.

Actions:

- Confirm the daemon URL.
- Start the daemon if permitted: `uv run python -m pandora_daemon`.
- Retry `health --json`.
- Do not inspect credential files.

## `usage_error` Or `invalid_gallery_target`

Meaning: command syntax or gallery target is invalid.

Actions:

- Re-check whether the user supplied a full gallery URL or `gid token` pair.
- Use examples from [`gallery-inspection.md`](gallery-inspection.md) or [`download.md`](download.md).

## `websocket_dependency_missing`

Meaning: the CLI cannot import `websockets` for NDJSON download watch commands.

Actions:

- Report the error.
- Do not switch to human-output parsing.
- If dependency installation is in scope, use repository `uv` workflows only.

## `websocket_error`

Meaning: WebSocket connection or stream failed.

Actions:

- Check daemon health.
- Inspect current queue with `download list --json`.
- If watching a specific task, inspect `download pages <gid> --json`.

## Stale Or Unloaded Tag Database

Actions:

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
```

Do not auto-rewrite translated text without suggestions and candidate choice.

## Download Paused Or Auth Failed

Terminal events:

- `download_paused`
- `download_auth_failed`

Actions:

- Treat the watcher as terminal for the current automation step.
- Report `reason` or `error`.
- Inspect `download pages <gid> --json` if useful.
- Resume only a task whose public status is `paused`. The daemon reconciles
  existing page files and clears the old error before queueing it.
- `download_auth_failed` leaves the failing task in `failed`; it is not a
  separate `auth_failed` task status.
- Do not read, print, or modify credentials unless the user explicitly asks for config work.

## Completed With Errors

Actions:

- Inspect failed pages: `uv run python -m pandora_daemon.cli download pages <gid> --json`.
- If the user wants recovery, run `uv run python -m pandora_daemon.cli download retry <gid> --json`.
- Retry reconciles disk first, so restored pages are retained and stale failure
  lists are not treated as authoritative.
- Do not maintain a separate failed-page list outside the daemon.
