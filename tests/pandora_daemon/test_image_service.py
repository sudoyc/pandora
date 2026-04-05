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
        svc = ImageService(mock_api, mock_cache, cache_config)
        svc._page_url_cache["123:1"] = "https://cdn.example.com/full.jpg"
        mock_cache.get_image = AsyncMock(return_value=b"page_bytes")

        result = await svc.get_page_image("123", "abc", 1)

        assert result == b"page_bytes"
        mock_cache.get_image.assert_awaited_once_with("https://cdn.example.com/full.jpg")

    @pytest.mark.asyncio
    async def test_page_image_not_cached(self, mock_api, mock_cache, cache_config):
        detail = MagicMock()
        detail.viewer_urls = ["https://exhentai.org/s/imgkey1/123-1"]
        detail.pages = 1
        mock_cache.get_gallery = MagicMock(return_value=detail)

        viewer_html = '<html><body><img id="img" src="https://cdn.example.com/full.jpg" /><script>nl(\'nltoken\')</script></body></html>'
        mock_api.client.get_html = AsyncMock(return_value=viewer_html)

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
        detail = MagicMock()
        detail.viewer_urls = [f"https://exhentai.org/s/key{i}/123-{i+1}" for i in range(10)]
        mock_cache.get_gallery = MagicMock(return_value=detail)

        svc = ImageService(mock_api, mock_cache, cache_config)
        svc.get_page_image = AsyncMock(return_value=b"data")

        await svc.prefetch("123", "abc", current_page=5, total_pages=10)
        await asyncio.sleep(0.05)

        expected_keys = {"123:4", "123:6", "123:7", "123:8"}
        actual_keys = set(svc._prefetch_tasks.keys())
        assert expected_keys.issubset(actual_keys)

        await svc.shutdown()

    @pytest.mark.asyncio
    async def test_prefetch_clamps_to_bounds(self, mock_api, mock_cache, cache_config):
        detail = MagicMock()
        detail.viewer_urls = [f"https://exhentai.org/s/key{i}/123-{i+1}" for i in range(5)]
        mock_cache.get_gallery = MagicMock(return_value=detail)

        svc = ImageService(mock_api, mock_cache, cache_config)
        svc.get_page_image = AsyncMock(return_value=b"data")

        await svc.prefetch("123", "abc", current_page=1, total_pages=5)
        await asyncio.sleep(0.05)

        assert "123:0" not in svc._prefetch_tasks

        await svc.shutdown()


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_cancels_prefetch(self, mock_api, mock_cache, cache_config):
        svc = ImageService(mock_api, mock_cache, cache_config)

        async def slow():
            await asyncio.sleep(999)

        task = asyncio.create_task(slow())
        svc._prefetch_tasks["123:1"] = task

        await svc.shutdown()

        assert task.cancelled()
        assert len(svc._prefetch_tasks) == 0
