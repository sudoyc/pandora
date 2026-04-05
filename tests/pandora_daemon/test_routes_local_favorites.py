"""Tests for pandora_daemon.routes.local_favorites module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.local_favorites import router
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
    "time": 1700000000,
}

_ADD_BODY = {
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
}


class TestListLocalFavorites:
    def test_returns_200_with_list(self):
        mock_db = MagicMock()
        mock_db.get_local_favorites = AsyncMock(return_value=[_SAMPLE])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/local-favorites")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["gid"] == "123"

    def test_returns_empty_list(self):
        mock_db = MagicMock()
        mock_db.get_local_favorites = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/local-favorites")

        assert response.status_code == 200
        assert response.json() == []

    def test_passes_limit_and_offset(self):
        mock_db = MagicMock()
        mock_db.get_local_favorites = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        client.get("/api/local-favorites?limit=10&offset=5")

        mock_db.get_local_favorites.assert_called_once_with(10, 5)

    def test_default_limit_offset(self):
        mock_db = MagicMock()
        mock_db.get_local_favorites = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        client.get("/api/local-favorites")

        mock_db.get_local_favorites.assert_called_once_with(50, 0)


class TestAddLocalFavorite:
    def test_returns_ok(self):
        mock_db = MagicMock()
        mock_db.add_local_favorite = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.post("/api/local-favorites", json=_ADD_BODY)

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_calls_add_with_gallery_object(self):
        mock_db = MagicMock()
        mock_db.add_local_favorite = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        client.post("/api/local-favorites", json=_ADD_BODY)

        mock_db.add_local_favorite.assert_called_once()
        arg = mock_db.add_local_favorite.call_args[0][0]
        assert arg.gid == "123"
        assert arg.token == "abc"
        assert arg.title == "Test Gallery"
        assert arg.rating == 4.5

    def test_optional_fields_have_defaults(self):
        mock_db = MagicMock()
        mock_db.add_local_favorite = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.post(
            "/api/local-favorites",
            json={"gid": "999", "token": "xyz", "title": "Minimal"},
        )

        assert response.status_code == 200
        arg = mock_db.add_local_favorite.call_args[0][0]
        assert arg.gid == "999"
        assert arg.category == ""
        assert arg.rating == 0.0


class TestRemoveLocalFavorite:
    def test_returns_ok(self):
        mock_db = MagicMock()
        mock_db.remove_local_favorite = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.delete("/api/local-favorites/123")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_calls_remove_with_gid(self):
        mock_db = MagicMock()
        mock_db.remove_local_favorite = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        client.delete("/api/local-favorites/456")

        mock_db.remove_local_favorite.assert_called_once_with("456")
