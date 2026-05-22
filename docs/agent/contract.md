# Agent Contract

This document describes the stable machine-facing Pandora contracts used by the Pandora Agent Pack.

## Surfaces

Agents may use:

- CLI JSON: `uv run python -m pandora_daemon.cli <command> --json`.
- CLI NDJSON: `uv run python -m pandora_daemon.cli download run ... --ndjson` and `download watch ... --ndjson`.
- REST: `http://127.0.0.1:7860/api/...`.
- WebSocket: `WS /ws`.

Installed CLI examples may use `pandora ...`; checkout examples use `uv run python -m pandora_daemon.cli ...`.

## Readiness Probes

```bash
uv run python -m pandora_daemon.cli health --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

- `health --json` is the minimal safe capability probe.
- `config --json` omits credentials and redacts proxy secrets, but local non-secret paths may appear.
- `status --json` returns the download queue state.
- `tags status --json` reports the EhTagTranslation cache state for search agents.

## CLI Error Envelope

When `--json` or `--ndjson` is active, CLI failures use this envelope:

```json
{"ok": false, "error": {"code": "connect_error", "message": "Cannot connect to daemon at http://127.0.0.1:7860"}}
```

Known error codes:

- `connect_error`
- `http_error`
- `invalid_gallery_target`
- `usage_error`
- `websocket_error`
- `websocket_dependency_missing`

Schema: [`schemas/cli-error-envelope.schema.json`](schemas/cli-error-envelope.schema.json).

## Search Response Shape

Search, homepage, popular, watched, and other gallery-list-style responses are arrays of gallery list items. This schema is for gallery-list arrays only; it is not the schema for every REST response that may contain gallery data, such as library status or wrapper objects. Stable list-item fields include:

- `gid`
- `token`
- `title`
- `category`
- `uploader`
- `thumb_url`
- `posted`
- `rating`
- `pages`
- `rated`
- `thumb_width`
- `thumb_height`
- `url`

Schema: [`schemas/search-response.schema.json`](schemas/search-response.schema.json).

## Gallery Inspection

```bash
uv run python -m pandora_daemon.cli gallery "https://exhentai.org/g/123/abcdef0123/" --json
uv run python -m pandora_daemon.cli gallery 123 abcdef0123 --json
```

CLI gallery output redacts daemon-only `api_uid` and `api_key` by default. REST detail responses may contain daemon-internal fields required by daemon routes; agents should not persist or expose them.

## Download Events

WebSocket path:

```text
WS /ws
```

The daemon event discriminator is `event`, not `type`.

Common events:

```json
{"event":"download_queued","gid":"123","title":"..."}
{"event":"download_progress","gid":"123","phase":"pages","page":5,"total":20}
{"event":"download_complete","gid":"123","path":"/path/to/gallery"}
{"event":"download_complete_with_errors","gid":"123","failed_pages":[7]}
{"event":"download_error","gid":"123","error":"..."}
{"event":"download_cancelled","gid":"123"}
{"event":"download_paused","gid":"123","reason":"image_limit"}
{"event":"download_auth_failed","gid":"123","error":"..."}
```

CLI `download run --ndjson` also emits:

```json
{"event":"download_submitted","gid":"123","status":"queued","title":"..."}
{"event":"download_already_queued","gid":"123","status":"already_queued","detail":"..."}
```

Terminal watcher exit semantics:

- `download_complete`: exit 0.
- `download_complete_with_errors`: exit 1.
- `download_error`: exit 1.
- `download_cancelled`: exit 1.
- `download_paused`: exit 1.
- `download_auth_failed`: exit 1.

Schema: [`schemas/download-event.schema.json`](schemas/download-event.schema.json).

## Download Pages

```bash
uv run python -m pandora_daemon.cli download pages 123 --json
```

Public page state values include `completed` and `failed`. The CLI maps internal daemon state `done` to public state `completed`.

## Tag Search Contract

Pandora uses Scheme A for translated tags. The daemon and CLI expose primitives only; agents choose candidates.

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

Do not replace this with `search "丝袜" --search-tags` unless the user explicitly wants a literal untranslated tag query.
