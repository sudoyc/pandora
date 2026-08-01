"""Provider-backed image caching and background page prefetching."""
from __future__ import annotations

import asyncio
import logging

from pandora_daemon.cache import CacheManager
from pandora_daemon.config import CacheConfig
from pandora_daemon.providers.contracts import GalleryProvider

logger = logging.getLogger(__name__)


class ImageService:
    """Caches provider media and manages bounded background page prefetches."""

    def __init__(
        self,
        provider: GalleryProvider,
        cache: CacheManager,
        config: CacheConfig,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._config = config
        self._prefetch_tasks: dict[str, asyncio.Task[None]] = {}

    def _media_cache_key(
        self,
        kind: str,
        gid: str,
        token: str,
        ordinal: int,
    ) -> str:
        return f"media:{self._provider.provider_id}:{kind}:{gid}:{token}:{ordinal}"

    def _page_cache_key(self, gid: str, token: str, page: int) -> str:
        return self._media_cache_key("page", gid, token, page)

    def _thumbnail_cache_key(self, gid: str, token: str, page: int) -> str:
        return self._media_cache_key("thumbnail", gid, token, page)

    async def _get_gallery_detail(self, gid: str, token: str) -> object:
        detail = self._cache.get_gallery(gid, token)
        if detail is not None:
            return detail

        detail = await self._provider.get_gallery_details(gid, token)
        self._cache.put_gallery(detail)
        return detail

    async def proxy_image(self, source: str) -> bytes:
        """Return a source image from cache or the configured provider."""
        cached = await self._cache.get_image(source)
        if cached is not None:
            return cached

        data = await self._provider.fetch_image(source)
        await self._cache.put_image(source, data)
        return data

    async def get_page_image(self, gid: str, token: str, page: int) -> bytes:
        """Return a full-size page image from cache or the configured provider."""
        cache_key = self._page_cache_key(gid, token, page)
        cached = await self._cache.get_image(cache_key)
        if cached is not None:
            return cached

        detail = await self._get_gallery_detail(gid, token)
        data = await self._provider.get_page_image(detail, page)
        await self._cache.put_image(cache_key, data)
        return data

    async def get_thumbnail(self, gid: str, token: str, page: int) -> bytes:
        """Return a page thumbnail from cache or the configured provider."""
        cache_key = self._thumbnail_cache_key(gid, token, page)
        cached = await self._cache.get_image(cache_key)
        if cached is not None:
            return cached

        detail = await self._get_gallery_detail(gid, token)
        data = await self._provider.get_thumbnail(detail, page)
        await self._cache.put_image(cache_key, data)
        return data

    async def prefetch(
        self,
        gid: str,
        token: str,
        current_page: int,
        total_pages: int,
    ) -> None:
        """Schedule uncached pages around the current page for background loading."""
        done_keys = [key for key, task in self._prefetch_tasks.items() if task.done()]
        for key in done_keys:
            del self._prefetch_tasks[key]

        start = max(1, current_page - self._config.prefetch_behind)
        end = min(total_pages, current_page + self._config.prefetch_ahead)

        for page in range(start, end + 1):
            if page == current_page:
                continue

            cache_key = self._page_cache_key(gid, token, page)
            task = self._prefetch_tasks.get(cache_key)
            if task is not None and not task.done():
                continue

            cached = await self._cache.get_image(cache_key)
            if cached is not None:
                continue

            self._prefetch_tasks[cache_key] = asyncio.create_task(
                self._prefetch_page(gid, token, page)
            )

    async def _prefetch_page(self, gid: str, token: str, page: int) -> None:
        """Load one page without exposing background failures to the caller."""
        try:
            await self.get_page_image(gid, token, page)
        except Exception as error:
            logger.debug("Prefetch failed for %s page %d: %s", gid, page, error)

    async def shutdown(self) -> None:
        """Cancel and await only outstanding prefetch work."""
        tasks = tuple(self._prefetch_tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._prefetch_tasks.clear()
