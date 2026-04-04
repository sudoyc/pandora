# Unified Image Browsing & Download System Design

## Overview

Redesign pandora-daemon's image handling into two independent systems:

1. **Cache** — accelerates online browsing, all image types (full-size pages, thumbnails, covers), LRU eviction, ephemeral
2. **Library** — complete offline gallery clones, self-contained with metadata + all images, permanent

The daemon proxies **all** image requests (frontends never access exhentai directly) and supports server-side prefetching for smooth browsing.

## Architecture

```
Frontend (TUI / Web / CLI)
    │
    │  GET /api/image/proxy?url=...       (covers, thumbnails — known URLs)
    │  GET /api/gallery/{gid}/{token}/page/{page}  (full-size page images)
    │  POST /api/gallery/{gid}/{token}/prefetch     (report current page)
    │  POST /api/downloads                 (trigger full gallery download)
    │
pandora-daemon
    ├── ImageService (proxy, cache coordination, prefetch)
    ├── CacheManager (unified image cache)
    │     └── ~/.cache/pandora/images/{sha256}.{ext}
    └── DownloadManager (library builder)
          └── ~/Downloads/pandora/{gid}-{title}/
```

## System 1: Unified Image Cache

### Purpose

Accelerate all image loading during online browsing. Every image request from the frontend goes through daemon, which checks the cache before hitting exhentai.

### Storage

- **Location:** `~/.cache/pandora/images/`
- **Key:** `SHA256(source_url).{ext}` where ext is derived from the URL path (e.g., `.jpg` from `image.jpg?params=...`); falls back to `.jpg` if unrecognizable
- **Scope:** All image types — full-size gallery pages, page thumbnails, gallery covers, list thumbnails
- **Replaces:** The current separate `~/.cache/pandora/thumbs/` directory is merged into this unified pool

### Eviction

- LRU based on file access time (`st_atime`)
- Configurable max size (default 2GB)
- Eviction runs when cache exceeds the limit
- Images belonging to a gallery currently being downloaded are not evicted during that download

### CacheManager Interface

```python
class CacheManager:
    def __init__(self, config: CacheConfig) -> None: ...

    # Unified image cache
    async def get_image(self, url: str) -> bytes | None:
        """Return cached image bytes for url, or None."""

    async def put_image(self, url: str, data: bytes) -> None:
        """Store image bytes keyed by url."""

    async def evict_images(self) -> None:
        """LRU evict until total size is within limit."""

    # Gallery detail cache (unchanged, in-memory, TTL-based)
    def get_gallery(self, gid: str, token: str) -> GalleryDetail | None: ...
    def put_gallery(self, detail: GalleryDetail) -> None: ...
```

### CacheConfig Changes

```python
@dataclass
class CacheConfig:
    image_dir: str = "~/.cache/pandora/images"     # replaces thumb_dir
    image_max_size_mb: int = 2048                   # replaces thumb_max_size_mb (2GB default)
    gallery_ttl_seconds: int = 300                  # unchanged
    prefetch_ahead: int = 3                         # pages to prefetch forward
    prefetch_behind: int = 1                        # pages to prefetch backward
```

## System 2: Local Library (Download)

### Purpose

Create complete, self-contained offline clones of galleries. The downloaded data does not depend on network connectivity or the website being available. It is a standalone artifact.

### Directory Structure

```
~/Downloads/pandora/
  {gid}-{sanitized_title}/
    metadata.json           # Complete gallery metadata
    cover.jpg               # Gallery cover image
    thumbs/                 # Page thumbnails
      0001.jpg
      0002.jpg
      ...
    pages/                  # Full-size page images
      0001.jpg
      0002.png
      ...
```

### metadata.json Schema

Contains the complete `GalleryDetail` data plus the gallery URL for traceability:

```json
{
  "gid": "123456",
  "token": "abcdef1234",
  "url": "https://exhentai.org/g/123456/abcdef1234/",
  "title": "Gallery Title",
  "title_jpn": "Japanese Title",
  "category": "Manga",
  "uploader": "UploaderName",
  "cover_url": "https://exhentai.org/t/...",
  "tags": {
    "parody": ["tag1", "tag2"],
    "artist": ["artist1"]
  },
  "pages": 20,
  "size": "100 MB",
  "posted": "2026-01-01 12:00",
  "rating": 4.5,
  "rating_count": 100,
  "favorite_count": 50,
  "favorite_slot": null,
  "torrent_count": 2,
  "comments": [
    {
      "id": 1,
      "user": "user1",
      "comment": "text",
      "score": 10,
      "time": "2026-01-01 12:00"
    }
  ],
  "downloaded_at": "2026-04-04T12:00:00Z"
}
```

### Download Flow

```
POST /api/downloads {gid, token}

1. Fetch GalleryDetail (cache-first)
2. Create output directory: {gid}-{sanitized_title}/
3. Write metadata.json (GalleryDetail + url + downloaded_at)
4. Download cover image → cover.{ext}
5. Collect all page viewer URLs (paginate preview pages if needed)
6. For each page:
   a. Download page thumbnail → thumbs/{NNNN}.{ext}
   b. Full-size image: check cache first → hit: copy from cache → miss: fetch from exhentai
      → pages/{NNNN}.{ext}
   c. Broadcast progress via WebSocket
7. Mark task complete
```

Key behaviors:
- Cache is consulted during download: already-cached full-size pages are copied, not re-fetched
- After download completes, cached copies are free to be evicted by LRU
- If download is resumed after restart, already-downloaded files are skipped (check file existence)

### DownloadTask Changes

```python
@dataclass
class DownloadTask:
    gid: str
    token: str
    title: str
    total_pages: int
    output_dir: str
    status: str = "queued"          # queued|downloading|completed|failed|cancelled
    downloaded_pages: int = 0       # pages (full-size) completed
    downloaded_thumbs: int = 0      # thumbnails completed
    cover_downloaded: bool = False   # cover status
    metadata_saved: bool = False     # metadata status
    error: str = ""
    created_at: str = ""
    preview_urls: list[str] = field(default_factory=list)
```

### WebSocket Events

```json
{"event": "download_queued", "gid": "123", "title": "..."}
{"event": "download_progress", "gid": "123", "phase": "pages", "page": 5, "total": 20}
{"event": "download_progress", "gid": "123", "phase": "thumbs", "page": 5, "total": 20}
{"event": "download_progress", "gid": "123", "phase": "cover"}
{"event": "download_complete", "gid": "123", "path": "/path/to/gallery/"}
{"event": "download_error", "gid": "123", "error": "..."}
{"event": "download_cancelled", "gid": "123"}
```

## Page Thumbnail URLs

### Problem

The current `GalleryDetail.preview_urls` contains **viewer page links** (`/s/{imgkey}/{gid}-{page}`), not thumbnail image URLs. For the thumbnail grid in frontends (and for downloading thumbnails to the library), we need the actual thumbnail image URLs.

### Solution

Add a `thumb_urls: List[str]` field to `GalleryDetail`. The gallery detail parser already iterates over `.gdtm`/`.gdtl` elements to extract viewer links; it also needs to extract the thumbnail image URL from each element:

- `.gdtm` (medium thumbnails): the `<div>` inside has a `background-image` CSS property with the sprite URL and position
- `.gdtl` (large thumbnails): the `<img>` inside has a `src` attribute with the direct thumbnail URL

Both `preview_urls` (viewer links) and `thumb_urls` (thumbnail image URLs) are collected in parallel during gallery detail parsing. For multi-page preview pagination, the same HTML parsing extracts both.

This requires updating:
- `exhentai_api/models/gallery.py`: add `thumb_urls: List[str]` to `GalleryDetail`
- `exhentai_api/parsers/gallery_detail.py`: extract thumbnail image URLs alongside viewer URLs

## Image Proxy API

The daemon proxies **all** image requests. Frontends never access exhentai image CDN directly.

### Endpoints

#### `GET /api/image/proxy?url={url}`

Generic image proxy for images with known URLs (covers, thumbnails from gallery list, page thumbnails from gallery detail).

Flow:
1. Check `CacheManager.get_image(url)`
2. Cache hit → return bytes with appropriate Content-Type
3. Cache miss → fetch from exhentai via `api.client.session.get(url)` → store in cache → return bytes

Replaces the current `GET /api/thumb?url=...` endpoint.

#### `GET /api/gallery/{gid}/{token}/page/{page}`

Get full-size image for a specific page. This requires resolving the viewer URL first.

Flow:
1. Get GalleryDetail (cache-first) to obtain `preview_urls[page-1]` (the viewer URL)
2. Check if the resolved image URL is already cached (requires a secondary index: `{gid}:{page}` → `image_url`)
3. Cache miss: fetch viewer HTML → `parse_image_viewer(html)` → get CDN image URL → fetch image → cache by CDN URL → return bytes
4. Cache hit: return cached bytes

The secondary index (`{gid}:{page}` → `image_url`) maps gallery page numbers to their resolved CDN URLs, so we don't need to re-parse the viewer page every time. This is stored in-memory with the same TTL as gallery detail cache.

#### `POST /api/gallery/{gid}/{token}/prefetch`

Report the page the user is currently viewing. Daemon asynchronously prefetches surrounding pages.

Request body:
```json
{"current_page": 5}
```

Response: `{"ok": true}` (immediate, does not wait for prefetch)

Behavior:
1. Calculate prefetch range: `[current_page - prefetch_behind, current_page + prefetch_ahead]`
2. Skip pages already cached or already being prefetched
3. Spawn background asyncio tasks to fetch each page (same flow as `/page/{page}`)
4. Cap concurrent prefetch tasks (e.g., max 4 in-flight) to avoid flooding

## Prefetch Mechanism

### Design

Not a separate component. Implemented as a method on the daemon's image service layer that coordinates CacheManager and ExhentaiAPI.

```python
class ImageService:
    """Coordinates image proxy, caching, and prefetching."""

    def __init__(self, api: ExhentaiAPI, cache: CacheManager, config: CacheConfig):
        self._api = api
        self._cache = cache
        self._config = config
        self._prefetch_tasks: dict[str, asyncio.Task] = {}  # "{gid}:{page}" -> task
        self._page_url_cache: dict[str, str] = {}            # "{gid}:{page}" -> image_url
        self._semaphore = asyncio.Semaphore(4)                # max concurrent prefetches

    async def get_page_image(self, gid: str, token: str, page: int) -> bytes:
        """Get full-size image for a page. Cache-first."""
        ...

    async def prefetch(self, gid: str, token: str, current_page: int, total_pages: int) -> None:
        """Trigger background prefetch for pages around current_page."""
        ...

    async def proxy_image(self, url: str) -> bytes:
        """Generic image proxy with caching."""
        ...

    async def shutdown(self) -> None:
        """Cancel all in-flight prefetch tasks."""
        ...
```

### Prefetch Behavior

- Prefetch range: `[current_page - behind, current_page + ahead]`, clamped to `[1, total_pages]`
- Pages already cached or in-flight are skipped
- Each prefetch task respects the semaphore (max 4 concurrent)
- Prefetch tasks are fire-and-forget; failures are silently ignored (the page will be fetched on demand)
- When the user reports a new current_page, old prefetch tasks outside the new window are **not** cancelled (they're almost done anyway)

## Changes to Existing Code

### Files to Modify

| File | Change |
|------|--------|
| `pandora_daemon/config.py` | Replace `CacheConfig` fields: `image_dir`, `image_max_size_mb`, `prefetch_ahead`, `prefetch_behind` |
| `pandora_daemon/cache.py` | Rewrite: unified image pool (`get_image`/`put_image`/`evict_images`), remove old thumb methods |
| `pandora_daemon/download.py` | Rewrite: produce complete offline directory (metadata + cover + thumbs + pages), consult cache during download |
| `pandora_daemon/state.py` | Add `ImageService` to `AppState` |
| `pandora_daemon/dependencies.py` | Add `get_image_service` dependency |
| `pandora_daemon/app.py` | Create `ImageService` in lifespan, shut down on exit |
| `pandora_daemon/routes/browse.py` | Remove `GET /api/thumb`, replace with `/api/image/proxy` |
| `pandora_daemon/routes/gallery.py` | Add `GET /{gid}/{token}/page/{page}`, `POST /{gid}/{token}/prefetch` |

### Files to Create

| File | Purpose |
|------|---------|
| `pandora_daemon/image_service.py` | `ImageService` class: proxy, cache coordination, prefetch |

### Files to Delete

None. All changes are modifications.

## Error Handling

- Image fetch failure (CDN down, 403, etc.): return HTTP 502 to frontend with error detail
- Prefetch failure: silently ignored, page will be fetched on-demand when requested
- Download page failure: log per-page error, continue with remaining pages (existing behavior)
- Cache corruption (unreadable file): treat as cache miss, re-fetch

## Testing Strategy

- Unit tests for `CacheManager`: get/put/evict with unified image pool
- Unit tests for `ImageService`: proxy, page fetch, prefetch logic (mock API + cache)
- Unit tests for `DownloadManager`: metadata writing, cover download, cache consultation
- Route tests for new endpoints: `/api/image/proxy`, `/page/{page}`, `/prefetch`
- Integration test: browse → prefetch → download flow
