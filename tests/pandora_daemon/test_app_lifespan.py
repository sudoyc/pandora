"""Tests for _build_state and lifespan in app.py."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pandora_daemon.app import _build_state


class TestBuildState:
    @pytest.mark.asyncio
    async def test_returns_appstate(self):
        """_build_state returns a properly constructed AppState."""
        with (
            patch("pandora_daemon.app.load_config") as mock_load,
            patch("pandora_daemon.app.PandoraDB") as mock_db_cls,
            patch("pandora_daemon.app.ExhentaiClient") as mock_client_cls,
            patch("pandora_daemon.app.ExhentaiAPI") as mock_api_cls,
            patch("pandora_daemon.app.CacheManager") as mock_cache_cls,
            patch("pandora_daemon.app.ImageService") as mock_img_cls,
            patch("pandora_daemon.app.WebSocketManager") as mock_ws_cls,
            patch("pandora_daemon.app.TagDatabase") as mock_tag_cls,
            patch("pandora_daemon.app.DownloadManager") as mock_dl_cls,
        ):
            mock_config = MagicMock()
            mock_config.credentials.igneous = "test"
            mock_config.credentials.ipb_member_id = "test"
            mock_load.return_value = mock_config

            mock_db = AsyncMock()
            mock_db.initialize = AsyncMock()
            mock_db_cls.return_value = mock_db

            mock_tag = MagicMock()
            mock_tag.download_and_load = AsyncMock()
            mock_tag_cls.return_value = mock_tag

            state = await _build_state()

            from pandora_daemon.state import AppState
            assert isinstance(state, AppState)
            assert state.config is mock_config
            mock_db.initialize.assert_awaited_once()
            mock_tag.download_and_load.assert_awaited_once()


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_calls_start_and_shutdown(self):
        """lifespan calls state.start() before yield and state.shutdown() after."""
        from pandora_daemon.app import lifespan

        mock_state = MagicMock()

        async def _consume_coro(coro):
            coro.close()

        mock_state.start = AsyncMock(side_effect=_consume_coro)
        mock_state.shutdown = AsyncMock()

        mock_app = MagicMock()

        with patch("pandora_daemon.app._build_state", new_callable=AsyncMock, return_value=mock_state):
            async with lifespan(mock_app):
                mock_state.start.assert_awaited_once()
                assert mock_app.state.pandora is mock_state

            mock_state.shutdown.assert_awaited_once()
