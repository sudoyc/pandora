# Download Workflow

Use this workflow for daemon-backed gallery downloads. The daemon owns the queue and persisted page state.

## Preferred Bot Path

```bash
uv run python -m pandora_daemon.cli download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
```

With `gid token`:

```bash
uv run python -m pandora_daemon.cli download run 123 abcdef0123 --ndjson
```

Installed equivalent:

```bash
pandora download run "https://exhentai.org/g/123/abcdef0123/" --ndjson
```

`download run --ndjson` connects to WebSocket first, submits `/api/downloads`, emits `download_submitted` or `download_already_queued`, then watches terminal events. Prefer it over `download add` plus `download watch` because a late watcher can miss early events.

## Split Control Path

Use this only when the agent intentionally wants separate submit and watch steps:

```bash
uv run python -m pandora_daemon.cli download add "https://exhentai.org/g/123/abcdef0123/" --json
uv run python -m pandora_daemon.cli download watch 123 --ndjson
```

## Terminal Events

- `download_complete`: success, watcher exits 0.
- `download_complete_with_errors`: terminal non-success, watcher exits 1.
- `download_error`: terminal non-success, watcher exits 1.
- `download_cancelled`: terminal non-success, watcher exits 1.
- `download_paused`: terminal non-success, watcher exits 1.
- `download_auth_failed`: terminal non-success, watcher exits 1.

The event discriminator is `event`, not `type`.

## Follow-Up Inspection

```bash
uv run python -m pandora_daemon.cli download list --json
uv run python -m pandora_daemon.cli download pages 123 --json
uv run python -m pandora_daemon.cli library list --json
```

`download pages --json` reports public page states such as `completed`; internal daemon state may use `done`.

## Recovery Commands

Use only when appropriate for the user request and current task state:

```bash
uv run python -m pandora_daemon.cli download cancel 123 --json
uv run python -m pandora_daemon.cli download resume 123 --json
uv run python -m pandora_daemon.cli download retry 123 --json
```

Do not implement a separate retry database or queue in an agent. The daemon owns retry/resume state.
