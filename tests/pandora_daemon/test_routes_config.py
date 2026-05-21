"""Tests for pandora_daemon.routes.config_routes module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.config import CredentialsConfig, PandoraConfig
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

    def test_get_config_redacts_proxy_value(self):
        config = PandoraConfig()
        config.network.proxy = "http://user:pass@proxy.example:8080"
        app, _ = _make_app(config=config)
        client = TestClient(app)

        resp = client.get("/api/config")

        assert resp.status_code == 200
        data = resp.json()
        assert data["network"]["proxy_configured"] is True
        assert "proxy" not in data["network"]
        assert "user:pass" not in resp.text


class TestHealth:
    def test_health_returns_safe_public_shape(self, tmp_path):
        config = PandoraConfig(
            credentials=CredentialsConfig(igneous="secret-igneous", ipb_member_id="secret-member"),
        )
        config.download.path = "~/Downloads/pandora"
        config.cache.image_dir = "~/.cache/pandora/images"
        app, _ = _make_app(config=config, config_path=tmp_path / "config.toml")
        client = TestClient(app)

        resp = client.get("/api/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["service"] == "pandora-daemon"
        assert isinstance(data["version"], str)
        assert data["auth_configured"] is True
        assert data["capabilities"] == {
            "browse": True,
            "gallery_detail": True,
            "downloads": True,
            "library": True,
            "tags": True,
            "favorites": True,
            "websocket": True,
        }
        assert "config_path" not in data
        assert "database_path" not in data
        assert "download_path" not in data
        assert "cache_path" not in data
        assert "secret-igneous" not in resp.text
        assert "secret-member" not in resp.text

    def test_health_reports_auth_not_configured(self):
        app, _ = _make_app()
        client = TestClient(app)

        resp = client.get("/api/health")

        assert resp.status_code == 200
        assert resp.json()["auth_configured"] is False


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
