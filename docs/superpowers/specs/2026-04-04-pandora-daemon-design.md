# pandora-daemon Design Spec

## Overview

pandora-daemon is a local FastAPI service that wraps `exhentai_api` as a REST + WebSocket API. All frontends (Rust TUI, Web, CLI) connect to the daemon instead of making direct ExHentai requests.

**Single process, asyncio-based.** The daemon manages session state, download queue, caching, and configuration — things the stateless `exhentai_api` library intentionally does not handle.

## Architecture

```
exhentai_api (stateless library)
        │ import
pandora_daemon (FastAPI, single process)
        ├── AppState          ── holds ExhentaiAPI, DownloadManager, CacheManager, WebSocketManager
        ├── routes/           ── REST endpoints grouped by domain
        ├── DownloadManager   ── asyncio workers + JSON persistence
        ├── CacheManager      ── disk thumbs + in-memory TTL
        ├── WebSocketManager  ── broadcast events to connected clients
        └── config.py         ── TOML config load/save
```

## File Structure

```
pandora_daemon/
├── __init__.py
├── __main__.py          # Entry point: `python -m pandora_daemon`
├── app.py               # FastAPI app creation + lifespan
├── config.py            # PandoraConfig dataclass + TOML load/save
├── state.py             # AppState dataclass
├── dependencies.py      # FastAPI Depends() helpers
├── download.py          # DownloadManager + DownloadTask
├── cache.py             # CacheManager (disk thumbs + memory TTL)
├── ws.py                # WebSocketManager + event broadcast
└── routes/
    ├── __init__.py      # Includes all routers
    ├── browse.py        # search, homepage, popular, toplist, watched
    ├── gallery.py       # gallery detail, images, comments, rating
    ├── favorites.py     # favorites CRUD
    ├── downloads.py     # download queue management
    ├── user.py          # home, profile, tags
    └── config_routes.py # config read/update
```

## 1. Configuration (`config.py`)

### Config File Location

`~/.config/pandora/config.toml` — created with defaults if absent.

### Config Schema

```toml
[credentials]
igneous = ""
ipb_member_id = ""

[server]
host = "127.0.0.1"
port = 7860

[download]
path = "~/Downloads/pandora"
concurrency = 3

[cache]
thumb_dir = "~/.cache/pandora/thumbs"
thumb_max_size_mb = 500
gallery_ttl_seconds = 300
```

### PandoraConfig Dataclass

```python
@dataclass
class CredentialsConfig:
    igneous: str = ""
    ipb_member_id: str = ""

@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 7860

@dataclass
class DownloadConfig:
    path: str = "~/Downloads/pandora"
    concurrency: int = 3

@dataclass
class CacheConfig:
    thumb_dir: str = "~/.cache/pandora/thumbs"
    thumb_max_size_mb: int = 500
    gallery_ttl_seconds: int = 300

@dataclass
class PandoraConfig:
    credentials: CredentialsConfig
    server: ServerConfig
    download: DownloadConfig
    cache: CacheConfig
```

### Behavior

- `load_config(path: Path) -> PandoraConfig`: Reads TOML, creates defaults if missing, expands `~` in all paths.
- `save_config(config: PandoraConfig, path: Path)`: Writes back to TOML.
- Credentials are never exposed through the REST API (GET `/api/config` omits them).

## 2. Application State (`state.py`)

```python
@dataclass
class AppState:
    config: PandoraConfig
    config_path: Path
    client: ExhentaiClient
    api: ExhentaiAPI
    downloads: DownloadManager
    cache: CacheManager
    ws: WebSocketManager
```

Created in lifespan, stored as `app.state.pandora`, accessed via `dependencies.py`.

## 3. Application Lifespan (`app.py`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)

    client = ExhentaiClient(
        igneous=config.credentials.igneous,
        ipb_member_id=config.credentials.ipb_member_id,
    )
    api = ExhentaiAPI(client=client)
    cache = CacheManager(config.cache)
    ws = WebSocketManager()
    downloads = DownloadManager(api=api, config=config.download, ws=ws)

    state = AppState(
        config=config, config_path=config_path,
        client=client, api=api,
        downloads=downloads, cache=cache, ws=ws,
    )
    app.state.pandora = state

    await downloads.start()
    yield
    await downloads.shutdown()
    await api.aclose()
```

## 4. Dependencies (`dependencies.py`)

```python
def get_state(request: Request) -> AppState:
    return request.app.state.pandora

def get_api(state: AppState = Depends(get_state)) -> ExhentaiAPI:
    return state.api

def get_downloads(state: AppState = Depends(get_state)) -> DownloadManager:
    return state.downloads

def get_cache(state: AppState = Depends(get_state)) -> CacheManager:
    return state.cache
```

## 5. REST API Routes

### 5.1 Browse (`routes/browse.py`)

| Method | Path | Query Params | Returns | Wraps |
|--------|------|-------------|---------|-------|
| GET | `/api/search` | `keyword`, `page`, `min_rating`, `category`, etc. | `list[GalleryListItem]` | `api.search(SearchParams, page)` |
| GET | `/api/homepage` | — | `list[GalleryListItem]` | `api.get_homepage()` |
| GET | `/api/popular` | — | `list[GalleryListItem]` | `api.get_popular()` |
| GET | `/api/toplist` | `tl` (default "15") | `list[TopListItem]` | `api.get_toplist(tl)` |
| GET | `/api/watched` | `page` | `list[GalleryListItem]` | `api.get_watched(page)` |

**Search query parameters** map to `SearchParams` fields:
- `keyword` → `f_search`
- `page` → page number
- `min_rating` → `f_srdd` (with `f_sr="on"`)
- `category` → `f_cats` bitmask. Frontends send the integer bitmask directly (same as ExHentai's `f_cats` parameter). No name-to-bitmask conversion in the daemon.
- Additional advanced search params passed through as-is

### 5.2 Gallery (`routes/gallery.py`)

| Method | Path | Body/Params | Returns | Wraps |
|--------|------|-------------|---------|-------|
| GET | `/api/gallery/{gid}/{token}` | — | `GalleryDetail` | `api.get_gallery_details(gid, token)` with cache |
| GET | `/api/gallery/{gid}/{token}/images` | `page` (optional) | `list[ImageDetail]` | iterate `get_image_url()` for all pages |
| POST | `/api/gallery/{gid}/{token}/comment` | `{"comment": "text", "edit_id": null}` | `list[GalleryComment]` | `api.comment_gallery()` |
| POST | `/api/gallery/{gid}/{token}/rate` | `{"rating": 8}` | `RateResult` | `api.rate_gallery()` |
| POST | `/api/gallery/{gid}/{token}/vote_comment` | `{"comment_id": 1, "vote": 1}` | `VoteCommentResult` | `api.vote_comment()` |
| GET | `/api/gallery/{gid}/{token}/torrents` | — | `list[TorrentItem]` | `api.get_torrent_list()` |
| GET | `/api/gallery/{gid}/{token}/archive` | — | `ArchiverData` | `api.get_archive_list()` |

**Gallery detail caching:** GET `/api/gallery/{gid}/{token}` checks `CacheManager` first. Cache miss → fetch + cache with TTL.

**Image listing:** `/api/gallery/{gid}/{token}/images` fetches image URLs by iterating pages. Without a `page` param, it returns image URLs for all pages (N requests — expensive, use sparingly). With `page=N`, it returns a single page's `ImageDetail`. The route parses the gallery detail's preview pages to extract per-page image tokens (imgkey), then calls `api.get_image_url(gid, imgkey, page)` for each.

### 5.3 Favorites (`routes/favorites.py`)

| Method | Path | Params/Body | Returns | Wraps |
|--------|------|-------------|---------|-------|
| GET | `/api/favorites` | `slot` (-1=all), `page`, `keyword`, `sn`, `st`, `sf` | `FavoritesResponse` | `api.get_favorites()` |
| POST | `/api/favorites` | `{"gid": "x", "token": "y", "slot": 0, "note": ""}` | `str` | `api.add_favorite()` |
| DELETE | `/api/favorites` | `{"gids": ["x","y"], "action": "delete"}` | `str` | `api.modify_favorites()` |

### 5.4 Downloads (`routes/downloads.py`)

| Method | Path | Body/Params | Returns | Wraps |
|--------|------|-------------|---------|-------|
| POST | `/api/downloads` | `{"gid": "x", "token": "y"}` | `DownloadTask` | `downloads.submit()` |
| GET | `/api/downloads` | — | `list[DownloadTask]` | `downloads.status()` |
| DELETE | `/api/downloads/{gid}` | — | `{"success": bool}` | `downloads.cancel()` |

### 5.5 User (`routes/user.py`)

| Method | Path | Body | Returns | Wraps |
|--------|------|------|---------|-------|
| GET | `/api/home` | — | `HomeDetail` | `api.get_home_detail()` |
| POST | `/api/home/reset_limit` | — | `HomeDetail` | `api.reset_image_limit()` |
| GET | `/api/profile` | — | `ProfileResult` | `api.get_profile()` |
| GET | `/api/tags` | — | `list[WatchedTag]` | `api.get_mytags()` |
| POST | `/api/tags` | `{"name": "x", "watched": true, ...}` | `list[WatchedTag]` | `api.add_tag()` |
| DELETE | `/api/tags/{tag_id}` | — | `list[WatchedTag]` | `api.delete_tag()` |

### 5.6 Config (`routes/config_routes.py`)

| Method | Path | Body | Returns |
|--------|------|------|---------|
| GET | `/api/config` | — | Config (credentials omitted) |
| PUT | `/api/config` | Partial config update | Updated config |

PUT merges the provided fields into the current config and writes back to TOML.

### 5.7 Thumbnails (`routes/browse.py`)

| Method | Path | Params | Returns |
|--------|------|--------|---------|
| GET | `/api/thumb` | `url` (thumbnail URL) | Raw image bytes (proxied + cached) |

Proxies thumbnail requests through the daemon, caching to disk. Frontends never need ExHentai cookies to load thumbnails.

## 6. Download Manager (`download.py`)

### DownloadTask Model

```python
@dataclass
class DownloadTask:
    gid: str
    token: str
    title: str
    status: str          # "queued" | "downloading" | "completed" | "failed" | "cancelled"
    total_pages: int
    downloaded_pages: int
    output_dir: str
    error: str           # empty if no error
    created_at: str      # ISO timestamp
```

### DownloadManager

```python
class DownloadManager:
    def __init__(self, api: ExhentaiAPI, config: DownloadConfig, ws: WebSocketManager): ...

    async def start(self) -> None
        # Start N worker tasks (config.concurrency)
        # Load downloads.json and re-queue pending/downloading tasks

    async def shutdown(self) -> None
        # Cancel workers, save state

    async def submit(self, gid: str, token: str) -> DownloadTask
        # Fetch gallery detail for title + page count
        # Create DownloadTask, put on queue
        # Broadcast "download_queued" event
        # Save state

    async def cancel(self, gid: str) -> bool
        # Mark task as cancelled
        # Broadcast "download_cancelled" event
        # Save state

    async def status(self) -> list[DownloadTask]
        # Return all tasks (queued + active + completed + failed)

    async def _worker(self) -> None
        # Loop: get task from queue, download pages, update progress
        # Per-page: get_image_url() -> download bytes -> save file
        # Broadcast "download_progress" after each page
        # On completion: broadcast "download_complete"
        # On error: broadcast "download_error", mark failed
```

### Download Flow (per gallery)

1. `submit()` fetches `GalleryDetail` to get `title`, `pages`, and preview page URLs
2. Worker gets task from queue, sets status to "downloading"
3. For each page (1..total_pages):
   a. Parse preview page to extract image page tokens
   b. Call `api.get_image_url(gid, imgkey, page)` → `ImageDetail`
   c. Download image bytes via `client.session.get(image_url)`
   d. Save to `{download_path}/{gid}-{sanitized_title}/{page:04d}.{ext}`
   e. Broadcast progress event
   f. Save state to `downloads.json`
4. On completion: write `metadata.json` with gallery info, broadcast complete event

### Persistence

State file: `~/.config/pandora/downloads.json`

```json
{
  "tasks": [
    {
      "gid": "12345",
      "token": "abc",
      "title": "Gallery Title",
      "status": "downloading",
      "total_pages": 20,
      "downloaded_pages": 5,
      "output_dir": "/home/user/Downloads/pandora/12345-Gallery Title",
      "error": "",
      "created_at": "2026-04-04T12:00:00"
    }
  ]
}
```

On startup, tasks with status "queued" or "downloading" are re-queued. "Downloading" tasks resume from `downloaded_pages` (skip already-downloaded files).

## 7. Cache Manager (`cache.py`)

### Thumbnail Cache (Disk)

- Directory: `~/.cache/pandora/thumbs/`
- Key: SHA256 of thumbnail URL → `{hash}.jpg`
- Max size: configurable (default 500 MB)
- Eviction: LRU based on file access time when total size exceeds limit

### Gallery Detail Cache (In-Memory)

- Key: `{gid}:{token}`
- Value: `GalleryDetail` + expiry timestamp
- TTL: configurable (default 300 seconds)
- No persistence (cleared on restart)

### Interface

```python
class CacheManager:
    def __init__(self, config: CacheConfig): ...

    # Thumbnail cache
    async def get_thumb(self, url: str) -> bytes | None
    async def put_thumb(self, url: str, data: bytes) -> None
    async def evict_thumbs(self) -> None

    # Gallery cache
    def get_gallery(self, gid: str, token: str) -> GalleryDetail | None
    def put_gallery(self, detail: GalleryDetail) -> None
```

## 8. WebSocket Manager (`ws.py`)

### Connection Management

```python
class WebSocketManager:
    def __init__(self): ...

    async def connect(self, websocket: WebSocket) -> None
        # Accept + add to connection set

    def disconnect(self, websocket: WebSocket) -> None
        # Remove from connection set

    async def broadcast(self, event: dict) -> None
        # Send JSON to all connected clients
        # Remove disconnected clients on send failure
```

### WebSocket Endpoint

```python
@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, state: AppState = Depends(get_state)):
    await state.ws.connect(ws)
    try:
        while True:
            await ws.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        state.ws.disconnect(ws)
```

### Event Types

| Event | Fields | When |
|-------|--------|------|
| `download_queued` | `gid`, `title`, `total_pages` | Task submitted |
| `download_progress` | `gid`, `page`, `total_pages` | Page downloaded |
| `download_complete` | `gid`, `path` | All pages done |
| `download_error` | `gid`, `error` | Download failed |
| `download_cancelled` | `gid` | Task cancelled |

## 9. Entry Point (`__main__.py`)

```python
# python -m pandora_daemon
import uvicorn
from pandora_daemon.app import create_app
from pandora_daemon.config import load_config

def main():
    config = load_config()
    app = create_app()
    uvicorn.run(app, host=config.server.host, port=config.server.port)

if __name__ == "__main__":
    main()
```

## 10. Error Handling

- **Sad Panda**: `ExhentaiClient` raises `RuntimeError`. The daemon catches this at the route level and returns HTTP 401 with a clear message.
- **Network errors**: `exhentai_api` retries 3 times internally. If still failing, the route returns HTTP 502.
- **Download errors**: Per-page errors are caught and reported. The task is marked "failed" with the error message. Other downloads continue.
- **WebSocket disconnects**: Silently removed from broadcast set.
- **Config errors**: Invalid TOML → daemon refuses to start with a clear error message.

## 11. Dependencies

```toml
[project]
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "httpx>=0.28",
    "beautifulsoup4>=4.13",
    "tomli>=2.0;python_version<'3.11'",  # stdlib tomllib in 3.11+
    "tomli-w>=1.0",                       # TOML writing
]
```

No Redis, no database, no Celery. Pure Python + asyncio.

## 12. Testing Strategy

- **Unit tests**: Config loading, DownloadTask state machine, CacheManager eviction logic, WebSocketManager add/remove.
- **Route tests**: FastAPI `TestClient` with mocked `ExhentaiAPI`. Each route gets its own test file mirroring `routes/`.
- **Integration tests**: Full lifespan test with mocked HTTP responses. Submit download → verify progress events on WebSocket → verify files on disk.
- **No real network calls in tests.** All ExHentai interactions are mocked.

## Non-Goals (Explicitly Excluded)

- **Authentication**: No auth layer for the daemon. It binds to localhost only. Remote access auth belongs to a future Web frontend spec.
- **Multi-user**: Single user, single ExHentai session.
- **Database**: No SQLite/PostgreSQL. JSON files are sufficient for personal use.
- **Horizontal scaling**: Single process, single machine.
- **Image format conversion**: Images saved as-is from ExHentai.
