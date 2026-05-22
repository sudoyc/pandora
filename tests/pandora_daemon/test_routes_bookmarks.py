"""Tests for pandora_daemon.routes.bookmarks_routes module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.bookmarks_routes import router
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
    "thumb_url": "http://example.com/thumb.jpg",
    "page": 5,
    "total": 20,
    "time": 1700000000,
}


class TestListBookmarks:
    def test_returns_200_with_list(self):
        mock_db = MagicMock()
        mock_db.get_bookmarks = AsyncMock(return_value=[_SAMPLE])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/bookmarks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["gid"] == "123"
        assert data[0]["title"] == "Test Gallery"
        assert data[0]["page"] == 5
        assert "token" not in data[0]

    def test_returns_empty_list(self):
        mock_db = MagicMock()
        mock_db.get_bookmarks = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/bookmarks")

        assert response.status_code == 200
        assert response.json() == []

    def test_passes_limit_and_offset(self):
        mock_db = MagicMock()
        mock_db.get_bookmarks = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        client.get("/api/bookmarks?limit=5&offset=10")

        mock_db.get_bookmarks.assert_called_once_with(5, 10)

    def test_default_limit_offset(self):
        mock_db = MagicMock()
        mock_db.get_bookmarks = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        client.get("/api/bookmarks")

        mock_db.get_bookmarks.assert_called_once_with(50, 0)


class TestGetOneBookmark:
    def test_returns_bookmark_when_found(self):
        mock_db = MagicMock()
        mock_db.get_bookmark = AsyncMock(return_value=_SAMPLE)
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/bookmarks/123")

        assert response.status_code == 200
        data = response.json()
        assert data["gid"] == "123"
        assert data["page"] == 5
        assert data["total"] == 20
        assert "token" not in data

    def test_returns_404_when_not_found(self):
        mock_db = MagicMock()
        mock_db.get_bookmark = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/bookmarks/nonexistent")

        assert response.status_code == 404

    def test_calls_get_bookmark_with_gid(self):
        mock_db = MagicMock()
        mock_db.get_bookmark = AsyncMock(return_value=_SAMPLE)
        client = TestClient(_make_app(mock_db))

        client.get("/api/bookmarks/456")

        mock_db.get_bookmark.assert_called_once_with("456")


class TestDeleteBookmark:
    def test_returns_ok(self):
        mock_db = MagicMock()
        mock_db.delete_bookmark = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.delete("/api/bookmarks/123")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_calls_delete_with_gid(self):
        mock_db = MagicMock()
        mock_db.delete_bookmark = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        client.delete("/api/bookmarks/789")

        mock_db.delete_bookmark.assert_called_once_with("789")
