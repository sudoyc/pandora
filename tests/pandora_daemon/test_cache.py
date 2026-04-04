"""Tests for pandora_daemon.cache module."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from pandora_daemon.cache import CacheManager
from pandora_daemon.config import CacheConfig


def make_config(tmp_path, thumb_max_size_mb: int = 500, gallery_ttl_seconds: int = 300) -> CacheConfig:
    """Create a CacheConfig pointing to a temporary directory."""
    return CacheConfig(
        thumb_dir=str(tmp_path / "thumbs"),
        thumb_max_size_mb=thumb_max_size_mb,
        gallery_ttl_seconds=gallery_ttl_seconds,
    )


class TestThumbCache:
    """Disk-based thumbnail cache tests."""

    @pytest.mark.asyncio
    async def test_thumb_miss_returns_none(self, tmp_path):
        """get_thumb returns None for an unknown URL."""
        config = make_config(tmp_path)
        cache = CacheManager(config)

        result = await cache.get_thumb("https://example.com/unknown.jpg")

        assert result is None

    @pytest.mark.asyncio
    async def test_thumb_put_and_get(self, tmp_path):
        """put_thumb then get_thumb returns the same bytes."""
        config = make_config(tmp_path)
        cache = CacheManager(config)

        url = "https://example.com/thumb.jpg"
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 100  # fake JPEG bytes

        await cache.put_thumb(url, data)
        result = await cache.get_thumb(url)

        assert result == data

    @pytest.mark.asyncio
    async def test_thumb_eviction(self, tmp_path):
        """With 0 MB limit, evict_thumbs removes all cached files."""
        config = make_config(tmp_path, thumb_max_size_mb=0)
        cache = CacheManager(config)

        # Store a few thumbnails
        for i in range(3):
            await cache.put_thumb(f"https://example.com/img{i}.jpg", b"x" * 1024)

        # Confirm files exist
        thumb_dir = tmp_path / "thumbs"
        assert len(list(thumb_dir.iterdir())) == 3

        await cache.evict_thumbs()

        assert len(list(thumb_dir.iterdir())) == 0


class TestGalleryCache:
    """In-memory gallery detail cache with TTL tests."""

    def test_gallery_cache_miss(self, tmp_path):
        """get_gallery returns None for an unknown (gid, token)."""
        config = make_config(tmp_path)
        cache = CacheManager(config)

        result = cache.get_gallery("12345", "abc123")

        assert result is None

    def test_gallery_cache_put_and_get(self, tmp_path):
        """put_gallery then get_gallery returns the same object."""
        config = make_config(tmp_path)
        cache = CacheManager(config)

        detail = SimpleNamespace(gid="12345", token="abc123", title="Test Gallery")
        cache.put_gallery(detail)
        result = cache.get_gallery("12345", "abc123")

        assert result is detail

    def test_gallery_cache_ttl_expiry(self, tmp_path):
        """Manually expire entry: get_gallery returns None after TTL."""
        config = make_config(tmp_path, gallery_ttl_seconds=300)
        cache = CacheManager(config)

        detail = SimpleNamespace(gid="99999", token="deadbeef", title="Expired Gallery")
        cache.put_gallery(detail)

        # Manually set the expiry to the past to simulate TTL expiry
        key = f"{detail.gid}:{detail.token}"
        existing_detail, _ = cache._gallery_cache[key]
        cache._gallery_cache[key] = (existing_detail, time.time() - 1)

        result = cache.get_gallery("99999", "deadbeef")

        assert result is None
