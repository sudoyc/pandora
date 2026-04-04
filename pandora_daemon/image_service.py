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
