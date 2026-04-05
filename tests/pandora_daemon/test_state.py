"""Tests for AppState lifecycle methods."""
from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from pandora_daemon.state import AppState


def _make_state() -> AppState:
    """Build an AppState with all-mock components."""
    downloads = MagicMock()
    downloads.start = AsyncMock()
    downloads.shutdown = AsyncMock()

    image_service = MagicMock()
    image_service.shutdown = AsyncMock()

    db = MagicMock()
    db.close = AsyncMock()

    api = MagicMock()
    api.aclose = AsyncMock()

    return AppState(
        config=MagicMock(),
        config_path=MagicMock(),
        client=MagicMock(),
        api=api,
        downloads=downloads,
        cache=MagicMock(),
        image_service=image_service,
        ws=MagicMock(),
        db=db,
        tag_database=MagicMock(),
    )


class TestAppStateStart:
    @pytest.mark.asyncio
    async def test_start_calls_downloads_start(self):
        state = _make_state()
        coro = AsyncMock()()  # a coroutine object
        await state.start(coro)
        state.downloads.start.assert_awaited_once()
        # cleanup dangling task
        state._eviction_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await state._eviction_task

    @pytest.mark.asyncio
    async def test_start_creates_eviction_task(self):
        state = _make_state()
        started = asyncio.Event()

        async def fake_loop():
            started.set()
            await asyncio.sleep(9999)

        await state.start(fake_loop())
        await asyncio.sleep(0.01)
        assert started.is_set()
        assert state._eviction_task is not None
        assert not state._eviction_task.done()
        # cleanup
        state._eviction_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await state._eviction_task


class TestAppStateShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_order(self):
        """shutdown() calls components in correct order."""
        state = _make_state()
        order = []
        state.downloads.shutdown = AsyncMock(side_effect=lambda: order.append("downloads"))
        state.image_service.shutdown = AsyncMock(side_effect=lambda: order.append("image_service"))
        state.db.close = AsyncMock(side_effect=lambda: order.append("db"))
        state.api.aclose = AsyncMock(side_effect=lambda: order.append("api"))

        # start first so _eviction_task exists
        async def fake_loop():
            await asyncio.sleep(9999)

        await state.start(fake_loop())
        await state.shutdown()

        assert order == ["downloads", "image_service", "db", "api"]

    @pytest.mark.asyncio
    async def test_shutdown_cancels_eviction_task(self):
        state = _make_state()

        async def fake_loop():
            await asyncio.sleep(9999)

        await state.start(fake_loop())
        task = state._eviction_task
        await state.shutdown()
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_without_start(self):
        """shutdown() works even if start() was never called."""
        state = _make_state()
        await state.shutdown()  # should not raise
        state.downloads.shutdown.assert_awaited_once()
        state.api.aclose.assert_awaited_once()
