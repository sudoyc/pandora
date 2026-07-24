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
uv run python -m pandora_daemon.cli readiness --json
uv run python -m pandora_daemon.cli status --json
uv run python -m pandora_daemon.cli tags status --json
```

- `health --json` is the minimal safe capability probe.
- `config --json` omits credentials and redacts proxy secrets, but local non-secret paths may appear.
- `readiness --json` runs read-only authenticated probes for homepage, search,
  popular, and home without returning upstream content.
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

## Download Consistency Report

```bash
uv run python -m pandora_daemon.cli download report --json
```

REST:

```text
GET /api/downloads/report
```

The report compares the daemon's loaded task registry with `download.path`
without modifying either. Its consistency rules are:

- Only `completed` and `completed_with_errors` tasks require complete artifacts.
- A required task directory that is absent or outside the current `download.path` library root is `orphan_task`; metadata/page checks are not cascaded for that directory.
- An existing required directory must contain readable object metadata whose `gid` matches the task. Absence is `missing_metadata`; unreadable or mismatched metadata is `invalid_metadata`.
- Required page numbers are `1..total_pages`; absent files produce `missing_pages`.
- A directory with readable metadata whose `gid` has no task is `unregistered_library`.

```json
{
  "consistent": false,
  "summary": {
    "registered_tasks": 2,
    "terminal_tasks": 1,
    "library_entries": 1,
    "affected_galleries": 1,
    "issue_count": 1
  },
  "issues": [
    {
      "code": "missing_pages",
      "gid": "123",
      "task_status": "completed",
      "expected_pages": 3,
      "present_pages": 2,
      "missing_pages": [2]
    }
  ]
}
```

The report omits task tokens and local paths. Retrieving `consistent: false` is
a successful read and exits 0; machine transport or HTTP failures retain their
normal nonzero error semantics.

## Download State Recovery

Preview first:

```bash
uv run python -m pandora_daemon.cli download repair 123 --json
uv run python -m pandora_daemon.cli download forget 123 --json
```

Apply only after inspecting `actions`:

```bash
uv run python -m pandora_daemon.cli download repair 123 --apply --json
uv run python -m pandora_daemon.cli download forget 123 --apply --json
```

REST:

```text
POST /api/downloads/{gid}/repair  {"apply": false}
POST /api/downloads/{gid}/forget  {"apply": false}
```

Both operations default to preview. `apply: true` is the only mode that changes
`downloads.json`.

- `repair` registers one unregistered library entry as a completed task only when metadata identifies the requested `gid`, `pages` is valid, every expected page file exists, and the entry is unique.
- `forget` removes one inactive task registration. `queued` and `downloading` tasks return HTTP 409 instead.
- Neither operation writes, moves, or deletes metadata, page files, or library directories.
- Repeating an applied operation is a successful no-op with `changed: false` and `actions: []`.
- Responses never include task tokens or local paths. Invalid or ambiguous repair inputs return HTTP 409 through the normal CLI `http_error` envelope.

Preview response:

```json
{
  "operation": "repair",
  "gid": "123",
  "apply": false,
  "changed": false,
  "actions": [
    {
      "code": "register_library_task",
      "gid": "123",
      "task_status": "completed",
      "expected_pages": 3,
      "present_pages": 3
    }
  ]
}
```

`forget` uses action code `forget_task`. In preview mode, `changed` remains
false even when actions are planned. In apply mode, `changed` is true only when
the state registry was actually updated.

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
