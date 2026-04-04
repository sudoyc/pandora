"""Tests for pandora_daemon.routes.browse module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.browse import router
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


def _make_app(mock_api, mock_cache=None, mock_image_service=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.api = mock_api
    state.cache = mock_cache or MagicMock()
    state.image_service = mock_image_service or MagicMock()
    app.state.pandora = state
    return app


class TestHomepage:
    def test_homepage_returns_200_and_data(self):
        mock_api = MagicMock()
        gallery = _make_gallery_item()
        mock_api.get_homepage = AsyncMock(return_value=[gallery])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/homepage")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["gid"] == "12345"
        assert data[0]["title"] == "Test Gallery"
        assert data[0]["category"] == "Doujinshi"
        assert data[0]["rating"] == 4.5
        assert data[0]["pages"] == 20
        mock_api.get_homepage.assert_called_once()


class TestSearch:
    def test_search_returns_200_and_calls_with_search_params(self):
        mock_api = MagicMock()
        gallery = _make_gallery_item()
        mock_api.search = AsyncMock(return_value=[gallery])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/search?keyword=test+gallery&page=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        call_args = mock_api.search.call_args
        search_params = call_args[0][0]
        assert search_params.f_search == "test gallery"
        assert call_args[1]["page"] == 1

    def test_search_with_min_rating_sets_advsearch(self):
        mock_api = MagicMock()
        mock_api.search = AsyncMock(return_value=[])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/search?keyword=hello&min_rating=3")

        assert response.status_code == 200
        call_args = mock_api.search.call_args
        search_params = call_args[0][0]
        assert search_params.advsearch is True
        assert search_params.f_sr is True
        assert search_params.f_srdd == 3

    def test_search_with_category_sets_f_cats(self):
        mock_api = MagicMock()
        mock_api.search = AsyncMock(return_value=[])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/search?category=2")

        assert response.status_code == 200
        call_args = mock_api.search.call_args
        search_params = call_args[0][0]
        assert search_params.f_cats == 2

    def test_search_default_params(self):
        mock_api = MagicMock()
        mock_api.search = AsyncMock(return_value=[])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/search")

        assert response.status_code == 200
        call_args = mock_api.search.call_args
        search_params = call_args[0][0]
        assert search_params.f_search == ""
        assert search_params.f_cats is None
        assert search_params.advsearch is False
        assert call_args[1]["page"] == 0


class TestPopular:
    def test_popular_returns_200(self):
        mock_api = MagicMock()
        gallery1 = _make_gallery_item(gid="1", token="aaa", title="Popular 1")
        gallery2 = _make_gallery_item(gid="2", token="bbb", title="Popular 2")
        mock_api.get_popular = AsyncMock(return_value=[gallery1, gallery2])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/popular")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["gid"] == "1"
        assert data[1]["gid"] == "2"
        mock_api.get_popular.assert_called_once()


class TestToplist:
    def test_toplist_called_with_default_tl(self):
        mock_api = MagicMock()

        toplist_item = MagicMock()
        toplist_item.type = "Doujinshi"
        toplist_item.name = "Test Doujin"
        toplist_item.link = "https://exhentai.org/g/999/zzz/"

        mock_api.get_toplist = AsyncMock(return_value=[toplist_item])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/toplist")

        assert response.status_code == 200
        mock_api.get_toplist.assert_called_once_with("15")

    def test_toplist_returns_correct_fields(self):
        mock_api = MagicMock()

        toplist_item = MagicMock()
        toplist_item.type = "Manga"
        toplist_item.name = "Some Manga"
        toplist_item.link = "https://exhentai.org/g/777/xxx/"

        mock_api.get_toplist = AsyncMock(return_value=[toplist_item])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/toplist?tl=11")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["type"] == "Manga"
        assert data[0]["name"] == "Some Manga"
        assert data[0]["link"] == "https://exhentai.org/g/777/xxx/"
        mock_api.get_toplist.assert_called_once_with("11")


class TestWatched:
    def test_watched_called_with_page(self):
        mock_api = MagicMock()
        gallery = _make_gallery_item()
        mock_api.get_watched = AsyncMock(return_value=[gallery])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/watched?page=2")

        assert response.status_code == 200
        mock_api.get_watched.assert_called_once_with(page=2)

    def test_watched_default_page_zero(self):
        mock_api = MagicMock()
        mock_api.get_watched = AsyncMock(return_value=[])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/watched")

        assert response.status_code == 200
        mock_api.get_watched.assert_called_once_with(page=0)


class TestImageProxy:
    def test_image_proxy_cached(self):
        """When cache has the image, return it without fetching."""
        mock_api = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.proxy_image = AsyncMock(return_value=b"\xff\xd8\xff\xe0cached")

        app = _make_app(mock_api, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/image/proxy?url=https://example.com/img.jpg")

        assert response.status_code == 200
        assert response.content == b"\xff\xd8\xff\xe0cached"
        mock_image_service.proxy_image.assert_awaited_once_with("https://example.com/img.jpg")

    def test_image_proxy_missing_url(self):
        """Request without url parameter returns 422."""
        mock_api = MagicMock()
        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/image/proxy")

        assert response.status_code == 422
