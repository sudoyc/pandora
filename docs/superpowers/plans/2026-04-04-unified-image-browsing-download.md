# Unified Image Browsing & Download System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign pandora-daemon's image handling into a unified image cache with proxy/prefetch, plus a complete offline gallery download system (library).

**Architecture:** All image requests (thumbnails, covers, full-size pages) are proxied through the daemon and cached in a unified disk pool (`~/.cache/pandora/images/`). An `ImageService` coordinates caching, page resolution, and background prefetching. The `DownloadManager` produces self-contained offline gallery clones with metadata, covers, thumbnails, and full-size pages. `GalleryDetail` gains a `thumb_urls` field for page thumbnail image URLs.

**Tech Stack:** Python, FastAPI, httpx, BeautifulSoup4, pytest, asyncio

---

## File Structure

| File | Responsibility |
|------|---------------|
| `exhentai_api/models/gallery.py` | Add `thumb_urls` field to `GalleryDetail` |
| `exhentai_api/parsers/gallery_detail.py` | Extract thumbnail image URLs alongside viewer URLs |
| `pandora_daemon/config.py` | New `CacheConfig` fields for unified cache + prefetch |
| `pandora_daemon/cache.py` | Rewrite: unified image cache (`get_image`/`put_image`/`evict_images`) |
| `pandora_daemon/image_service.py` | **New**: image proxy, page resolution, prefetching |
| `pandora_daemon/state.py` | Add `ImageService` to `AppState` |
| `pandora_daemon/dependencies.py` | Add `get_image_service` |
| `pandora_daemon/app.py` | Create `ImageService` in lifespan, shutdown on exit |
| `pandora_daemon/download.py` | Rewrite: produce complete offline directories |
| `pandora_daemon/routes/browse.py` | Replace `/api/thumb` with `/api/image/proxy` |
| `pandora_daemon/routes/gallery.py` | Add `GET /page/{page}`, `POST /prefetch` |

---

### Task 1: Add `thumb_urls` to GalleryDetail and update parser

**Files:**
- Modify: `exhentai_api/models/gallery.py`
- Modify: `exhentai_api/parsers/gallery_detail.py`
- Modify: `tests/exhentai_api/data/gallery_detail.html`
- Modify: `tests/exhentai_api/test_parser_gallery_detail.py`

- [ ] **Step 1: Update the mock HTML to include `gdtl` elements with thumbnail image URLs**

Add a `<div id="gdt">` section to `tests/exhentai_api/data/gallery_detail.html` with `gdtl` class elements that contain both viewer links (`<a href="/s/...">`) and thumbnail images (`<img src="...">`).

Insert before the `<table class="ptt">` line:

```html
    <div id="gdt">
        <div class="gdtl"><a href="https://exhentai.org/s/imgkey1/12345-1"><img src="https://exhentai.org/t/thumb1.jpg" /></a></div>
        <div class="gdtl"><a href="https://exhentai.org/s/imgkey2/12345-2"><img src="https://exhentai.org/t/thumb2.jpg" /></a></div>
        <div class="gdtl"><a href="https://exhentai.org/s/imgkey3/12345-3"><img src="https://exhentai.org/t/thumb3.jpg" /></a></div>
    </div>
```

- [ ] **Step 2: Write the failing test**

Add assertions for `thumb_urls` in `tests/exhentai_api/test_parser_gallery_detail.py`:

```python
def test_parse_gallery_detail_thumb_urls():
    html_path = Path(__file__).parent / "data" / "gallery_detail.html"
    html = html_path.read_text()

    detail = parse_gallery_detail(html, "12345", "abcdef1234")

    assert detail.thumb_urls == [
        "https://exhentai.org/t/thumb1.jpg",
        "https://exhentai.org/t/thumb2.jpg",
        "https://exhentai.org/t/thumb3.jpg",
    ]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/exhentai_api/test_parser_gallery_detail.py::test_parse_gallery_detail_thumb_urls -v`
Expected: FAIL (AttributeError: GalleryDetail has no attribute 'thumb_urls')

- [ ] **Step 4: Add `thumb_urls` field to GalleryDetail**

In `exhentai_api/models/gallery.py`, add after the `preview_urls` field:

```python
    thumb_urls: List[str] = field(default_factory=list)
```

- [ ] **Step 5: Update parser to extract thumbnail image URLs**

In `exhentai_api/parsers/gallery_detail.py`, add thumb_urls extraction after the `preview_urls` block (after line 92):

```python
    thumb_urls = []
    for gdt in soup.find_all(class_=["gdtm", "gdtl"]):
        a_tag = gdt.find("a")
        if a_tag:
            img_tag = a_tag.find("img")
            if img_tag and img_tag.get("src"):
                thumb_urls.append(img_tag.get("src"))
            elif "gdtm" == gdt.get("class", [""])[0]:
                # gdtm uses background-image sprite
                inner_div = gdt.find("div")
                if inner_div:
                    style = inner_div.get("style", "")
                    bg_match = re.search(r"url\((.+?)\)", style)
                    if bg_match:
                        thumb_urls.append(bg_match.group(1))
```

And add `thumb_urls=thumb_urls,` to the `GalleryDetail(...)` constructor call at the end.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/exhentai_api/test_parser_gallery_detail.py -v`
Expected: ALL PASS

- [ ] **Step 7: Run all existing tests to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add exhentai_api/models/gallery.py exhentai_api/parsers/gallery_detail.py tests/exhentai_api/
git commit -m "feat: add thumb_urls to GalleryDetail and parser"
```

---

### Task 2: Rewrite CacheConfig and CacheManager for unified image cache

**Files:**
- Modify: `pandora_daemon/config.py`
- Rewrite: `pandora_daemon/cache.py`
- Rewrite: `tests/pandora_daemon/test_cache.py`

- [ ] **Step 1: Write the failing tests for the new CacheManager**

Replace entire `tests/pandora_daemon/test_cache.py`:

```python
"""Tests for pandora_daemon.cache module — unified image cache."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from pandora_daemon.cache import CacheManager
from pandora_daemon.config import CacheConfig


def make_config(tmp_path, image_max_size_mb: int = 2048, gallery_ttl_seconds: int = 300) -> CacheConfig:
    return CacheConfig(
        image_dir=str(tmp_path / "images"),
        image_max_size_mb=image_max_size_mb,
        gallery_ttl_seconds=gallery_ttl_seconds,
    )


class TestImageCache:
    """Unified disk-based image cache tests."""

    @pytest.mark.asyncio
    async def test_image_miss_returns_none(self, tmp_path):
        config = make_config(tmp_path)
        cache = CacheManager(config)

        result = await cache.get_image("https://example.com/unknown.jpg")

        assert result is None

    @pytest.mark.asyncio
    async def test_image_put_and_get(self, tmp_path):
        config = make_config(tmp_path)
        cache = CacheManager(config)

        url = "https://example.com/image.jpg"
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100

        await cache.put_image(url, data)
        result = await cache.get_image(url)

        assert result == data

    @pytest.mark.asyncio
    async def test_image_different_urls_different_files(self, tmp_path):
        config = make_config(tmp_path)
        cache = CacheManager(config)

        await cache.put_image("https://example.com/a.jpg", b"aaa")
        await cache.put_image("https://example.com/b.png", b"bbb")

        assert await cache.get_image("https://example.com/a.jpg") == b"aaa"
        assert await cache.get_image("https://example.com/b.png") == b"bbb"

    @pytest.mark.asyncio
    async def test_image_eviction(self, tmp_path):
        config = make_config(tmp_path, image_max_size_mb=0)
        cache = CacheManager(config)

        for i in range(3):
            await cache.put_image(f"https://example.com/img{i}.jpg", b"x" * 1024)

        image_dir = tmp_path / "images"
        assert len(list(image_dir.iterdir())) == 3

        await cache.evict_images()

        assert len(list(image_dir.iterdir())) == 0

    @pytest.mark.asyncio
    async def test_ext_from_url(self, tmp_path):
        """Extension is derived from the URL path."""
        config = make_config(tmp_path)
        cache = CacheManager(config)

        await cache.put_image("https://cdn.example.com/image.png?token=abc", b"pngdata")
        # Verify file was created with .png extension
        files = list((tmp_path / "images").iterdir())
        assert len(files) == 1
        assert files[0].suffix == ".png"


class TestGalleryCache:
    """In-memory gallery detail cache with TTL tests (unchanged behavior)."""

    def test_gallery_cache_miss(self, tmp_path):
        config = make_config(tmp_path)
        cache = CacheManager(config)

        result = cache.get_gallery("12345", "abc123")

        assert result is None

    def test_gallery_cache_put_and_get(self, tmp_path):
        config = make_config(tmp_path)
        cache = CacheManager(config)

        detail = SimpleNamespace(gid="12345", token="abc123", title="Test Gallery")
        cache.put_gallery(detail)
        result = cache.get_gallery("12345", "abc123")

        assert result is detail

    def test_gallery_cache_ttl_expiry(self, tmp_path):
        config = make_config(tmp_path, gallery_ttl_seconds=300)
        cache = CacheManager(config)

        detail = SimpleNamespace(gid="99999", token="deadbeef", title="Expired Gallery")
        cache.put_gallery(detail)

        key = f"{detail.gid}:{detail.token}"
        existing_detail, _ = cache._gallery_cache[key]
        cache._gallery_cache[key] = (existing_detail, time.time() - 1)

        result = cache.get_gallery("99999", "deadbeef")

        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_cache.py -v`
Expected: FAIL (CacheConfig missing `image_dir`, CacheManager missing `get_image`)

- [ ] **Step 3: Update CacheConfig in config.py**

Replace the existing `CacheConfig` class in `pandora_daemon/config.py`:

```python
@dataclass
class CacheConfig:
    """Cache settings."""

    image_dir: str = "~/.cache/pandora/images"
    image_max_size_mb: int = 2048
    gallery_ttl_seconds: int = 300
    prefetch_ahead: int = 3
    prefetch_behind: int = 1
```

Update `load_config()` — replace the cache_data section:

```python
    cache_data = data.get("cache", {})
    cache = CacheConfig(
        image_dir=cache_data.get("image_dir", "~/.cache/pandora/images"),
        image_max_size_mb=cache_data.get("image_max_size_mb", 2048),
        gallery_ttl_seconds=cache_data.get("gallery_ttl_seconds", 300),
        prefetch_ahead=cache_data.get("prefetch_ahead", 3),
        prefetch_behind=cache_data.get("prefetch_behind", 1),
    )
```

Update `to_public_dict()` — replace the cache section:

```python
            "cache": {
                "image_dir": self.cache.image_dir,
                "image_max_size_mb": self.cache.image_max_size_mb,
                "gallery_ttl_seconds": self.cache.gallery_ttl_seconds,
                "prefetch_ahead": self.cache.prefetch_ahead,
                "prefetch_behind": self.cache.prefetch_behind,
            },
```

- [ ] **Step 4: Rewrite CacheManager in cache.py**

Replace entire `pandora_daemon/cache.py`:

```python
"""Cache manager for pandora-daemon.

Provides two cache layers:
- Disk-based unified image cache: SHA256(URL) -> file, with LRU eviction.
- In-memory gallery detail cache: (gid, token) -> detail with TTL expiry.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from pandora_daemon.config import CacheConfig


def _ext_from_url(url: str) -> str:
    """Derive file extension from URL path. Falls back to '.jpg'."""
    # Strip query string and fragment
    path = url.split("?")[0].split("#")[0]
    match = re.search(r"\.([a-zA-Z]{3,4})$", path)
    if match:
        return f".{match.group(1).lower()}"
    return ".jpg"


class CacheManager:
    """Manages unified image cache and gallery detail cache."""

    def __init__(self, config: CacheConfig) -> None:
        self._config = config
        self._image_dir = Path(config.image_dir).expanduser()
        self._image_dir.mkdir(parents=True, exist_ok=True)
        self._max_bytes = config.image_max_size_mb * 1024 * 1024
        self._ttl = config.gallery_ttl_seconds
        self._gallery_cache: dict[str, tuple] = {}

    def _image_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()
        ext = _ext_from_url(url)
        return self._image_dir / f"{h}{ext}"

    async def get_image(self, url: str) -> bytes | None:
        path = self._image_path(url)
        if path.exists():
            return path.read_bytes()
        return None

    async def put_image(self, url: str, data: bytes) -> None:
        path = self._image_path(url)
        path.write_bytes(data)

    async def evict_images(self) -> None:
        if not self._image_dir.exists():
            return
        files = sorted(self._image_dir.iterdir(), key=lambda p: p.stat().st_atime)
        total = sum(f.stat().st_size for f in files)
        while total > self._max_bytes and files:
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink()

    def get_gallery(self, gid: str, token: str):
        key = f"{gid}:{token}"
        entry = self._gallery_cache.get(key)
        if entry is None:
            return None
        detail, expires_at = entry
        if time.time() > expires_at:
            del self._gallery_cache[key]
            return None
        return detail

    def put_gallery(self, detail) -> None:
        key = f"{detail.gid}:{detail.token}"
        self._gallery_cache[key] = (detail, time.time() + self._ttl)
```

- [ ] **Step 5: Update app.py CacheManager constructor call**

In `pandora_daemon/app.py`, the existing line `cache = CacheManager(config.cache)` remains valid since the constructor signature is unchanged.

- [ ] **Step 6: Run cache tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_cache.py -v`
Expected: ALL PASS

- [ ] **Step 7: Fix broken config tests**

Run: `uv run pytest tests/pandora_daemon/test_config.py -v`

If any config tests reference old fields (`thumb_dir`, `thumb_max_size_mb`), update them to use `image_dir`, `image_max_size_mb`, `prefetch_ahead`, `prefetch_behind`.

- [ ] **Step 8: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: Some browse route tests may fail (they reference `get_thumb`/`put_thumb`). That's expected — we'll fix those in Task 6. All cache and config tests should PASS.

- [ ] **Step 9: Commit**

```bash
git add pandora_daemon/config.py pandora_daemon/cache.py tests/pandora_daemon/test_cache.py
git commit -m "feat: rewrite CacheManager for unified image cache"
```

---

### Task 3: Create ImageService

**Files:**
- Create: `pandora_daemon/image_service.py`
- Create: `tests/pandora_daemon/test_image_service.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/pandora_daemon/test_image_service.py`:

```python
"""Tests for pandora_daemon.image_service module."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pandora_daemon.config import CacheConfig
from pandora_daemon.image_service import ImageService


@pytest.fixture
def cache_config(tmp_path):
    return CacheConfig(
        image_dir=str(tmp_path / "images"),
        image_max_size_mb=2048,
        gallery_ttl_seconds=300,
        prefetch_ahead=3,
        prefetch_behind=1,
    )


@pytest.fixture
def mock_api():
    api = MagicMock()
    api.client = MagicMock()
    return api


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get_image = AsyncMock(return_value=None)
    cache.put_image = AsyncMock()
    cache.get_gallery = MagicMock(return_value=None)
    cache.put_gallery = MagicMock()
    return cache


class TestProxyImage:
    @pytest.mark.asyncio
    async def test_proxy_cache_hit(self, mock_api, mock_cache, cache_config):
        mock_cache.get_image = AsyncMock(return_value=b"cached_bytes")
        svc = ImageService(mock_api, mock_cache, cache_config)

        result = await svc.proxy_image("https://example.com/img.jpg")

        assert result == b"cached_bytes"
        mock_cache.get_image.assert_awaited_once_with("https://example.com/img.jpg")

    @pytest.mark.asyncio
    async def test_proxy_cache_miss_fetches(self, mock_api, mock_cache, cache_config):
        mock_cache.get_image = AsyncMock(return_value=None)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = b"fetched_bytes"
        mock_api.client.session.get = AsyncMock(return_value=resp)

        svc = ImageService(mock_api, mock_cache, cache_config)
        result = await svc.proxy_image("https://example.com/img.jpg")

        assert result == b"fetched_bytes"
        mock_cache.put_image.assert_awaited_once_with("https://example.com/img.jpg", b"fetched_bytes")


class TestGetPageImage:
    @pytest.mark.asyncio
    async def test_page_image_cached(self, mock_api, mock_cache, cache_config):
        """When the resolved CDN URL is cached, return directly."""
        svc = ImageService(mock_api, mock_cache, cache_config)
        # Pre-populate the page URL index
        svc._page_url_cache["123:1"] = "https://cdn.example.com/full.jpg"
        mock_cache.get_image = AsyncMock(return_value=b"page_bytes")

        result = await svc.get_page_image("123", "abc", 1)

        assert result == b"page_bytes"
        mock_cache.get_image.assert_awaited_once_with("https://cdn.example.com/full.jpg")

    @pytest.mark.asyncio
    async def test_page_image_not_cached(self, mock_api, mock_cache, cache_config):
        """When not cached, resolve viewer URL, fetch image, cache it."""
        detail = MagicMock()
        detail.preview_urls = ["https://exhentai.org/s/imgkey1/123-1"]
        mock_cache.get_gallery = MagicMock(return_value=detail)

        # Mock viewer HTML fetch
        viewer_html = '<html><body><img id="img" src="https://cdn.example.com/full.jpg" /><script>nl(\'nltoken\')</script></body></html>'
        mock_api.client.get_html = AsyncMock(return_value=viewer_html)

        # Mock image fetch
        mock_cache.get_image = AsyncMock(return_value=None)
        img_resp = MagicMock()
        img_resp.raise_for_status = MagicMock()
        img_resp.content = b"image_data"
        mock_api.client.session.get = AsyncMock(return_value=img_resp)

        svc = ImageService(mock_api, mock_cache, cache_config)
        result = await svc.get_page_image("123", "abc", 1)

        assert result == b"image_data"
        mock_cache.put_image.assert_awaited_once_with("https://cdn.example.com/full.jpg", b"image_data")
        assert svc._page_url_cache["123:1"] == "https://cdn.example.com/full.jpg"


class TestPrefetch:
    @pytest.mark.asyncio
    async def test_prefetch_schedules_tasks(self, mock_api, mock_cache, cache_config):
        """Prefetch should schedule background tasks for surrounding pages."""
        detail = MagicMock()
        detail.preview_urls = [f"https://exhentai.org/s/key{i}/123-{i+1}" for i in range(10)]
        mock_cache.get_gallery = MagicMock(return_value=detail)

        svc = ImageService(mock_api, mock_cache, cache_config)

        # Mock get_page_image to avoid actual fetching
        svc.get_page_image = AsyncMock(return_value=b"data")

        await svc.prefetch("123", "abc", current_page=5, total_pages=10)

        # With prefetch_behind=1, prefetch_ahead=3: pages 4, 6, 7, 8
        # Wait briefly for tasks to start
        await asyncio.sleep(0.05)

        # Check that tasks were created for the expected pages
        expected_keys = {"123:4", "123:6", "123:7", "123:8"}
        actual_keys = set(svc._prefetch_tasks.keys())
        assert expected_keys.issubset(actual_keys)

        await svc.shutdown()

    @pytest.mark.asyncio
    async def test_prefetch_clamps_to_bounds(self, mock_api, mock_cache, cache_config):
        """Prefetch range is clamped to [1, total_pages]."""
        detail = MagicMock()
        detail.preview_urls = [f"https://exhentai.org/s/key{i}/123-{i+1}" for i in range(5)]
        mock_cache.get_gallery = MagicMock(return_value=detail)

        svc = ImageService(mock_api, mock_cache, cache_config)
        svc.get_page_image = AsyncMock(return_value=b"data")

        # Page 1 with prefetch_behind=1 should not go below 1
        await svc.prefetch("123", "abc", current_page=1, total_pages=5)
        await asyncio.sleep(0.05)

        # Should NOT have key "123:0"
        assert "123:0" not in svc._prefetch_tasks

        await svc.shutdown()


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_cancels_prefetch(self, mock_api, mock_cache, cache_config):
        svc = ImageService(mock_api, mock_cache, cache_config)

        # Create a never-completing fake task
        async def slow():
            await asyncio.sleep(999)

        task = asyncio.create_task(slow())
        svc._prefetch_tasks["123:1"] = task

        await svc.shutdown()

        assert task.cancelled()
        assert len(svc._prefetch_tasks) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_image_service.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'pandora_daemon.image_service')

- [ ] **Step 3: Implement ImageService**

Create `pandora_daemon/image_service.py`:

```python
"""Image service for pandora-daemon.

Coordinates image proxy, caching, page resolution, and prefetching.
"""
from __future__ import annotations

import asyncio

from exhentai_api.parsers.image import parse_image_viewer
from pandora_daemon.cache import CacheManager
from pandora_daemon.config import CacheConfig


class ImageService:
    """Proxies all image requests through cache with background prefetch."""

    def __init__(self, api, cache: CacheManager, config: CacheConfig) -> None:
        self._api = api
        self._cache = cache
        self._config = config
        self._prefetch_tasks: dict[str, asyncio.Task] = {}
        self._page_url_cache: dict[str, str] = {}  # "{gid}:{page}" -> image_url
        self._semaphore = asyncio.Semaphore(4)

    async def proxy_image(self, url: str) -> bytes:
        """Generic image proxy with caching."""
        cached = await self._cache.get_image(url)
        if cached is not None:
            return cached

        resp = await self._api.client.session.get(url)
        resp.raise_for_status()
        data = resp.content
        await self._cache.put_image(url, data)
        return data

    async def get_page_image(self, gid: str, token: str, page: int) -> bytes:
        """Get full-size image for a gallery page. Cache-first."""
        # Check if we already know the CDN URL for this page
        page_key = f"{gid}:{page}"
        known_url = self._page_url_cache.get(page_key)
        if known_url:
            cached = await self._cache.get_image(known_url)
            if cached is not None:
                return cached

        # Resolve the viewer URL from gallery detail
        detail = self._cache.get_gallery(gid, token)
        if detail is None:
            detail = await self._api.get_gallery_details(gid, token)
            self._cache.put_gallery(detail)

        page_idx = page - 1
        if page_idx < 0 or page_idx >= len(detail.preview_urls):
            raise ValueError(f"Page {page} out of range (1-{len(detail.preview_urls)})")

        viewer_url = detail.preview_urls[page_idx]

        # Fetch and parse the viewer page to get the CDN image URL
        html = await self._api.client.get_html(viewer_url)
        image_url, nl = parse_image_viewer(html)

        if not image_url:
            raise RuntimeError(f"Could not resolve image URL for page {page}")

        # Cache the CDN URL mapping
        self._page_url_cache[page_key] = image_url

        # Check if the image is already cached (maybe by a different code path)
        cached = await self._cache.get_image(image_url)
        if cached is not None:
            return cached

        # Fetch the actual image
        resp = await self._api.client.session.get(image_url)
        resp.raise_for_status()
        data = resp.content
        await self._cache.put_image(image_url, data)
        return data

    async def prefetch(self, gid: str, token: str, current_page: int, total_pages: int) -> None:
        """Schedule background prefetch for pages around current_page."""
        start = max(1, current_page - self._config.prefetch_behind)
        end = min(total_pages, current_page + self._config.prefetch_ahead)

        for p in range(start, end + 1):
            if p == current_page:
                continue
            page_key = f"{gid}:{p}"
            # Skip if already cached or already being prefetched
            if page_key in self._page_url_cache:
                known_url = self._page_url_cache[page_key]
                cached = await self._cache.get_image(known_url)
                if cached is not None:
                    continue
            if page_key in self._prefetch_tasks and not self._prefetch_tasks[page_key].done():
                continue

            task = asyncio.create_task(self._prefetch_page(gid, token, p))
            self._prefetch_tasks[page_key] = task

    async def _prefetch_page(self, gid: str, token: str, page: int) -> None:
        """Prefetch a single page (fire-and-forget)."""
        async with self._semaphore:
            try:
                await self.get_page_image(gid, token, page)
            except Exception:
                pass  # Prefetch failures are silently ignored

    async def shutdown(self) -> None:
        """Cancel all in-flight prefetch tasks."""
        for task in self._prefetch_tasks.values():
            task.cancel()
        if self._prefetch_tasks:
            await asyncio.gather(*self._prefetch_tasks.values(), return_exceptions=True)
        self._prefetch_tasks.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_image_service.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/image_service.py tests/pandora_daemon/test_image_service.py
git commit -m "feat: create ImageService with proxy, page resolution, and prefetch"
```

---

### Task 4: Wire ImageService into AppState, dependencies, and lifespan

**Files:**
- Modify: `pandora_daemon/state.py`
- Modify: `pandora_daemon/dependencies.py`
- Modify: `pandora_daemon/app.py`

- [ ] **Step 1: Update AppState**

In `pandora_daemon/state.py`, add the import and field:

```python
from pandora_daemon.image_service import ImageService
```

Add to the `AppState` dataclass after the `cache` field:

```python
    image_service: ImageService
```

- [ ] **Step 2: Update dependencies**

In `pandora_daemon/dependencies.py`, add:

```python
from pandora_daemon.image_service import ImageService

def get_image_service(state: AppState = Depends(get_state)) -> ImageService:
    return state.image_service
```

- [ ] **Step 3: Update lifespan in app.py**

In `pandora_daemon/app.py`, add import:

```python
from pandora_daemon.image_service import ImageService
```

In the `lifespan` function, after creating `cache` and before creating `downloads`, add:

```python
    image_service = ImageService(api=api, cache=cache, config=config.cache)
```

Update the `AppState` constructor to include:

```python
    state = AppState(
        config=config, config_path=config_path,
        client=client, api=api,
        downloads=downloads, cache=cache,
        image_service=image_service, ws=ws,
    )
```

In the shutdown section (after `yield`), add before `await api.aclose()`:

```python
    await image_service.shutdown()
```

- [ ] **Step 4: Run tests to check for breakage**

Run: `uv run pytest tests/ -v`

Some existing tests that create `AppState` mocks may need to include `image_service`. Fix any failures by adding `state.image_service = MagicMock()` to test helpers.

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/state.py pandora_daemon/dependencies.py pandora_daemon/app.py
git commit -m "feat: wire ImageService into AppState and lifespan"
```

---

### Task 5: Add image proxy route and replace `/api/thumb`

**Files:**
- Modify: `pandora_daemon/routes/browse.py`
- Rewrite: `tests/pandora_daemon/test_routes_browse.py` (thumb proxy tests)

- [ ] **Step 1: Write failing tests for the new proxy endpoint**

In `tests/pandora_daemon/test_routes_browse.py`, replace the `TestThumbProxy` class with:

```python
class TestImageProxy:
    def test_image_proxy_cached(self):
        """When cache has the image, return it without fetching."""
        mock_api = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.proxy_image = AsyncMock(return_value=b"\xff\xd8\xff\xe0cached")

        app = _make_app(mock_api, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/image/proxy?url=https://example.com/img.jpg")

        assert response.status_code == 200
        assert response.content == b"\xff\xd8\xff\xe0cached"
        mock_image_service.proxy_image.assert_awaited_once_with("https://example.com/img.jpg")

    def test_image_proxy_missing_url(self):
        """Request without url parameter returns 422."""
        mock_api = MagicMock()
        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/image/proxy")

        assert response.status_code == 422
```

Update the `_make_app` helper to accept `mock_image_service`:

```python
def _make_app(mock_api, mock_cache=None, mock_image_service=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.api = mock_api
    state.cache = mock_cache or MagicMock()
    state.image_service = mock_image_service or MagicMock()
    app.state.pandora = state
    return app
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_browse.py::TestImageProxy -v`
Expected: FAIL (404 — endpoint doesn't exist yet)

- [ ] **Step 3: Replace `/api/thumb` with `/api/image/proxy` in browse.py**

In `pandora_daemon/routes/browse.py`:

Add import:
```python
from pandora_daemon.dependencies import get_api, get_cache, get_image_service
```

Replace the existing `thumb_proxy` function:

```python
@router.get("/image/proxy")
async def image_proxy(url: str, image_service=Depends(get_image_service)):
    """Proxy any image URL through the local cache."""
    data = await image_service.proxy_image(url)
    # Determine content type from URL extension
    lower_url = url.lower()
    if lower_url.endswith(".png"):
        media_type = "image/png"
    elif lower_url.endswith(".gif"):
        media_type = "image/gif"
    elif lower_url.endswith(".webp"):
        media_type = "image/webp"
    else:
        media_type = "image/jpeg"
    return Response(content=data, media_type=media_type)
```

Remove the old `get_cache` import if no longer used in this file (other routes still use it, so keep it if needed). Remove old `thumb_proxy` function.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_browse.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/routes/browse.py tests/pandora_daemon/test_routes_browse.py
git commit -m "feat: replace /api/thumb with /api/image/proxy using ImageService"
```

---

### Task 6: Add page image and prefetch routes

**Files:**
- Modify: `pandora_daemon/routes/gallery.py`
- Modify: `tests/pandora_daemon/test_routes_gallery.py`

- [ ] **Step 1: Write failing tests for the new endpoints**

Add to `tests/pandora_daemon/test_routes_gallery.py`:

```python
class TestPageImage:
    def test_page_image_returns_bytes(self):
        mock_api = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_page_image = AsyncMock(return_value=b"\xff\xd8page_image")

        app = _make_app(mock_api, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/page/5")

        assert response.status_code == 200
        assert response.content == b"\xff\xd8page_image"
        mock_image_service.get_page_image.assert_awaited_once_with("123", "abc", 5)

    def test_page_image_invalid_page(self):
        mock_api = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_page_image = AsyncMock(side_effect=ValueError("Page 99 out of range"))

        app = _make_app(mock_api, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/page/99")

        assert response.status_code == 400


class TestPrefetch:
    def test_prefetch_returns_ok(self):
        mock_api = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_gallery = MagicMock(return_value=MagicMock(pages=20))
        mock_image_service = MagicMock()
        mock_image_service.prefetch = AsyncMock()

        app = _make_app(mock_api, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/prefetch",
            json={"current_page": 5},
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_image_service.prefetch.assert_awaited_once()

    def test_prefetch_fetches_detail_on_cache_miss(self):
        mock_api = MagicMock()
        detail = _make_detail()
        detail.pages = 20
        mock_api.get_gallery_details = AsyncMock(return_value=detail)
        mock_cache = _make_cache_miss()
        mock_image_service = MagicMock()
        mock_image_service.prefetch = AsyncMock()

        app = _make_app(mock_api, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/prefetch",
            json={"current_page": 3},
        )

        assert response.status_code == 200
```

Update `_make_app` helper to accept `mock_image_service`:

```python
def _make_app(mock_api, mock_cache=None, mock_image_service=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.api = mock_api
    state.cache = mock_cache or MagicMock()
    state.image_service = mock_image_service or MagicMock()
    app.state.pandora = state
    return app
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_routes_gallery.py::TestPageImage -v`
Expected: FAIL (404)

- [ ] **Step 3: Implement the routes**

In `pandora_daemon/routes/gallery.py`, add imports:

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from pandora_daemon.dependencies import get_api, get_cache, get_image_service
```

Add request model:

```python
class PrefetchBody(BaseModel):
    current_page: int
```

Add new routes at the end of the file:

```python
@router.get("/{gid}/{token}/page/{page}")
async def get_page_image(gid: str, token: str, page: int, image_service=Depends(get_image_service)):
    """Return full-size image bytes for a gallery page."""
    try:
        data = await image_service.get_page_image(gid, token, page)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return Response(content=data, media_type="image/jpeg")


@router.post("/{gid}/{token}/prefetch")
async def prefetch_pages(
    gid: str,
    token: str,
    body: PrefetchBody,
    api=Depends(get_api),
    cache=Depends(get_cache),
    image_service=Depends(get_image_service),
):
    """Report current page and trigger background prefetch."""
    detail = await _get_detail(gid, token, api, cache)
    await image_service.prefetch(gid, token, body.current_page, detail.pages)
    return {"ok": True}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_routes_gallery.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/routes/gallery.py tests/pandora_daemon/test_routes_gallery.py
git commit -m "feat: add GET /page/{page} and POST /prefetch routes"
```

---

### Task 7: Rewrite DownloadManager for complete offline library

**Files:**
- Rewrite: `pandora_daemon/download.py`
- Rewrite: `tests/pandora_daemon/test_download.py`

- [ ] **Step 1: Write the failing tests**

Replace entire `tests/pandora_daemon/test_download.py`:

```python
"""Tests for pandora_daemon.download module — offline library builder."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pandora_daemon.config import DownloadConfig
from pandora_daemon.download import DownloadManager, DownloadTask, _sanitize_filename


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def download_config(tmp_path):
    return DownloadConfig(path=str(tmp_path / "downloads"), concurrency=2)


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "downloads.json"


@pytest.fixture
def mock_api():
    api = AsyncMock()
    detail = MagicMock()
    detail.title = "Test Gallery"
    detail.title_jpn = "Test JPN"
    detail.pages = 3
    detail.preview_pages = 1
    detail.preview_urls = [
        "https://exhentai.org/s/abc/123-1",
        "https://exhentai.org/s/def/123-2",
        "https://exhentai.org/s/ghi/123-3",
    ]
    detail.thumb_urls = [
        "https://exhentai.org/t/thumb1.jpg",
        "https://exhentai.org/t/thumb2.jpg",
        "https://exhentai.org/t/thumb3.jpg",
    ]
    detail.gid = "123"
    detail.token = "abc"
    detail.url = "https://exhentai.org/g/123/abc/"
    detail.category = "Manga"
    detail.uploader = "testuser"
    detail.cover_url = "https://exhentai.org/t/cover.jpg"
    detail.tags = {"parody": ["fate"]}
    detail.size = "50 MB"
    detail.posted = "2026-01-01"
    detail.favorite_slot = None
    detail.rating = 4.5
    detail.rating_count = 100
    detail.favorite_count = 50
    detail.torrent_count = 2
    detail.comments = []
    detail.comments_has_more = False
    api.get_gallery_details.return_value = detail
    return api


@pytest.fixture
def mock_ws():
    return AsyncMock()


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get_image = AsyncMock(return_value=None)
    cache.get_gallery = MagicMock(return_value=None)
    cache.put_gallery = MagicMock()
    return cache


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------

def test_sanitize_filename_removes_invalid_chars():
    assert _sanitize_filename('hello/world:foo<bar>baz') == "helloworldfoobarbaz"


def test_sanitize_filename_keeps_normal_chars():
    assert _sanitize_filename("test-gallery_123 (vol.1)") == "test-gallery_123 (vol.1)"


# ---------------------------------------------------------------------------
# DownloadTask
# ---------------------------------------------------------------------------

def test_download_task_creation():
    task = DownloadTask(
        gid="123",
        token="abc",
        title="My Gallery",
        total_pages=10,
        output_dir="/tmp/dl",
    )
    assert task.status == "queued"
    assert task.downloaded_pages == 0
    assert task.downloaded_thumbs == 0
    assert task.cover_downloaded is False
    assert task.metadata_saved is False
    assert task.error == ""
    assert task.created_at != ""
    assert task.preview_urls == []
    assert task.thumb_urls == []


def test_download_task_to_dict():
    task = DownloadTask(
        gid="42",
        token="xyz",
        title="Gallery 42",
        total_pages=5,
        output_dir="/tmp/42",
    )
    d = task.to_dict()
    assert isinstance(d, dict)
    assert d["gid"] == "42"
    assert d["downloaded_thumbs"] == 0
    assert d["cover_downloaded"] is False
    assert d["metadata_saved"] is False
    assert d["thumb_urls"] == []


# ---------------------------------------------------------------------------
# DownloadManager.submit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_creates_task(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)

    task = await manager.submit("123", "abc")

    assert task.gid == "123"
    assert task.token == "abc"
    assert task.title == "Test Gallery"
    assert task.total_pages == 3
    assert len(task.preview_urls) == 3
    assert len(task.thumb_urls) == 3
    assert task.status == "queued"


@pytest.mark.asyncio
async def test_submit_broadcasts_queued_event(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)

    await manager.submit("123", "abc")

    mock_ws.broadcast.assert_awaited_once()
    call_args = mock_ws.broadcast.call_args[0][0]
    assert call_args["event"] == "download_queued"
    assert call_args["gid"] == "123"


@pytest.mark.asyncio
async def test_submit_duplicate_rejected(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)

    await manager.submit("123", "abc")

    with pytest.raises(ValueError, match="123"):
        await manager.submit("123", "abc")


@pytest.mark.asyncio
async def test_submit_saves_state(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)

    await manager.submit("123", "abc")

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert "123" in data


# ---------------------------------------------------------------------------
# DownloadManager.status / cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_returns_all_tasks(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)
    await manager.submit("123", "abc")

    result = manager.status()
    assert len(result) == 1
    assert result[0].gid == "123"


@pytest.mark.asyncio
async def test_cancel_marks_cancelled(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)
    await manager.submit("123", "abc")

    result = await manager.cancel("123")

    assert result is True
    assert manager._tasks["123"].status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_nonexistent(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)

    result = await manager.cancel("999")

    assert result is False


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_and_load_state(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)
    await manager.submit("123", "abc")

    manager._save_state()

    data = json.loads(state_file.read_text())
    assert "123" in data
    assert data["123"]["gid"] == "123"
    assert data["123"]["title"] == "Test Gallery"


@pytest.mark.asyncio
async def test_load_state_requeues_pending(mock_api, mock_ws, mock_cache, download_config, state_file):
    task = DownloadTask(
        gid="456",
        token="def",
        title="Persisted Gallery",
        total_pages=5,
        output_dir="/tmp/456",
        status="queued",
        preview_urls=["https://exhentai.org/s/zzz/456-1"],
        thumb_urls=["https://exhentai.org/t/t1.jpg"],
    )
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"456": task.to_dict()}), encoding="utf-8")

    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)
    manager._load_state()

    assert "456" in manager._tasks
    assert manager._tasks["456"].title == "Persisted Gallery"


# ---------------------------------------------------------------------------
# start / shutdown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_creates_workers(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)
    await manager.start()

    try:
        assert len(manager._workers) == download_config.concurrency
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_saves_state(mock_api, mock_ws, mock_cache, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)
    await manager.start()
    await manager.submit("123", "abc")

    await manager.shutdown()

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert "123" in data


# ---------------------------------------------------------------------------
# Metadata writing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_metadata(mock_api, mock_ws, mock_cache, download_config, state_file):
    """_write_metadata creates a valid metadata.json in the output dir."""
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_cache, state_file)

    detail = mock_api.get_gallery_details.return_value
    output_dir = Path(download_config.path) / "123-Test Gallery"
    output_dir.mkdir(parents=True, exist_ok=True)

    manager._write_metadata(detail, str(output_dir))

    meta_path = output_dir / "metadata.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["gid"] == "123"
    assert meta["token"] == "abc"
    assert meta["url"] == "https://exhentai.org/g/123/abc/"
    assert meta["title"] == "Test Gallery"
    assert "downloaded_at" in meta
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/pandora_daemon/test_download.py -v`
Expected: FAIL (DownloadTask missing new fields, DownloadManager constructor changed)

- [ ] **Step 3: Rewrite DownloadManager**

Replace entire `pandora_daemon/download.py`:

```python
"""Download manager for pandora-daemon.

Produces complete offline gallery clones in the library directory.
Each gallery gets: metadata.json, cover, thumbs/, pages/.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from exhentai_api.parsers.image import parse_image_viewer

if TYPE_CHECKING:
    pass


def _sanitize_filename(name: str) -> str:
    """Remove characters that are invalid in file/directory names."""
    return re.sub(r'[\\/*?:"<>|]', "", name)


def _ext_from_url(url: str) -> str:
    """Derive file extension from URL path. Falls back to 'jpg'."""
    path = url.split("?")[0].split("#")[0]
    match = re.search(r"\.([a-zA-Z]{3,4})$", path)
    if match:
        return match.group(1).lower()
    return "jpg"


@dataclass
class DownloadTask:
    """Represents a single gallery download task."""

    gid: str
    token: str
    title: str
    total_pages: int
    output_dir: str
    status: str = "queued"
    downloaded_pages: int = 0
    downloaded_thumbs: int = 0
    cover_downloaded: bool = False
    metadata_saved: bool = False
    error: str = ""
    created_at: str = ""
    preview_urls: list[str] = field(default_factory=list)
    thumb_urls: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)


class DownloadManager:
    """Produces complete offline gallery clones with metadata, covers, thumbs, and pages."""

    def __init__(self, api, config, ws, cache, state_file: Path) -> None:
        self._api = api
        self._config = config
        self._ws = ws
        self._cache = cache
        self._state_file = state_file
        self._download_path = Path(config.path).expanduser()
        self._tasks: dict[str, DownloadTask] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []
        self._cancelled: set[str] = set()

    async def start(self) -> None:
        self._load_state()
        for task in list(self._tasks.values()):
            if task.status in ("queued", "downloading"):
                task.status = "queued"
                await self._queue.put(task.gid)

        for _ in range(self._config.concurrency):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)

    async def shutdown(self) -> None:
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        self._save_state()

    async def submit(self, gid: str, token: str) -> DownloadTask:
        existing = self._tasks.get(gid)
        if existing and existing.status in ("queued", "downloading"):
            raise ValueError(f"Gallery {gid} is already queued or downloading")

        detail = await self._api.get_gallery_details(gid, token)

        # Collect all preview URLs and thumb URLs across pages
        preview_urls = list(detail.preview_urls)
        thumb_urls = list(detail.thumb_urls)
        if detail.preview_pages > 1:
            import bs4
            for p in range(1, detail.preview_pages):
                page_url = f"{detail.url}?p={p}"
                html = await self._api.client.get_html(page_url)
                soup = bs4.BeautifulSoup(html, "html.parser")
                for gdt in soup.find_all(class_=["gdtm", "gdtl"]):
                    a_tag = gdt.find("a")
                    if a_tag and a_tag.get("href"):
                        preview_urls.append(a_tag.get("href"))
                    # Extract thumb URL
                    if a_tag:
                        img_tag = a_tag.find("img")
                        if img_tag and img_tag.get("src"):
                            thumb_urls.append(img_tag.get("src"))

        safe_title = _sanitize_filename(detail.title)
        output_dir = str(self._download_path / f"{gid}-{safe_title}")

        task = DownloadTask(
            gid=gid,
            token=token,
            title=detail.title,
            total_pages=detail.pages,
            output_dir=output_dir,
            preview_urls=preview_urls,
            thumb_urls=thumb_urls,
        )
        self._tasks[gid] = task
        await self._queue.put(gid)

        await self._ws.broadcast({"event": "download_queued", "gid": gid, "title": detail.title})
        self._save_state()
        return task

    async def cancel(self, gid: str) -> bool:
        task = self._tasks.get(gid)
        if task is None:
            return False

        self._cancelled.add(gid)
        task.status = "cancelled"
        await self._ws.broadcast({"event": "download_cancelled", "gid": gid})
        self._save_state()
        return True

    def status(self) -> list[DownloadTask]:
        return list(self._tasks.values())

    def _write_metadata(self, detail, output_dir: str) -> None:
        """Write metadata.json with complete gallery info."""
        meta = {
            "gid": detail.gid,
            "token": detail.token,
            "url": detail.url,
            "title": detail.title,
            "title_jpn": getattr(detail, "title_jpn", None),
            "category": detail.category,
            "uploader": detail.uploader,
            "cover_url": detail.cover_url,
            "tags": detail.tags,
            "pages": detail.pages,
            "size": detail.size,
            "posted": detail.posted,
            "rating": detail.rating,
            "rating_count": detail.rating_count,
            "favorite_count": detail.favorite_count,
            "favorite_slot": detail.favorite_slot,
            "torrent_count": detail.torrent_count,
            "comments": [
                {"id": c.id, "user": c.user, "comment": c.comment,
                 "score": c.score, "time": c.time}
                for c in detail.comments
            ] if detail.comments else [],
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        path = Path(output_dir) / "metadata.json"
        path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    async def _worker(self) -> None:
        while True:
            try:
                gid = await self._queue.get()
            except asyncio.CancelledError:
                return

            task = self._tasks.get(gid)
            if task is None:
                self._queue.task_done()
                continue

            if gid in self._cancelled or task.status == "cancelled":
                self._queue.task_done()
                continue

            task.status = "downloading"
            self._save_state()

            try:
                await self._download_gallery(task)
            except asyncio.CancelledError:
                if task.status == "downloading":
                    task.status = "queued"
                    self._save_state()
                self._queue.task_done()
                return
            except Exception as exc:
                task.status = "failed"
                task.error = str(exc)
                await self._ws.broadcast(
                    {"event": "download_error", "gid": gid, "error": str(exc)}
                )
                self._save_state()

            self._queue.task_done()

    async def _download_gallery(self, task: DownloadTask) -> None:
        """Download complete gallery: metadata, cover, thumbs, pages."""
        output_dir = Path(task.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        thumbs_dir = output_dir / "thumbs"
        thumbs_dir.mkdir(exist_ok=True)
        pages_dir = output_dir / "pages"
        pages_dir.mkdir(exist_ok=True)

        # 1. Write metadata
        if not task.metadata_saved:
            detail = await self._api.get_gallery_details(task.gid, task.token)
            self._write_metadata(detail, str(output_dir))
            task.metadata_saved = True
            self._save_state()

        # 2. Download cover
        if not task.cover_downloaded:
            detail = await self._api.get_gallery_details(task.gid, task.token)
            if detail.cover_url:
                try:
                    cover_data = await self._fetch_image(detail.cover_url)
                    ext = _ext_from_url(detail.cover_url)
                    (output_dir / f"cover.{ext}").write_bytes(cover_data)
                except Exception:
                    pass  # Cover failure is non-fatal
            task.cover_downloaded = True
            await self._ws.broadcast({"event": "download_progress", "gid": task.gid, "phase": "cover"})
            self._save_state()

        # 3. Download thumbnails
        for idx, thumb_url in enumerate(task.thumb_urls):
            if task.gid in self._cancelled:
                task.status = "cancelled"
                self._save_state()
                return

            page_num = idx + 1
            ext = _ext_from_url(thumb_url)
            dest = thumbs_dir / f"{page_num:04d}.{ext}"
            if not dest.exists():
                try:
                    data = await self._fetch_image(thumb_url)
                    dest.write_bytes(data)
                except Exception:
                    pass

            task.downloaded_thumbs = page_num
            await self._ws.broadcast({
                "event": "download_progress", "gid": task.gid,
                "phase": "thumbs", "page": page_num, "total": task.total_pages,
            })
            self._save_state()

        # 4. Download full-size pages
        for idx, viewer_url in enumerate(task.preview_urls):
            if task.gid in self._cancelled:
                task.status = "cancelled"
                self._save_state()
                return

            page_num = idx + 1

            # Check if already downloaded (resume support)
            existing = list(pages_dir.glob(f"{page_num:04d}.*"))
            if existing:
                task.downloaded_pages = page_num
                continue

            try:
                html = await self._api.client.get_html(viewer_url)
                image_url, _ = parse_image_viewer(html)
                if not image_url:
                    continue

                data = await self._fetch_image(image_url)
                ext = _ext_from_url(image_url)
                (pages_dir / f"{page_num:04d}.{ext}").write_bytes(data)
            except Exception as exc:
                task.error = f"Page {page_num}: {exc}"

            task.downloaded_pages = page_num
            await self._ws.broadcast({
                "event": "download_progress", "gid": task.gid,
                "phase": "pages", "page": page_num, "total": task.total_pages,
            })
            self._save_state()

        if task.gid not in self._cancelled:
            task.status = "completed"
            await self._ws.broadcast(
                {"event": "download_complete", "gid": task.gid, "path": task.output_dir}
            )
            self._save_state()

    async def _fetch_image(self, url: str) -> bytes:
        """Fetch image bytes, checking cache first."""
        cached = await self._cache.get_image(url)
        if cached is not None:
            return cached

        resp = await self._api.client.session.get(url)
        resp.raise_for_status()
        return resp.content

    def _save_state(self) -> None:
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {gid: task.to_dict() for gid, task in self._tasks.items()}
        self._state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_state(self) -> None:
        if not self._state_file.exists():
            return
        try:
            raw = self._state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            return
        for gid, task_dict in data.items():
            try:
                task = DownloadTask(**task_dict)
                self._tasks[gid] = task
            except Exception:
                continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/pandora_daemon/test_download.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add pandora_daemon/download.py tests/pandora_daemon/test_download.py
git commit -m "feat: rewrite DownloadManager for complete offline library"
```

---

### Task 8: Update app.py and download routes for new DownloadManager signature

**Files:**
- Modify: `pandora_daemon/app.py`
- Modify: `pandora_daemon/routes/downloads.py`
- Modify: `tests/pandora_daemon/test_routes_downloads.py`

- [ ] **Step 1: Update app.py DownloadManager constructor**

In `pandora_daemon/app.py`, the `lifespan` function creates `DownloadManager`. Update the call to pass `cache`:

```python
    downloads = DownloadManager(api=api, config=config.download, ws=ws, cache=cache, state_file=state_file)
```

- [ ] **Step 2: Update download route tests**

In `tests/pandora_daemon/test_routes_downloads.py`, update the `_make_app` and fixture setup to pass `cache` to DownloadManager if tests instantiate it directly. The route tests use mocks, so they likely only need `state.downloads` to be a MagicMock — verify they still pass.

Run: `uv run pytest tests/pandora_daemon/test_routes_downloads.py -v`

If they pass, no changes needed. If they fail, fix the mock setup.

- [ ] **Step 3: Run ALL tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

Fix any remaining failures from the CacheConfig field name changes, DownloadManager constructor changes, or AppState field additions.

- [ ] **Step 4: Commit**

```bash
git add pandora_daemon/app.py tests/
git commit -m "fix: update app lifespan and tests for new DownloadManager signature"
```

---

### Task 9: Fix remaining test breakage and final integration test

**Files:**
- Modify: various test files as needed
- Modify: `tests/pandora_daemon/test_integration.py`

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -v`

Identify and fix any remaining failures. Common issues:
- `test_config.py`: old field names (`thumb_dir` → `image_dir`, `thumb_max_size_mb` → `image_max_size_mb`)
- `test_routes_config.py`: config dict assertions referencing old field names
- `test_integration.py`: AppState or DownloadManager constructor changes
- Any test helper creating `AppState` without `image_service`

- [ ] **Step 2: Fix each broken test**

For each failure, update the test to match the new interfaces. Do not change production code to accommodate old tests.

- [ ] **Step 3: Add integration test for browse → prefetch → download flow**

Add to `tests/pandora_daemon/test_integration.py`:

```python
@pytest.mark.asyncio
async def test_image_service_and_download_share_cache(tmp_path):
    """Images cached by ImageService are reused by DownloadManager."""
    from pandora_daemon.config import CacheConfig, DownloadConfig
    from pandora_daemon.cache import CacheManager
    from pandora_daemon.image_service import ImageService

    cache_config = CacheConfig(
        image_dir=str(tmp_path / "images"),
        image_max_size_mb=100,
    )
    cache = CacheManager(cache_config)

    # Simulate ImageService caching an image
    url = "https://cdn.example.com/full.jpg"
    await cache.put_image(url, b"image_bytes")

    # DownloadManager's _fetch_image should find it
    result = await cache.get_image(url)
    assert result == b"image_bytes"
```

- [ ] **Step 4: Run ALL tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "fix: update all tests for unified image cache and library system"
```

---

## Verification

After all tasks: - ALL DONE (203 tests passing, 2026-04-04)

1. `uv run pytest tests/ -v` — ALL PASS (203 tests)
2. New API endpoints available:
   - `GET /api/image/proxy?url=...` — unified image proxy
   - `GET /api/gallery/{gid}/{token}/page/{page}` — full-size page image
   - `POST /api/gallery/{gid}/{token}/prefetch` — trigger prefetch
3. Download produces complete offline directory:
   ```
   ~/Downloads/pandora/{gid}-{title}/
     metadata.json  (with url field)
     cover.{ext}
     thumbs/0001.{ext} ...
     pages/0001.{ext} ...
   ```
4. Cache is unified: `~/.cache/pandora/images/` stores all image types
5. Prefetch works: reporting current page triggers background fetch of surrounding pages
