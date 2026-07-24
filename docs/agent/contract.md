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
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli config --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

- `health --json` is the minimal safe capability probe.
- `readiness --json` runs read-only authenticated probes for homepage, search,
  popular, and home without returning upstream content.
- `config --json` omits credentials and redacts proxy secrets, but local non-secret paths may appear.
- `status --json` returns the download queue state.
- `tags status --json` reports the EhTagTranslation cache state for search agents.

`GET /api/readiness` returns HTTP 200 for every recognized diagnostic result so
clients can always parse the same response schema. Without complete credentials,
it returns `ready: false`, `session: "not_configured"`, and `not_checked` for all
four checks without contacting upstream. Check values are `ok`, `auth`,
`session`, `upstream`, `parse`, or `network`; `session` summarizes authentication
as `not_configured`, `valid`, `invalid`, or `unknown`.

`ready` is true only when all four checks are `ok`. Any `auth` or `session`
result makes the session `invalid`; otherwise, at least one `ok` result makes it
`valid`, while only transport/upstream/parser failures leave it `unknown`.

CLI `readiness --json` prints that response unchanged. A fully ready result exits
with exit 0; every not-ready result exits with exit 1. Daemon connection and HTTP
failures still use the standard CLI error envelope. Schema:
[`schemas/readiness-response.schema.json`](schemas/readiness-response.schema.json).

## Upstream REST Error Classification

Daemon routes use a stable, sanitized envelope for upstream failures:

```json
{"error":"session","detail":"Upstream session is invalid"}
```

Core classifications:

- `auth`: required authentication configuration is absent or rejected.
- `session`: the configured session is invalid or expired.
- `upstream`: the upstream service or endpoint returned an unexpected HTTP status.
- `parse`: the upstream HTML or JSON response could not be parsed.
- `network`: the upstream transport failed.

A successful empty list is not an error category. Consumers must branch on
`error`, not on the human-readable `detail`. The daemon does not include
exception text, raw upstream responses, cookies, proxy credentials, or upstream
status details in this envelope or its request-error logs.

Schema: [`schemas/upstream-error.schema.json`](schemas/upstream-error.schema.json).

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

CLI gallery output redacts daemon-only `api_uid` and `api_key` by default. Treat gallery detail as a user-facing metadata surface plus route identifiers. Daemon-internal helper fields such as `api_uid`, `api_key`, `viewer_urls`, `thumb_urls`, and `thumb_sprites` are internal-only and not part of the public stable contract.

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
{"event":"download_complete","gid":"123"}
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

Download status/detail surfaces are public machine interfaces for download state, not daemon-local bookkeeping. Fields such as `token` and daemon-local output directory/path values are internal-only and not part of the public stable contract.

## Library PDF Export

```bash
uv run python -m pandora_daemon.cli library export-pdf 123 --password "PDF_PASSWORD" --json
```

REST:

```text
POST /api/library/{gid}/export/pdf
```

Request body fields:

- `password` — optional PDF open password.
- `output_name` — optional filename ending in `.pdf`.
- `include_cover` — optional boolean to prepend cover as page 1 when present.

Export hook events on `WS /ws`:

```json
{"event":"pdf_export_started","gid":"123"}
{"event":"pdf_export_complete","gid":"123","path":"/path/to/file.pdf","password_protected":true}
{"event":"pdf_export_error","gid":"123","error":"..."}
```

Bot success criteria:

- CLI/REST response includes `ok: true`, `format: "pdf"`, `path`, and `password_protected`.
- `pdf_export_complete` means export finished successfully.
- Never echo or log the password in prompts, events, JSON output, or docs.

Schema: [`schemas/pdf-export-event.schema.json`](schemas/pdf-export-event.schema.json).

## Tag Search Contract

Pandora uses Scheme A for translated tags. The daemon and CLI expose primitives only; agents choose candidates.

```bash
uv run python -m pandora_daemon.cli tags status --json
uv run python -m pandora_daemon.cli tags refresh --json
uv run python -m pandora_daemon.cli tags suggest "丝袜" --json
uv run python -m pandora_daemon.cli search "female:stockings" --search-tags --json
```

Do not replace this with `search "丝袜" --search-tags` unless the user explicitly wants a literal untranslated tag query.
