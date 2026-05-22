# Pandora API Reference

This document summarizes the Python `exhentai_api` package, the local `pandora-daemon` REST/WebSocket API, and the current CLI surface.

## Python package: `exhentai_api`

All methods are async.

```python
from exhentai_api import ExhentaiAPI, ExhentaiClient

client = ExhentaiClient(igneous="...", ipb_member_id="...", ipb_pass_hash="...")
api = ExhentaiAPI(client=client)

async with ExhentaiAPI(client=client) as api:
    galleries = await api.get_homepage()
```

### Browse

| Method | Description |
|---|---|
| `get_homepage(page=0)` | Main gallery list |
| `search(params, page=0)` | Advanced gallery search |
| `get_popular()` | Popular galleries |
| `get_toplist(tl="15")` | Toplist rankings; currently E-Hentai host only in live probing |
| `get_watched(page=0)` | Watched-tag gallery list; live page may validly be empty |
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
| `get_home_detail()` / `reset_image_limit()` | Image limits; live endpoint needs re-check |
| `get_profile()` | Forum profile; live endpoint may return 403 |

## Main data models

- `GalleryListItem`: `gid`, `token`, `title`, `category`, `uploader`, `thumb_url`, `posted`, `rating`, `pages`, `rated`, dimensions, `url` property.
- `GalleryDetail`: metadata, tags, page counts, comments, and archive/torrent metadata. Daemon-internal helper fields used by the daemon, including `api_uid`, `api_key`, `viewer_urls`, `thumb_urls`, and `thumb_sprites`, are internal-only and not part of the public agent contract. CLI machine output redacts `api_uid` and `api_key` by default.
- `ImageDetail`: `gid`, `page`, `image_url`, `nl` reload token.
- `FavoritesResponse`: `categories`, `galleries`.
- `DownloadTask` (daemon): `gid`, `title`, `status`, progress counters, and page states on public machine surfaces. Daemon-local fields such as `token` and output directory/path values are internal-only and not part of the public stable contract.

## Daemon REST API

Default base URL: `http://127.0.0.1:7860`.

Daemon credentials live in `~/.config/pandora/config.toml` under `[credentials]`. `igneous` and `ipb_member_id` are the usual minimum; `ipb_pass_hash` is optional and should be left empty when the session does not require it. Public config and CLI machine output never expose raw credential values.

### Browse

| Method | Path | Description |
|---|---|---|
| GET | `/api/homepage` | Homepage galleries |
| GET | `/api/search?keyword=...&page=0&min_rating=...&category=...` | Search galleries; `category` is an include bitmask |
| GET | `/api/popular` | Popular galleries |
| GET | `/api/toplist?tl=15` | Toplist as gallery-compatible rows |
| GET | `/api/watched?page=0` | Watched-tag galleries |
| GET | `/api/image/proxy?url=...` | Proxy/cache arbitrary image URL |

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
| DELETE | `/api/downloads/{gid}` | Cancel task |
| POST | `/api/downloads/{gid}/retry` | Retry failed pages for `completed_with_errors` task |
| POST | `/api/downloads/{gid}/resume` | Resume paused task |
| GET | `/api/downloads/{gid}/pages` | Page-level status detail |

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
| GET | `/api/health` | Minimal daemon health and capability probe; omits credentials and local paths |
| GET | `/api/config` | Public config; omits credentials and redacts proxy secrets |
| PUT | `/api/config` | Update a validated subset of public server/download/cache config fields; not an arbitrary dict patch |
| GET | `/api/home` | User home/image limits; live endpoint needs re-check |
| POST | `/api/home/reset_limit` | Reset image limit; live endpoint needs re-check |
| GET | `/api/profile` | User profile; forum endpoint may return 403 |
| GET | `/api/tags` | Account watched/hidden tags |
| POST | `/api/tags` | Add account tag |
| DELETE | `/api/tags/{tag_id}` | Delete account tag |
| GET | `/api/tags/suggest?q=...&limit=10` | EhTagTranslation suggestions |
| GET | `/api/tags/status` | Tag translation database cache/load status |
| POST | `/api/tags/refresh?force=false` | Refresh tag translation database cache using ETag metadata |
| GET | `/api/library` | Downloaded gallery metadata list |
| GET | `/api/library/{gid}/file?path=cover` | Serve local cover |
| GET | `/api/library/{gid}/file?path=thumb/{page}` | Serve local thumbnail |
| GET | `/api/library/{gid}/file?path=page/{page}` | Serve local page |

## WebSocket

Path: `WS /ws`

Download event examples:

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

## CLI

Deployment, daemon startup, readiness checks, and systemd examples live in [`docs/deployment.md`](deployment.md).

Global options on daemon-backed commands:

- `--daemon-url http://127.0.0.1:7860`
- `--json`
- `--timeout 30`

For bots, use `download run <url|gid> [token] --ndjson` as the supported successful streaming machine mode. It attaches to `WS /ws` before posting `/api/downloads`, emits a `download_submitted` machine event, and then watches until a terminal event. If `/api/downloads` returns HTTP 409 for an already-active task, `download run` emits `download_already_queued` and continues watching instead of failing. `download add` plus `download watch` remains available, but a late watcher can miss events emitted between the two commands.

`download watch --json` is accepted for JSON error envelopes, while successful watch output is still event-by-event. `download pages --json` normalizes internal page state `done` to public state `completed`. Public REST/CLI download surfaces do not expose daemon-local output directory/path fields as public contract; treat any such values as internal-only.

Machine-mode errors:

```json
{"ok": false, "error": {"code": "http_error", "message": "503 daemon unavailable"}}
```

Current tested error codes include `connect_error`, `http_error`, `invalid_gallery_target`, `usage_error`, `websocket_error`, and `websocket_dependency_missing`.

Search/tag workflow for agents uses scheme A: Pandora exposes primitive interfaces only and does not rewrite translated user text into tag queries. A bot should call `tags status`, refresh if needed, call `tags suggest`, choose the desired namespace/tag candidate itself, then call `search` with an explicit keyword such as `female:stockings` and `--search-tags`.

Advanced search query parameters accepted by `/api/search` are `category`, `min_rating`, `search_name`, `search_tags`, `search_description`, `search_torrent`, `search_low_power_tags`, `disable_language_filter`, `show_expunged`, `min_pages`, and `max_pages`. `category` is passed as an include bitmask; `SearchParams.to_dict()` converts it to ExHentai's exclude bitmask before the upstream request.

Current commands:

```bash
pandora health --json
pandora config --json
pandora download <url>              # legacy interactive path; submits and monitors via WebSocket
pandora dl <url>
pandora download run <url|gid> [token] --ndjson
pandora download add <url|gid> [token] --json
pandora download list --json
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
pandora tags status --json
pandora tags refresh [--force] --json
pandora tags suggest "tag" --json
pandora favorites list --json              # fetches all favorites (`slot=-1`)
pandora popular --json
pandora toplist --tl 15 --json
pandora watched --page 0 --json
```
