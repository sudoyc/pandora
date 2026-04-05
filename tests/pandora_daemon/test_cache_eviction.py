"""Tests for cache eviction loop in app.py."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pandora_daemon.app import _cache_eviction_loop


class TestCacheEvictionLoop:
    @pytest.mark.asyncio
    async def test_calls_prune_then_evict(self):
        """Loop calls prune_expired_galleries then evict_images each cycle."""
        cache = MagicMock()
        cache.prune_expired_galleries = MagicMock()
        cache.evict_images = AsyncMock()

        call_order = []
        cache.prune_expired_galleries.side_effect = lambda: call_order.append("prune")
        cache.evict_images.side_effect = lambda: call_order.append("evict")

        task = asyncio.create_task(_cache_eviction_loop(cache, interval=0))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        assert cache.prune_expired_galleries.call_count >= 1
        assert cache.evict_images.call_count >= 1
        # Verify ordering: each prune is followed by evict
        for i in range(0, len(call_order) - 1, 2):
            assert call_order[i] == "prune"
            assert call_order[i + 1] == "evict"

    @pytest.mark.asyncio
    async def test_exception_resilience(self):
        """If evict_images raises, the loop continues running."""
        cache = MagicMock()
        cache.prune_expired_galleries = MagicMock()
        call_count = 0

        async def evict_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("disk error")

        cache.evict_images = AsyncMock(side_effect=evict_side_effect)

        task = asyncio.create_task(_cache_eviction_loop(cache, interval=0))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Loop survived the first exception and ran again
        assert call_count >= 2

    @pytest.mark.asyncio
    async def test_cancel_exits_cleanly(self):
        """Cancelling the task raises CancelledError, no other exception."""
        cache = MagicMock()
        cache.prune_expired_galleries = MagicMock()
        cache.evict_images = AsyncMock()

        task = asyncio.create_task(_cache_eviction_loop(cache, interval=9999))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
