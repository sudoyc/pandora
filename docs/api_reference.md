# Pandora API Reference

This document summarizes Pandora's provider contracts, the built-in provider developer surface, the local `pandora-daemon` REST/WebSocket API, and the current CLI surface. REST/CLI/WS contract v1 is the public consumer boundary; adapter implementation imports are internal developer APIs.

## Provider application contract

`pandora_daemon.providers.contracts` defines immutable provider context, search, browse, detail,
account, mutation-result, media metadata, and translated-tag suggestion values together with the
`GalleryProvider` and `TagCatalog` protocols. Routes, image handling, downloads, and application
state depend on these types only. Every provider supplies a stable `provider_id`, authentication
readiness, a conforming tag catalog, browse/search/detail operations, page/thumbnail/media access,
supported mutations, home diagnostics, and `aclose()`. The registry rejects incomplete protocol
implementations at creation time. Adapter-owned `GalleryDetail.provider_data` is opaque outside
that adapter and is never serialized.

## Built-in provider developer API

The nested upstream implementation is stateless and all methods are async. Application code uses the `GalleryProvider` adapter rather than importing these classes directly.

```python
from pandora_daemon.providers.exhentai.upstream import ExhentaiAPI, ExhentaiClient

client = ExhentaiClient(igneous="...", ipb_member_id="...", ipb_pass_hash="...")
api = ExhentaiAPI(client=client)

async with ExhentaiAPI(client=client) as api:
    galleries = await api.get_homepage()
```

### Browse

| Method | Description |
|---|---|
| `get_homepage(next_gid=None)` | Main gallery list with optional next-batch cursor |
| `search(params, page=0, next_gid=None)` | Advanced gallery search; cursor takes precedence over legacy page number |
| `get_popular()` | Popular galleries |
| `get_toplist(tl="15")` | Toplist rankings; currently E-Hentai host only in live probing |
| `get_watched(page=0, next_gid=None)` | Watched-tag gallery list; live page may validly be empty |
| `image_search(file_path, similar=True, covers=True, exp=True)` | SHA1 image search |

### Gallery

| Method | Description |
|---|---|
| `get_gallery_details(gid, token)` | Full gallery metadata, comments, rating, torrents/archive metadata, preview URLs |
| `get_image_url(gid, imgkey, page, nl=None)` | Page image URL from viewer page or showpage API |
| `get_gallery_token(gid, imgkey, page)` | Gallery token via `api.php` gtoken |

### Interaction

| Method | Description |
|---|---|
| `comment_gallery(gid, token, comment, edit_id=None)` | Post/edit comment |
| `vote_comment(api_uid, api_key, gid, token, comment_id, vote)` | Vote on a comment (`1` or `-1`) |
| `rate_gallery(api_uid, api_key, gid, token, rating)` | Rate gallery (`2`-`10`, half-star scale) |

### Favorites / resources / tags / user

| Method | Description |
|---|---|
| `get_favorites(favcat=-1, page=0, keyword="", sn=False, st=False, sf=False)` | Favorites with categories |
| `add_favorite(gid, token, favcat=0, favnote="")` | Add/remove favorite (`favcat=-1` removes) |
| `modify_favorites(gids, ddact)` | Batch delete/move favorites |
| `get_torrent_list(gid, token)` | Torrent list |
| `get_archive_list(gid, token)` | Archive options |
| `download_archive(archive_url, resolution="org")` | Initiate archive download |
| `get_mytags()` / `add_tag(...)` / `delete_tag(tag_id)` | Account tag settings |
| `get_home_detail()` / `reset_image_limit()` | Image limits through the current E-Hentai home endpoint; reset is mutating and not exercised by unattended checks |
| `get_profile()` | Forum profile; live endpoint may return 403 |

## Main data models

- `GalleryListItem`: `gid`, `token`, `title`, `category`, `uploader`, `thumb_url`, `posted`, `rating`, `pages`, `rated`, dimensions, `url` property.
- `GalleryDetail`: metadata, tags, page counts, comments, and archive/torrent metadata. Daemon-internal helper fields used by the daemon, including `api_uid`, `api_key`, `viewer_urls`, `thumb_urls`, and `thumb_sprites`, are internal-only and not part of the public agent contract. CLI machine output redacts `api_uid` and `api_key` by default.
- `ImageDetail`: `gid`, `page`, `image_url`, `nl` reload token.
- `FavoritesResponse`: `categories`, `galleries`.
- `DownloadTask` (daemon): `gid`, `title`, `status`, progress counters, page
  states, `request_id`, and `correlation_id` on public machine surfaces.
  Daemon-local fields such as `token` and output directory/path values are
  internal-only and not part of the public stable contract.

## Daemon REST API

Default base URL: `http://127.0.0.1:7860`.

Daemon provider selection and credentials live in `~/.config/pandora/config.toml` under `[provider]` and `[provider.credentials]`. For the built-in adapter, `igneous` and `ipb_member_id` are the usual minimum; `ipb_pass_hash` is optional and should be left empty when the session does not require it. Legacy top-level `[credentials]` remains readable. Public config and CLI machine output expose the selected provider ID but never raw credential values.

The application version and machine contract version are independent. Clients
can read `contract_version: "1"` from `GET /api/health`; compatibility and
deprecation rules are defined in the
[`Agent Contract`](agent/contract.md#machine-contract-versioning).

### Diagnostic IDs

Daemon responses include `X-Request-ID`; callers may provide a UUID in 32- or
36-character form, and the daemon returns canonical 32-character lowercase
hex. Download submission and PDF export also accept and return
`X-Correlation-ID`. Their REST objects and WebSocket events expose the same
values as `request_id` and `correlation_id`.

For downloads, the correlation ID persists with the logical task across events
and daemon restart, while the request ID tracks the submit or most recent
cancel/resume/retry request. The CLI sets request IDs automatically and also
sets a correlation ID when starting a download or PDF export. Server logs use
route templates and minimal structured diagnostic fields without request
bodies, credentials, passwords, dynamic paths, local output paths, or raw
exception text.

### REST service error classification

Daemon exception handlers return a stable, sanitized REST envelope for
classified service failures:

```json
{"error":"session","detail":"Upstream session is invalid"}
```

| HTTP | `error` | Meaning |
|---|---|---|
| 401 | `auth` | Required authentication configuration is absent or rejected before a session can be used |
| 401 | `session` | A configured session was explicitly rejected or expired, including a Sad Panda response or HTTP 401 |
| 502 | `upstream` | The upstream service or endpoint returned an unexpected HTTP status |
| 502 | `parse` | An upstream HTML or JSON response could not be parsed |
| 502 | `network` | The upstream request failed at the transport layer |
| 500 | `exhentai` | An otherwise unclassified upstream-library failure occurred |
| 500 | `internal` | An unexpected daemon failure occurred |

These categories are distinct from a successful empty list. The `detail` value
is fixed human-readable text; exception messages, upstream status details,
cookies, proxy credentials, and response bodies are not returned or logged.
Resource-specific failures retain their existing codes, including
`gallery_not_found`, `image_limit`, and `offensive`.

Schema: [`agent/schemas/upstream-error.schema.json`](agent/schemas/upstream-error.schema.json).

### Browse

| Method | Path | Description |
|---|---|---|
| GET | `/api/homepage?next=...` | Homepage galleries; `next` is the last `gid` from the previous batch |
| GET | `/api/search?keyword=...&next=...&min_rating=...&category=...` | Search galleries; `next` is the last `gid` from the previous batch and `category` is an include bitmask |
| GET | `/api/popular` | Popular galleries |
| GET | `/api/toplist?tl=15` | Toplist as gallery-compatible rows |
| GET | `/api/watched?next=...` | Watched-tag galleries; `next` is the last `gid` from the previous batch |
| GET | `/api/image/proxy?url=...` | Proxy/cache arbitrary image URL |

Search, homepage, popular, toplist, and watched gallery-list responses use the
[`search response schema`](agent/schemas/search-response.schema.json).

Homepage, search, and watched lists use upstream cursor pagination. Omit
`next` for the first batch, then pass the final returned gallery's `gid` as
`next` for the following batch. An empty batch ends the list. The legacy
numeric `page` parameter remains accepted for compatibility, but cursor
pagination is the stable interface for continuous gallery feeds.

### Gallery

| Method | Path | Description |
|---|---|---|
| GET | `/api/gallery/{gid}/{token}` | Gallery detail; auto-writes history |
| POST | `/api/gallery/{gid}/{token}/comment` | Body `{comment, edit_id?}` |
| POST | `/api/gallery/{gid}/{token}/rate` | Body `{rating}` |
| POST | `/api/gallery/{gid}/{token}/vote_comment` | Body `{comment_id, vote}` |
| GET | `/api/gallery/{gid}/{token}/torrents` | Torrent list |
| GET | `/api/gallery/{gid}/{token}/archive` | Archive options |
| GET | `/api/gallery/{gid}/{token}/page/{page}` | Full-size page image bytes |
| GET | `/api/gallery/{gid}/{token}/thumb/{page}` | Cropped thumbnail bytes |
| POST | `/api/gallery/{gid}/{token}/prefetch` | Body `{current_page}`; prefetches around current page and updates bookmark |

The successful gallery detail response is validated by
[`gallery-detail-response.schema.json`](agent/schemas/gallery-detail-response.schema.json).

### Favorites

| Method | Path | Description |
|---|---|---|
| GET | `/api/favorites?slot=-1&page=0&keyword=&sn=false&st=false&sf=false` | Account favorites |
| POST | `/api/favorites` | Body `{gid, token, slot, note}` |
| DELETE | `/api/favorites` | Body `{gids, action}` |

### Downloads

| Method | Path | Description |
|---|---|---|
| POST | `/api/downloads` | Submit download, body `{gid, token}` |
| GET | `/api/downloads` | List all known download tasks |
| GET | `/api/downloads/report` | Read-only task, metadata, page, and library consistency report |
| POST | `/api/downloads/{gid}/repair` | Preview/apply registration of one complete library entry; body `{apply}` |
| POST | `/api/downloads/{gid}/forget` | Preview/apply removal of inactive task state; body `{apply}` |
| DELETE | `/api/downloads/{gid}` | Cancel a `queued`, `downloading`, or `paused` task; other states are an eventless no-op |
| POST | `/api/downloads/{gid}/retry` | Reconcile and retry missing pages for `completed_with_errors`, or for `completed` when files are missing |
| POST | `/api/downloads/{gid}/resume` | Reconcile and resume a `paused` task |
| GET | `/api/downloads/{gid}/pages` | Page-level status using `pending`, `downloading`, `completed`, or `failed` |

Successful download responses use the
[`task`](agent/schemas/download-task-response.schema.json),
[`list`](agent/schemas/download-list-response.schema.json),
[`pages`](agent/schemas/download-pages-response.schema.json), and
[`consistency report`](agent/schemas/download-consistency-report.schema.json)
schemas for the corresponding endpoints.

Public download task statuses are `queued`, `downloading`, `completed`,
`completed_with_errors`, `paused`, `failed`, and `cancelled`. Resume and retry
reconcile actual page files before queueing and clear stale error state. A retry
whose pages have already been restored normalizes directly to `completed`.
After daemon restart, active tasks are reconciled and persisted as `queued`
before workers start; final tasks are not requeued. Internal page state `done`
is exposed as `completed` by REST and CLI surfaces.
Task/list/pages responses include the task's diagnostic IDs. The correlation ID
is stable for the logical download; cancel, resume, and retry replace the task's
request ID with the ID of the state-changing request.

### Local database endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/history?limit=50&offset=0` | Browsing history |
| DELETE | `/api/history/{gid}` | Delete history entry |
| DELETE | `/api/history` | Clear history |
| GET | `/api/local-favorites?limit=50&offset=0` | Local favorites |
| POST | `/api/local-favorites` | Add local favorite |
| DELETE | `/api/local-favorites/{gid}` | Remove local favorite |
| GET | `/api/bookmarks?limit=50&offset=0` | Reading bookmarks |
| GET | `/api/bookmarks/{gid}` | Single bookmark |
| DELETE | `/api/bookmarks/{gid}` | Delete bookmark |
| GET | `/api/quick-search` | Saved search presets |
| POST | `/api/quick-search` | Add preset |
| DELETE | `/api/quick-search/{search_id}` | Delete preset |
| GET | `/api/filters` | Filter rules |
| POST | `/api/filters` | Add filter; modes: 0 title, 1 uploader, 2 tag, 3 namespace |
| PUT | `/api/filters/{filter_id}` | Toggle filter |
| DELETE | `/api/filters/{filter_id}` | Delete filter |

### Config / user / tags / library

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Minimal daemon health and capability probe; includes `contract_version`; omits credentials and local paths |
| GET | `/api/readiness` | Read-only authenticated homepage/search/popular/home checks with stable, sanitized status values |
| GET | `/api/config` | Public config; omits credentials and redacts proxy secrets |
| PUT | `/api/config` | Update a validated subset of public server/download/cache config fields; not an arbitrary dict patch |
| GET | `/api/home` | User home/image limits through the current E-Hentai home endpoint |
| POST | `/api/home/reset_limit` | Reset image limit; mutating upstream behavior is not exercised by unattended checks |
| GET | `/api/profile` | User profile; forum endpoint may return 403 |
| GET | `/api/tags` | Account watched/hidden tags |
| POST | `/api/tags` | Add account tag |
| DELETE | `/api/tags/{tag_id}` | Delete account tag |
| GET | `/api/tags/suggest?q=...&limit=10` | Active provider suggestions; the built-in ExHentai adapter uses EhTagTranslation |
| GET | `/api/tags/status` | Tag translation database cache/load status |
| POST | `/api/tags/refresh?force=false` | Refresh tag translation database cache using ETag metadata |
| GET | `/api/library` | Downloaded gallery metadata list |
| GET | `/api/library/{gid}/file?path=cover` | Serve local cover |
| GET | `/api/library/{gid}/file?path=thumb/{page}` | Serve local thumbnail |
| GET | `/api/library/{gid}/file?path=page/{page}` | Serve local page |
| POST | `/api/library/{gid}/export/pdf` | Export a PDF; body supports `password`, `output_name`, and `include_cover` |

The successful health, readiness, tag, and library list envelopes are defined
by [`health-response.schema.json`](agent/schemas/health-response.schema.json),
[`readiness-response.schema.json`](agent/schemas/readiness-response.schema.json),
[`tag-suggest-response.schema.json`](agent/schemas/tag-suggest-response.schema.json),
[`tag-status-response.schema.json`](agent/schemas/tag-status-response.schema.json),
and [`library-list-response.schema.json`](agent/schemas/library-list-response.schema.json).

## WebSocket

Path: `WS /ws`

Download event examples:

Daemon download events also contain `request_id` and `correlation_id`; those
fields are omitted from the abbreviated matrix below.

```json
{"event":"download_queued","gid":"123","title":"..."}
{"event":"download_progress","gid":"123","phase":"cover"}
{"event":"download_progress","gid":"123","phase":"thumbs","page":5,"total":20}
{"event":"download_progress","gid":"123","phase":"pages","page":5,"total":20}
{"event":"download_complete","gid":"123"}
{"event":"download_complete_with_errors","gid":"123","failed_pages":[7,12]}
{"event":"download_error","gid":"123","error":"..."}
{"event":"download_cancelled","gid":"123"}
{"event":"download_paused","gid":"123","reason":"image_limit"}
{"event":"download_auth_failed","gid":"123","error":"..."}
```

PDF export events use the same diagnostic pair:

```json
{"event":"pdf_export_started","gid":"123","request_id":"11111111111111111111111111111111","correlation_id":"22222222222222222222222222222222"}
{"event":"pdf_export_complete","gid":"123","path":"/path/to/file.pdf","password_protected":true,"request_id":"11111111111111111111111111111111","correlation_id":"22222222222222222222222222222222"}
{"event":"pdf_export_error","gid":"123","error":"PDF export failed","request_id":"11111111111111111111111111111111","correlation_id":"22222222222222222222222222222222"}
```

## CLI

Deployment, daemon startup, readiness checks, and systemd examples live in [`docs/deployment.md`](deployment.md).

Global options on daemon-backed commands:

- `--daemon-url http://127.0.0.1:7860`
- `--json`
- `--timeout 30`

For bots, use `download run <url|gid> [token] --ndjson` as the supported successful streaming machine mode. It attaches to `WS /ws` before posting `/api/downloads`, emits a `download_submitted` machine event, and then watches until a terminal event. If `/api/downloads` returns HTTP 409 for an already-active task, `download run` emits `download_already_queued` and continues watching instead of failing. `download add` plus `download watch` remains available, but a late watcher can miss events emitted between the two commands.
The submitted event includes the request and correlation IDs echoed by the
daemon, and subsequent WebSocket events retain the task correlation ID.

`download watch --json` is accepted for JSON error envelopes, while successful watch output is still event-by-event. `download pages --json` normalizes internal page state `done` to public state `completed`. Public REST/CLI download surfaces do not expose daemon-local output directory/path fields as public contract; treat any such values as internal-only.

`download report --json` calls `GET /api/downloads/report`. The response uses
`consistent`, `summary`, and `issues`; it never returns task tokens or local
paths. A successfully retrieved inconsistent report exits 0, while transport or
HTTP failures use the normal machine error envelope.

`download repair <gid> --json` and `download forget <gid> --json` are previews;
they send `{ "apply": false }` and do not write state. Add `--apply` to send
`{ "apply": true }`. Repair only registers a uniquely identified library entry
with valid metadata and every expected page. Forget only removes an inactive
task. Both operations preserve all library files and omit tokens and local paths
from their responses. Repeating a successful apply returns `changed: false` and
an empty `actions` list.

Machine-mode errors:

```json
{"ok": false, "error": {"code": "http_error", "message": "503 daemon unavailable"}}
```

Current generic error-envelope codes are `connect_error`, `http_error`,
`invalid_argument`, `invalid_gallery_target`, `usage_error`, `websocket_error`,
and `websocket_dependency_missing`. The endpoint-specific `refresh_failed` code
belongs to the `tags refresh` command result rather than that generic schema.

Stable CLI exits are 0 for success, 1 for recognized negative results and
runtime failures, 2 for parser usage errors, and 130 for Ctrl-C. A download
WebSocket that closes before a terminal event emits `websocket_error` and exits
1. See the Agent Contract for the complete compatibility policy and terminal
event matrix.

`readiness --json` prints the [`readiness response`](agent/schemas/readiness-response.schema.json)
even when upstream is not ready. It exits with exit 0 only when `ready` is true
and exits with exit 1 for every recognized not-ready result.

Search/tag workflow for agents uses scheme A: Pandora exposes primitive interfaces only and does not rewrite translated user text into tag queries. A bot should call `tags status`, refresh if needed, call `tags suggest`, choose the desired namespace/tag candidate itself, then call `search` with an explicit keyword such as `female:stockings` and `--search-tags`.

Advanced search query parameters accepted by `/api/search` are `category`, `min_rating`, `search_name`, `search_tags`, `search_description`, `search_torrent`, `search_low_power_tags`, `disable_language_filter`, `show_expunged`, `min_pages`, and `max_pages`. `category` remains the public v1 include bitmask; the built-in ExHentai adapter converts it to that upstream's exclude bitmask.

Current commands:

```bash
pandora health --json
pandora config --json
pandora readiness --json
pandora status --json
pandora download <url>              # legacy interactive path; submits and monitors via WebSocket
pandora dl <url>
pandora download run <url|gid> [token] --ndjson
pandora download add <url|gid> [token] --json
pandora download list --json
pandora download report --json
pandora download repair <gid> [--apply] --json
pandora download forget <gid> [--apply] --json
pandora download watch [gid] --ndjson
pandora download cancel <gid> --json
pandora download resume <gid> --json
pandora download retry <gid> --json
pandora download pages <gid> --json
pandora status --json
pandora search "keyword" --page 0 --json
pandora search "female:stockings" --search-tags --json
pandora gallery <url|gid> [token] --json
pandora library list --json
pandora library export-pdf <gid> [--password PDF_PASSWORD] --json
pandora tags status --json
pandora tags refresh [--force] --json
pandora tags suggest "tag" --json
pandora favorites list --json              # fetches all favorites (`slot=-1`)
pandora popular --json
pandora toplist --tl 15 --json
pandora watched --page 0 --json
```
