"""Tests for pandora_daemon.routes.favorites module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.favorites import router
from pandora_daemon.state import AppState


def _make_gallery_item(
    gid="12345",
    token="abcdef",
    title="Test Gallery",
    category="Doujinshi",
    uploader="testuser",
    thumb_url="https://example.com/thumb.jpg",
    posted="2023-01-01",
    rating=4.5,
    pages=20,
    rated=False,
    thumb_width=250,
    thumb_height=350,
    url="https://exhentai.org/g/12345/abcdef/",
):
    item = MagicMock()
    item.gid = gid
    item.token = token
    item.title = title
    item.category = category
    item.uploader = uploader
    item.thumb_url = thumb_url
    item.posted = posted
    item.rating = rating
    item.pages = pages
    item.rated = rated
    item.thumb_width = thumb_width
    item.thumb_height = thumb_height
    item.url = url
    return item


def _make_app(mock_provider):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.provider = mock_provider
    app.state.pandora = state
    return app


class TestGetFavorites:
    def test_get_favorites_returns_200_with_categories_and_galleries(self):
        mock_provider = MagicMock()

        category = MagicMock()
        category.slot = 0
        category.name = "My Favorites"
        category.count = 10

        gallery = _make_gallery_item()

        favorites_resp = MagicMock()
        favorites_resp.categories = [category]
        favorites_resp.galleries = [gallery]

        mock_provider.get_favorites = AsyncMock(return_value=favorites_resp)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/favorites")

        assert response.status_code == 200
        data = response.json()
        assert "categories" in data
        assert "galleries" in data
        assert len(data["categories"]) == 1
        assert len(data["galleries"]) == 1

        cat = data["categories"][0]
        assert cat["slot"] == 0
        assert cat["name"] == "My Favorites"
        assert cat["count"] == 10

        gal = data["galleries"][0]
        assert gal["gid"] == "12345"
        assert gal["title"] == "Test Gallery"

    def test_get_favorites_default_params(self):
        mock_provider = MagicMock()
        favorites_resp = MagicMock()
        favorites_resp.categories = []
        favorites_resp.galleries = []
        mock_provider.get_favorites = AsyncMock(return_value=favorites_resp)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.get("/api/favorites")

        mock_provider.get_favorites.assert_called_once_with(
            slot=-1,
            page=0,
            keyword="",
            search_name=False,
            search_tags=False,
            search_notes=False,
        )

    def test_get_favorites_with_slot_and_page(self):
        mock_provider = MagicMock()
        favorites_resp = MagicMock()
        favorites_resp.categories = []
        favorites_resp.galleries = []
        mock_provider.get_favorites = AsyncMock(return_value=favorites_resp)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.get("/api/favorites?slot=2&page=3&keyword=test&sn=true&st=true&sf=true")

        mock_provider.get_favorites.assert_called_once_with(
            slot=2,
            page=3,
            keyword="test",
            search_name=True,
            search_tags=True,
            search_notes=True,
        )


class TestAddFavorite:
    def test_add_favorite_returns_ok(self):
        mock_provider = MagicMock()
        mock_provider.add_favorite = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.post(
            "/api/favorites",
            json={"gid": "12345", "token": "abcdef", "slot": 1, "note": "great gallery"},
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_add_favorite_calls_provider_with_correct_args(self):
        mock_provider = MagicMock()
        mock_provider.add_favorite = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.post(
            "/api/favorites",
            json={"gid": "99999", "token": "xyz123", "slot": 3, "note": "my note"},
        )

        mock_provider.add_favorite.assert_called_once_with(
            "99999", "xyz123", slot=3, note="my note"
        )

    def test_add_favorite_default_slot_and_note(self):
        mock_provider = MagicMock()
        mock_provider.add_favorite = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.post("/api/favorites", json={"gid": "111", "token": "aaa"})

        mock_provider.add_favorite.assert_called_once_with(
            "111", "aaa", slot=0, note=""
        )


class TestModifyFavorites:
    def test_modify_favorites_returns_ok(self):
        mock_provider = MagicMock()
        mock_provider.modify_favorites = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.request(
            "DELETE",
            "/api/favorites",
            json={"gids": ["12345", "67890"], "action": "delete"},
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_modify_favorites_calls_provider_with_correct_args(self):
        mock_provider = MagicMock()
        mock_provider.modify_favorites = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.request(
            "DELETE",
            "/api/favorites",
            json={"gids": ["111", "222", "333"], "action": "delete"},
        )

        mock_provider.modify_favorites.assert_called_once_with(["111", "222", "333"], "delete")
