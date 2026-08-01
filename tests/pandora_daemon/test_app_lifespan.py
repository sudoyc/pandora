"""Tests for _build_state and lifespan in app.py."""
from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pandora_daemon.app import _build_state
from pandora_daemon.config import NetworkConfig, PandoraConfig, ProviderConfig
from pandora_daemon.providers import ProviderContext, ProviderRegistry


@contextmanager
def _build_dependencies(config: PandoraConfig):
    with (
        patch("pandora_daemon.app.load_config", return_value=config),
        patch("pandora_daemon.app.PandoraDB") as database_class,
        patch("pandora_daemon.app.CacheManager") as cache_class,
        patch("pandora_daemon.app.ImageService") as image_service_class,
        patch("pandora_daemon.app.WebSocketManager") as websocket_class,
        patch("pandora_daemon.app.TagDatabase") as tag_database_class,
        patch("pandora_daemon.app.DownloadManager") as download_manager_class,
    ):
        database = MagicMock()
        database.initialize = AsyncMock()
        database_class.return_value = database

        tag_database = MagicMock()
        tag_database.download_and_load = AsyncMock()
        tag_database_class.return_value = tag_database

        yield SimpleNamespace(
            database=database,
            database_class=database_class,
            cache_class=cache_class,
            image_service_class=image_service_class,
            websocket_class=websocket_class,
            tag_database=tag_database,
            download_manager_class=download_manager_class,
        )


class TestBuildState:
    @pytest.mark.asyncio
    async def test_explicit_provider_override_forwards_context_and_wires_provider(self):
        config = PandoraConfig(
            provider=ProviderConfig(
                id="configured",
                credentials={"session": "test-session", "extra": "value"},
            ),
            network=NetworkConfig(
                proxy="socks5://127.0.0.1:1080",
                timeout=60,
            ),
        )
        provider = MagicMock()
        provider.provider_id = "explicit"
        explicit_factory = MagicMock(return_value=provider)
        configured_factory = MagicMock()
        fallback_factory = MagicMock()
        registry = ProviderRegistry(
            {
                "explicit": explicit_factory,
                "configured": configured_factory,
                "fallback": fallback_factory,
            },
            default_provider_id="fallback",
        )

        with _build_dependencies(config) as dependencies:
            state = await _build_state(
                provider_registry=registry,
                provider_id=" explicit ",
            )

        from pandora_daemon.state import AppState

        assert isinstance(state, AppState)
        assert state.config is config
        assert state.provider is provider
        assert config.provider.id == "explicit"
        explicit_factory.assert_called_once()
        configured_factory.assert_not_called()
        fallback_factory.assert_not_called()
        context = explicit_factory.call_args.args[0]
        assert context == ProviderContext(
            credentials={"session": "test-session", "extra": "value"},
            proxy="socks5://127.0.0.1:1080",
            timeout=60,
        )
        assert context.credentials is not config.provider.credentials
        dependencies.database.initialize.assert_awaited_once()
        dependencies.tag_database.download_and_load.assert_awaited_once()
        dependencies.image_service_class.assert_called_once_with(
            provider=provider,
            cache=dependencies.cache_class.return_value,
            config=config.cache,
        )
        provider_dir = Path("~/.config/pandora/providers/explicit").expanduser()
        dependencies.database_class.assert_called_once_with(provider_dir / "pandora.db")
        dependencies.download_manager_class.assert_called_once_with(
            provider=provider,
            config=config.download,
            ws=dependencies.websocket_class.return_value,
            image_service=dependencies.image_service_class.return_value,
            state_file=provider_dir / "downloads.json",
            download_path=Path(config.download.path).expanduser() / "explicit",
        )

    @pytest.mark.asyncio
    async def test_configured_provider_is_selected_without_an_override(self):
        config = PandoraConfig(provider=ProviderConfig(id="configured"))
        provider = MagicMock()
        provider.provider_id = "configured"
        configured_factory = MagicMock(return_value=provider)
        fallback_factory = MagicMock()
        registry = ProviderRegistry(
            {"configured": configured_factory, "fallback": fallback_factory},
            default_provider_id="fallback",
        )

        with _build_dependencies(config):
            state = await _build_state(provider_registry=registry)

        assert state.provider is provider
        configured_factory.assert_called_once()
        fallback_factory.assert_not_called()

    @pytest.mark.asyncio
    async def test_registry_default_is_selected_when_config_has_no_provider_id(self):
        config = PandoraConfig(provider=ProviderConfig())
        provider = MagicMock()
        provider.provider_id = "fallback"
        fallback_factory = MagicMock(return_value=provider)
        registry = ProviderRegistry(
            {"fallback": fallback_factory},
            default_provider_id=" FALLBACK ",
        )

        with _build_dependencies(config):
            state = await _build_state(provider_registry=registry)

        assert state.provider is provider
        assert config.provider.id == "fallback"
        fallback_factory.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_default_provider_uses_isolated_workspace(self):
        config = PandoraConfig(provider=ProviderConfig(id="fixture"))
        provider = MagicMock()
        provider.provider_id = "fixture"
        registry = ProviderRegistry(
            {"default": MagicMock(), "fixture": MagicMock(return_value=provider)},
            default_provider_id="default",
        )

        with _build_dependencies(config) as dependencies:
            state = await _build_state(provider_registry=registry)

        config_dir = Path("~/.config/pandora").expanduser()
        provider_dir = config_dir / "providers" / "fixture"
        dependencies.database_class.assert_called_once_with(provider_dir / "pandora.db")
        call = dependencies.download_manager_class.call_args
        assert call.kwargs["state_file"] == provider_dir / "downloads.json"
        assert call.kwargs["download_path"] == Path(config.download.path).expanduser() / "fixture"
        assert state.config.download.path == "~/Downloads/pandora"


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
