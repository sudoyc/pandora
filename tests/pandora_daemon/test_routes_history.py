"""Tests for pandora_daemon.routes.history module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.history import router
from pandora_daemon.state import AppState


def _make_app(mock_db):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.db = mock_db
    app.state.pandora = state
    return app


_SAMPLE = {
    "gid": "123",
    "token": "abc",
    "title": "Test Gallery",
    "title_jpn": None,
    "category": "Doujinshi",
    "uploader": "uploader",
    "thumb_url": "http://example.com/thumb.jpg",
    "posted": "2024-01-01",
    "rating": 4.5,
    "pages": 20,
    "read_page": 5,
    "time": 1700000000,
}


class TestGetHistory:
    def test_returns_200_with_list(self):
        mock_db = MagicMock()
        mock_db.get_history = AsyncMock(return_value=[_SAMPLE])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/history")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["gid"] == "123"
        assert data[0]["title"] == "Test Gallery"
        assert data[0]["read_page"] == 5
        assert "token" not in data[0]

    def test_returns_empty_list(self):
        mock_db = MagicMock()
        mock_db.get_history = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/history")

        assert response.status_code == 200
        assert response.json() == []

    def test_passes_limit_and_offset(self):
        mock_db = MagicMock()
        mock_db.get_history = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        client.get("/api/history?limit=10&offset=20")

        mock_db.get_history.assert_called_once_with(10, 20)

    def test_default_limit_offset(self):
        mock_db = MagicMock()
        mock_db.get_history = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        client.get("/api/history")

        mock_db.get_history.assert_called_once_with(50, 0)


class TestDeleteOneHistory:
    def test_returns_ok(self):
        mock_db = MagicMock()
        mock_db.delete_history = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.delete("/api/history/123")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_calls_delete_with_gid(self):
        mock_db = MagicMock()
        mock_db.delete_history = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        client.delete("/api/history/456")

        mock_db.delete_history.assert_called_once_with("456")


class TestClearHistory:
    def test_returns_ok(self):
        mock_db = MagicMock()
        mock_db.clear_history = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.delete("/api/history")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_calls_clear_history(self):
        mock_db = MagicMock()
        mock_db.clear_history = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        client.delete("/api/history")

        mock_db.clear_history.assert_called_once()
