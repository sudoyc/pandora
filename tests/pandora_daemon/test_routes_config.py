"""Tests for pandora_daemon.routes.config_routes module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.config import PandoraConfig
from pandora_daemon.routes.config_routes import router
from pandora_daemon.state import AppState


def _make_app(config=None, config_path=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.config = config or PandoraConfig()
    state.config_path = config_path or Path("/tmp/config.toml")
    state.ws = MagicMock()
    app.state.pandora = state
    return app, state


class TestGetConfig:
    def test_get_config_returns_200(self):
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.get("/api/config")

        assert resp.status_code == 200

    def test_get_config_credentials_not_in_response(self):
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.get("/api/config")

        data = resp.json()
        assert "credentials" not in data

    def test_get_config_server_port_is_7860(self):
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.get("/api/config")

        data = resp.json()
        assert data["server"]["port"] == 7860

    def test_get_config_returns_server_section(self):
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.get("/api/config")

        data = resp.json()
        assert "server" in data
        assert "host" in data["server"]

    def test_get_config_returns_download_section(self):
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.get("/api/config")

        data = resp.json()
        assert "download" in data
        assert "gallery_concurrency" in data["download"]

    def test_get_config_returns_cache_section(self):
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.get("/api/config")

        data = resp.json()
        assert "cache" in data
        assert "gallery_ttl_seconds" in data["cache"]


class TestUpdateConfig:
    def test_update_config_returns_200(self, tmp_path):
        config_path = tmp_path / "config.toml"
        app, _ = _make_app(config_path=config_path)
        client = TestClient(app)

        with patch("pandora_daemon.routes.config_routes.save_config"):
            resp = client.put("/api/config", json={"server": {"port": 9999}})

        assert resp.status_code == 200

    def test_update_config_changes_server_port(self, tmp_path):
        config_path = tmp_path / "config.toml"
        app, state = _make_app(config_path=config_path)
        client = TestClient(app)

        with patch("pandora_daemon.routes.config_routes.save_config"):
            resp = client.put("/api/config", json={"server": {"port": 9999}})

        assert resp.status_code == 200
        assert state.config.server.port == 9999

    def test_update_config_calls_save_config(self, tmp_path):
        config_path = tmp_path / "config.toml"
        app, state = _make_app(config_path=config_path)
        client = TestClient(app)

        with patch("pandora_daemon.routes.config_routes.save_config") as mock_save:
            resp = client.put("/api/config", json={"server": {"port": 9999}})
            assert resp.status_code == 200
            assert state.config.server.port == 9999
            mock_save.assert_called_once()

    def test_update_config_download_concurrency(self, tmp_path):
        config_path = tmp_path / "config.toml"
        app, state = _make_app(config_path=config_path)
        client = TestClient(app)

        with patch("pandora_daemon.routes.config_routes.save_config"):
            resp = client.put("/api/config", json={"download": {"gallery_concurrency": 5}})

        assert resp.status_code == 200
        assert state.config.download.gallery_concurrency == 5

    def test_update_config_cache_ttl(self, tmp_path):
        config_path = tmp_path / "config.toml"
        app, state = _make_app(config_path=config_path)
        client = TestClient(app)

        with patch("pandora_daemon.routes.config_routes.save_config"):
            resp = client.put("/api/config", json={"cache": {"gallery_ttl_seconds": 600}})

        assert resp.status_code == 200
        assert state.config.cache.gallery_ttl_seconds == 600

    def test_update_config_ignores_unknown_keys(self, tmp_path):
        config_path = tmp_path / "config.toml"
        app, state = _make_app(config_path=config_path)
        client = TestClient(app)

        with patch("pandora_daemon.routes.config_routes.save_config"):
            resp = client.put("/api/config", json={"server": {"nonexistent_key": "value"}})

        assert resp.status_code == 200

    def test_update_config_response_omits_credentials(self, tmp_path):
        config_path = tmp_path / "config.toml"
        app, _ = _make_app(config_path=config_path)
        client = TestClient(app)

        with patch("pandora_daemon.routes.config_routes.save_config"):
            resp = client.put("/api/config", json={"server": {"port": 8080}})

        data = resp.json()
        assert "credentials" not in data

    def test_update_config_passes_config_path_to_save(self, tmp_path):
        config_path = tmp_path / "config.toml"
        app, state = _make_app(config_path=config_path)
        client = TestClient(app)

        with patch("pandora_daemon.routes.config_routes.save_config") as mock_save:
            client.put("/api/config", json={"server": {"port": 1234}})

        mock_save.assert_called_once_with(state.config, config_path)
