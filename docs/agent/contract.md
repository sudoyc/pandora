# Agent Contract

This document describes the stable machine-facing Pandora contracts used by the Pandora Agent Pack.

## Surfaces

Agents may use:

- CLI JSON: `uv run python -m pandora_daemon.cli <command> --json`.
- CLI NDJSON: `uv run python -m pandora_daemon.cli download run ... --ndjson` and `download watch ... --ndjson`.
- REST: `http://127.0.0.1:7860/api/...`.
- WebSocket: `WS /ws`.

Installed CLI examples may use `pandora ...`; checkout examples use `uv run python -m pandora_daemon.cli ...`.

## Machine Contract Versioning

Pandora's machine contract has its own major version, independent of the
application package version. `GET /api/health` advertises the active major as
`contract_version`; the current value is `"1"`. The version covers the public
REST fields and status mappings, CLI JSON/NDJSON envelopes and exit codes, and
WebSocket event classification documented here.

### Compatible changes

Within contract v1, a change is compatible when it fixes an implementation to
match this document or adds an optional field to an object documented as
extensible. Existing field names, types, meanings, HTTP mappings, CLI exit
semantics, and terminal WebSocket event classifications remain stable. Clients
may ignore unknown nonterminal WebSocket events. A closed WebSocket stream
before the watched download emits a terminal event is a `websocket_error`, not
successful completion.

### Breaking changes

Removing or renaming a field, changing its type or meaning, changing a stable
HTTP/error or CLI exit mapping, making an optional field required, or adding new
terminal event semantics is breaking. A breaking change requires a new machine
contract major and a parallel migration surface; an application package version
bump alone does not change the machine contract.

### Deprecation

A deprecation documents its replacement, warns without corrupting machine
stdout, and remains supported through at least one subsequent minor application
release. Removal occurs only in a new machine contract major. Consumers should
branch on stable codes and structured fields, not human-facing `detail` or
`message` text.

## Diagnostic Correlation

Every daemon REST response includes `X-Request-ID`. A caller may supply either
a 32-character hexadecimal UUID or the standard 36-character UUID form; the
daemon canonicalizes valid input to 32 lowercase hexadecimal characters and
replaces invalid input. CLI daemon requests set this header automatically.

Download submission and PDF export also use `X-Correlation-ID`. The daemon
echoes both IDs in response headers and includes them as the optional v1 fields
`request_id` and `correlation_id` in long-task REST responses and WebSocket
events. `download run` preserves the echoed fields in its initial
`download_submitted` NDJSON event; later WebSocket events pass them through.

For a download, `correlation_id` identifies the logical task and survives
daemon restart. `request_id` identifies the request that submitted or most
recently changed that task, including cancel, resume, or retry. PDF export uses
one pair for its REST response and all hook events. Treat both values as opaque
diagnostic identifiers, not authorization tokens.

Request logs use the route template rather than dynamic path values. Long-task
logs contain only correlation fields such as IDs, `gid`, event, status, phase,
and exception type; they do not record request bodies, headers, tokens,
passwords, titles, local paths, or raw exception text.

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
- `tags status --json` reports the active provider's translated-tag catalog state; the built-in ExHentai provider uses EhTagTranslation.

`GET /api/health` returns the minimal successful daemon capability envelope.
Its stable shape is defined by
[`schemas/health-response.schema.json`](schemas/health-response.schema.json).

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

## REST Service Error Classification

Daemon exception handlers use a stable, sanitized envelope for classified
service failures:

```json
{"error":"session","detail":"Upstream session is invalid"}
```

Stable classifications:

- `auth`: required authentication configuration is absent or rejected.
- `session`: the configured session is invalid or expired.
- `upstream`: the upstream service or endpoint returned an unexpected HTTP status.
- `parse`: the upstream HTML or JSON response could not be parsed.
- `network`: the upstream transport failed.
- `gallery_not_found`: the requested gallery is unavailable.
- `image_limit`: the upstream image limit was reached.
- `offensive`: the requested gallery is unavailable for policy reasons.
- `exhentai`: an otherwise unclassified upstream-library failure occurred.
- `internal`: an unexpected daemon failure occurred.

A successful empty list is not an error category. Consumers must branch on
`error`, not on the human-readable `detail`. Unexpected daemon failures use HTTP
500 with `error: "internal"`. The daemon does not include
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
- `invalid_argument`
- `invalid_gallery_target`
- `usage_error`
- `websocket_error`
- `websocket_dependency_missing`

Schema: [`schemas/cli-error-envelope.schema.json`](schemas/cli-error-envelope.schema.json).

`refresh_failed` is an endpoint-specific result returned by `tags refresh`, not
a generic CLI error-envelope code. Consumers should still branch on its nested
code rather than its human-facing message.

Stable process exit semantics:

- exit 0: the command or watched download completed successfully.
- exit 1: a recognized negative result, service/transport failure, invalid
  command argument, or failed/incomplete WebSocket watch.
- exit 2: CLI parser usage error.
- exit 130: the operation was interrupted with Ctrl-C.

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

Homepage, search, and watched REST lists are cursor-paginated. The first
request omits `next`; each subsequent request passes the previous batch's last
`gid` as the `next` query parameter. Consumers stop on an empty response and
must also stop if the last `gid` does not advance.

## Gallery Inspection

```bash
uv run python -m pandora_daemon.cli gallery "https://exhentai.org/g/123/abcdef0123/" --json
uv run python -m pandora_daemon.cli gallery 123 abcdef0123 --json
```

CLI gallery output redacts daemon-only `api_uid` and `api_key` by default. Treat gallery detail as a user-facing metadata surface plus route identifiers. Daemon-internal helper fields such as `api_uid`, `api_key`, `viewer_urls`, `thumb_urls`, and `thumb_sprites` are internal-only and not part of the public stable contract.

`GET /api/gallery/{gid}/{token}` uses the
[`schemas/gallery-detail-response.schema.json`](schemas/gallery-detail-response.schema.json)
shape. The response intentionally omits the route token and daemon-only API
identity/helper fields.

## Download Events

WebSocket path:

```text
WS /ws
```

The daemon event discriminator is `event`, not `type`.

Common events:

Every event emitted by the daemon includes `request_id` and `correlation_id`.
They are omitted from the abbreviated event matrix below. A complete event has
this form:

```json
{"event":"download_progress","gid":"123","phase":"pages","page":5,"total":20,"request_id":"11111111111111111111111111111111","correlation_id":"22222222222222222222222222222222"}
```

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

Unknown nonterminal events may be ignored. If the stream closes before one of
the terminal events above, the CLI emits `websocket_error` and exits 1. Adding a
new terminal classification requires a new machine contract major.

Schema: [`schemas/download-event.schema.json`](schemas/download-event.schema.json).

## Download Task Lifecycle

Public task status values are `queued`, `downloading`, `completed`,
`completed_with_errors`, `paused`, `failed`, and `cancelled`. A
`download_auth_failed` event corresponds to task status `failed`; there is no
separate public `auth_failed` task status. The five final statuses are terminal
for the current watcher. A `paused` task remains resumable.

`POST /api/downloads` returns one public task object, and `GET /api/downloads`
returns an array of the same objects. They are defined by
[`schemas/download-task-response.schema.json`](schemas/download-task-response.schema.json)
and [`schemas/download-list-response.schema.json`](schemas/download-list-response.schema.json).
Neither shape contains the task token or local output path.
Both may include `request_id` and `correlation_id`; new daemon responses emit
both fields, while v1 consumers must continue treating additive fields as
optional.

Control operations have these state boundaries:

- Cancel accepts only `queued`, `downloading`, or `paused`. Missing tasks,
  final tasks, and repeated cancellation return `success: false` without
  changing state or emitting another event.
- Resume accepts only `paused`. Before queueing, the daemon reconciles
  `1..total_pages` against page files, clears stale failures and errors,
  persists `queued`, and emits `download_queued`.
- Retry accepts `completed_with_errors`, plus `completed` when expected page
  files are missing. Disk files are authoritative. If every previously failed
  page is already present, retry normalizes directly to `completed` without
  network work; otherwise it clears stale failures, persists `queued`, and
  emits `download_queued`.
- On daemon restart, persisted `queued` and `downloading` tasks are reconciled
  from disk and persisted as `queued` before workers start. Final tasks are not
  requeued.

## Download Pages

```bash
uv run python -m pandora_daemon.cli download pages 123 --json
```

Public page state values are `pending`, `downloading`, `completed`, and
`failed`. Internal state may use `done`, but REST task/list/page responses and
CLI page output expose it as `completed`.

`GET /api/downloads/{gid}/pages` is validated by
[`schemas/download-pages-response.schema.json`](schemas/download-pages-response.schema.json).
The response also carries the task's `request_id` and `correlation_id`.

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
normal nonzero error semantics. The response shape is defined by
[`schemas/download-consistency-report.schema.json`](schemas/download-consistency-report.schema.json).

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

## Library List

`GET /api/library` returns an array of local metadata objects. Every item has a
`gid` and daemon-generated `thumb_url`; other metadata fields remain extensible
to preserve existing downloaded entries. The successful response is described
by [`schemas/library-list-response.schema.json`](schemas/library-list-response.schema.json).

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

Each event below also includes the same `request_id` and `correlation_id` pair.

```json
{"event":"pdf_export_started","gid":"123"}
{"event":"pdf_export_complete","gid":"123","path":"/path/to/file.pdf","password_protected":true}
{"event":"pdf_export_error","gid":"123","error":"..."}
```

Bot success criteria:

- CLI/REST response includes `ok: true`, `format: "pdf"`, `path`,
  `password_protected`, `request_id`, and `correlation_id`.
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

`GET /api/tags/suggest` returns the
[`schemas/tag-suggest-response.schema.json`](schemas/tag-suggest-response.schema.json)
envelope. `GET /api/tags/status` returns the cache/load fields described by
[`schemas/tag-status-response.schema.json`](schemas/tag-status-response.schema.json).
