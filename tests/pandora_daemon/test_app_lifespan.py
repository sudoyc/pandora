"""Tests for _build_state and lifespan in app.py."""
from __future__ import annotations

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from pandora_daemon.app import _build_state
from pandora_daemon.config import CredentialsConfig, NetworkConfig, PandoraConfig
from pandora_daemon.providers import ProviderContext, ProviderRegistry


class TestBuildState:
    @pytest.mark.asyncio
    async def test_returns_appstate(self):
        """_build_state returns a properly constructed AppState."""
        provider = MagicMock()
        provider_registry = MagicMock(spec=ProviderRegistry)
        provider_registry.create.return_value = provider

        with (
            patch("pandora_daemon.app.load_config") as mock_load,
            patch("pandora_daemon.app.PandoraDB") as mock_db_cls,
            patch("pandora_daemon.app.CacheManager") as mock_cache_cls,
            patch("pandora_daemon.app.ImageService") as mock_img_cls,
            patch("pandora_daemon.app.WebSocketManager") as mock_ws_cls,
            patch("pandora_daemon.app.TagDatabase") as mock_tag_cls,
            patch("pandora_daemon.app.DownloadManager") as mock_dl_cls,
        ):
            mock_config = PandoraConfig()
            mock_load.return_value = mock_config

            mock_db = MagicMock()
            mock_db.initialize = AsyncMock()
            mock_db_cls.return_value = mock_db

            mock_tag = MagicMock()
            mock_tag.download_and_load = AsyncMock()
            mock_tag_cls.return_value = mock_tag

            state = await _build_state(provider_registry=provider_registry)

            from pandora_daemon.state import AppState

            assert isinstance(state, AppState)
            assert state.config is mock_config
            assert state.provider is provider
            provider_registry.create.assert_called_once_with(
                "exhentai",
                ProviderContext(
                    credentials={
                        "igneous": "",
                        "ipb_member_id": "",
                        "ipb_pass_hash": "",
                    },
                    proxy="",
                    timeout=30,
                ),
            )
            mock_db.initialize.assert_awaited_once()
            mock_tag.download_and_load.assert_awaited_once()
            mock_img_cls.assert_called_once_with(
                api=provider,
                cache=mock_cache_cls.return_value,
                config=mock_config.cache,
            )
            mock_dl_cls.assert_called_once_with(
                api=provider,
                config=mock_config.download,
                ws=mock_ws_cls.return_value,
                image_service=mock_img_cls.return_value,
                state_file=ANY,
            )

    @pytest.mark.asyncio
    async def test_build_state_passes_provider_context(self):
        """_build_state creates the configured provider with a neutral context."""
        provider = MagicMock()
        provider_registry = MagicMock(spec=ProviderRegistry)
        provider_registry.create.return_value = provider

        with (
            patch("pandora_daemon.app.load_config") as mock_load,
            patch("pandora_daemon.app.PandoraDB") as mock_db_cls,
            patch("pandora_daemon.app.CacheManager"),
            patch("pandora_daemon.app.ImageService"),
            patch("pandora_daemon.app.WebSocketManager"),
            patch("pandora_daemon.app.TagDatabase") as mock_tag_cls,
            patch("pandora_daemon.app.DownloadManager"),
        ):
            mock_config = PandoraConfig(
                credentials=CredentialsConfig(
                    igneous="test",
                    ipb_member_id="test",
                    ipb_pass_hash="synthetic_hash",
                ),
                network=NetworkConfig(
                    proxy="socks5://127.0.0.1:1080",
                    timeout=60,
                ),
            )
            mock_load.return_value = mock_config

            mock_db = MagicMock()
            mock_db.initialize = AsyncMock()
            mock_db_cls.return_value = mock_db

            mock_tag = MagicMock()
            mock_tag.download_and_load = AsyncMock()
            mock_tag_cls.return_value = mock_tag

            await _build_state(provider_registry=provider_registry)

            provider_registry.create.assert_called_once_with(
                "exhentai",
                ProviderContext(
                    credentials={
                        "igneous": "test",
                        "ipb_member_id": "test",
                        "ipb_pass_hash": "synthetic_hash",
                    },
                    proxy="socks5://127.0.0.1:1080",
                    timeout=60,
                ),
            )


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
