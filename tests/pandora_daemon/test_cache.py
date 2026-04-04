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
        config = make_config(tmp_path)
        cache = CacheManager(config)
        await cache.put_image("https://cdn.example.com/image.png?token=abc", b"pngdata")
        files = list((tmp_path / "images").iterdir())
        assert len(files) == 1
        assert files[0].suffix == ".png"


class TestGalleryCache:
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
