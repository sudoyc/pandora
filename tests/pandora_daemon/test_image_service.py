"""Tests for provider-backed image caching and prefetching."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from pandora_daemon.config import CacheConfig
from pandora_daemon.image_service import ImageService


class FakeProvider:
    """Plain provider fake with independently observable async media methods."""

    def __init__(self, provider_id: str = "alpha") -> None:
        self.provider_id = provider_id
        self.fetch_image = AsyncMock()
        self.get_gallery_details = AsyncMock()
        self.get_page_image = AsyncMock()
        self.get_thumbnail = AsyncMock()


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
def provider():
    return FakeProvider()


@pytest.fixture
def cache():
    result = MagicMock()
    result.get_image = AsyncMock(return_value=None)
    result.put_image = AsyncMock()
    result.get_gallery = MagicMock(return_value=None)
    result.put_gallery = MagicMock()
    return result


@pytest.fixture
def detail():
    return SimpleNamespace(gid="gallery", token="token")


class TestProxyImage:
    @pytest.mark.asyncio
    async def test_returns_cached_source_without_provider_fetch(
        self,
        provider,
        cache,
        cache_config,
    ):
        cache.get_image.return_value = b"cached-source"
        service = ImageService(provider, cache, cache_config)

        result = await service.proxy_image("cover-source")

        assert result == b"cached-source"
        cache.get_image.assert_awaited_once_with("cover-source")
        provider.fetch_image.assert_not_awaited()
        cache.put_image.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_fetches_and_caches_source_on_miss(self, provider, cache, cache_config):
        provider.fetch_image.return_value = b"fetched-source"
        service = ImageService(provider, cache, cache_config)

        result = await service.proxy_image("cover-source")

        assert result == b"fetched-source"
        cache.get_image.assert_awaited_once_with("cover-source")
        provider.fetch_image.assert_awaited_once_with("cover-source")
        cache.put_image.assert_awaited_once_with("cover-source", b"fetched-source")


class TestPageAndThumbnailCaching:
    @pytest.mark.asyncio
    async def test_page_cache_hit_skips_detail_and_provider(
        self,
        provider,
        cache,
        cache_config,
    ):
        cache_key = "media:alpha:page:gallery:token:2"
        cache.get_image.return_value = b"cached-page"
        service = ImageService(provider, cache, cache_config)

        result = await service.get_page_image("gallery", "token", 2)

        assert result == b"cached-page"
        cache.get_image.assert_awaited_once_with(cache_key)
        cache.get_gallery.assert_not_called()
        provider.get_gallery_details.assert_not_awaited()
        provider.get_page_image.assert_not_awaited()
        cache.put_image.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_page_miss_loads_caches_detail_and_delegates_bytes(
        self,
        provider,
        cache,
        cache_config,
        detail,
    ):
        cache_key = "media:alpha:page:gallery:token:2"
        provider.get_gallery_details.return_value = detail
        provider.get_page_image.return_value = b"page-bytes"
        service = ImageService(provider, cache, cache_config)

        result = await service.get_page_image("gallery", "token", 2)

        assert result == b"page-bytes"
        cache.get_image.assert_awaited_once_with(cache_key)
        cache.get_gallery.assert_called_once_with("gallery", "token")
        provider.get_gallery_details.assert_awaited_once_with("gallery", "token")
        cache.put_gallery.assert_called_once_with(detail)
        provider.get_page_image.assert_awaited_once_with(detail, 2)
        cache.put_image.assert_awaited_once_with(cache_key, b"page-bytes")

    @pytest.mark.asyncio
    async def test_thumbnail_miss_uses_cached_detail_and_delegates_bytes(
        self,
        provider,
        cache,
        cache_config,
        detail,
    ):
        cache_key = "media:alpha:thumbnail:gallery:token:2"
        cache.get_gallery.return_value = detail
        provider.get_thumbnail.return_value = b"thumbnail-bytes"
        service = ImageService(provider, cache, cache_config)

        result = await service.get_thumbnail("gallery", "token", 2)

        assert result == b"thumbnail-bytes"
        cache.get_image.assert_awaited_once_with(cache_key)
        cache.get_gallery.assert_called_once_with("gallery", "token")
        provider.get_gallery_details.assert_not_awaited()
        provider.get_thumbnail.assert_awaited_once_with(detail, 2)
        cache.put_image.assert_awaited_once_with(cache_key, b"thumbnail-bytes")

    @pytest.mark.asyncio
    async def test_media_keys_separate_provider_and_media_kind(self, cache, cache_config, detail):
        alpha = FakeProvider("alpha")
        beta = FakeProvider("beta")
        alpha.get_gallery_details.return_value = detail
        beta.get_gallery_details.return_value = detail
        alpha.get_page_image.return_value = b"alpha-page"
        alpha.get_thumbnail.return_value = b"alpha-thumbnail"
        beta.get_page_image.return_value = b"beta-page"
        alpha_service = ImageService(alpha, cache, cache_config)
        beta_service = ImageService(beta, cache, cache_config)

        await alpha_service.get_page_image("gallery", "token", 1)
        await alpha_service.get_thumbnail("gallery", "token", 1)
        await beta_service.get_page_image("gallery", "token", 1)

        keys = [call.args[0] for call in cache.get_image.await_args_list]
        assert keys == [
            "media:alpha:page:gallery:token:1",
            "media:alpha:thumbnail:gallery:token:1",
            "media:beta:page:gallery:token:1",
        ]
        assert len(keys) == len(set(keys))


class TestPrefetch:
    @pytest.mark.asyncio
    async def test_prefetch_respects_bounds_and_deduplicates_active_tasks(
        self,
        provider,
        cache,
        cache_config,
        detail,
    ):
        cache.get_gallery.return_value = detail
        release = asyncio.Event()
        started = asyncio.Event()
        started_pages: set[int] = set()

        async def load_page(_detail, page):
            started_pages.add(page)
            if len(started_pages) == 4:
                started.set()
            await release.wait()
            return f"page-{page}".encode()

        provider.get_page_image.side_effect = load_page
        service = ImageService(provider, cache, cache_config)

        await service.prefetch("gallery", "token", current_page=5, total_pages=10)
        await asyncio.wait_for(started.wait(), timeout=1)
        tasks = dict(service._prefetch_tasks)

        assert set(tasks) == {
            "media:alpha:page:gallery:token:4",
            "media:alpha:page:gallery:token:6",
            "media:alpha:page:gallery:token:7",
            "media:alpha:page:gallery:token:8",
        }
        assert started_pages == {4, 6, 7, 8}

        await service.prefetch("gallery", "token", current_page=5, total_pages=10)

        assert service._prefetch_tasks == tasks
        release.set()
        await asyncio.gather(*tasks.values())
        await service.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_and_clears_prefetch_tasks(
        self,
        provider,
        cache,
        cache_config,
        detail,
    ):
        cache.get_gallery.return_value = detail
        started = asyncio.Event()
        never = asyncio.Event()

        async def load_page(_detail, _page):
            started.set()
            await never.wait()
            return b"unreachable"

        provider.get_page_image.side_effect = load_page
        service = ImageService(provider, cache, cache_config)

        await service.prefetch("gallery", "token", current_page=1, total_pages=2)
        await asyncio.wait_for(started.wait(), timeout=1)
        tasks = tuple(service._prefetch_tasks.values())

        await service.shutdown()

        assert all(task.cancelled() for task in tasks)
        assert service._prefetch_tasks == {}
