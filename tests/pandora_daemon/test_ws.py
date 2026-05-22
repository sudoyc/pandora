"""Tests for pandora_daemon.ws module."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from pandora_daemon.ws import WebSocketManager


@pytest.fixture
def manager():
    return WebSocketManager()


def make_ws():
    """Create a mock WebSocket."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


class TestConnect:
    """Test WebSocketManager.connect."""

    @pytest.mark.asyncio
    async def test_connect_adds_to_set(self, manager):
        ws = make_ws()
        await manager.connect(ws)
        assert ws in manager.connections

    @pytest.mark.asyncio
    async def test_connect_calls_accept(self, manager):
        ws = make_ws()
        await manager.connect(ws)
        ws.accept.assert_called_once()


class TestDisconnect:
    """Test WebSocketManager.disconnect."""

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_set(self, manager):
        ws = make_ws()
        await manager.connect(ws)
        manager.disconnect(ws)
        assert ws not in manager.connections

    def test_disconnect_ignores_missing(self, manager):
        ws = make_ws()
        # Should not raise even if ws was never connected
        manager.disconnect(ws)


class TestBroadcast:
    """Test WebSocketManager.broadcast."""

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self, manager):
        ws1 = make_ws()
        ws2 = make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)

        event = {"event": "download_complete", "gid": "123"}
        await manager.broadcast(event)

        ws1.send_json.assert_called_once_with(event)
        ws2.send_json.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_broadcast_removes_disconnected(self, manager):
        ws_good = make_ws()
        ws_dead = make_ws()
        ws_dead.send_json = AsyncMock(side_effect=Exception("connection closed"))

        await manager.connect(ws_good)
        await manager.connect(ws_dead)

        event = {"event": "test"}
        await manager.broadcast(event)

        assert ws_dead not in manager.connections
        assert ws_good in manager.connections
