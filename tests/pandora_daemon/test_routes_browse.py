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

    def test_search_forwards_complete_advanced_parameters(self):
        mock_api = MagicMock()
        mock_api.search = AsyncMock(return_value=[])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get(
            "/api/search"
            "?keyword=stocking"
            "&page=2"
            "&category=1"
            "&min_rating=4"
            "&search_name=true"
            "&search_tags=true"
            "&search_description=true"
            "&search_torrent=true"
            "&search_low_power_tags=true"
            "&disable_language_filter=true"
            "&show_expunged=true"
            "&min_pages=10"
            "&max_pages=30"
        )

        assert response.status_code == 200
        call_args = mock_api.search.call_args
        search_params = call_args[0][0]
        assert search_params.f_search == "stocking"
        assert call_args[1]["page"] == 2
        assert search_params.f_cats == 1
        assert search_params.advsearch is True
        assert search_params.f_sr is True
        assert search_params.f_srdd == 4
        assert search_params.f_sname is True
        assert search_params.f_stags is True
        assert search_params.f_sdesc is True
        assert search_params.f_storr is True
        assert search_params.f_sto is True
        assert search_params.f_sdt1 is True
        assert search_params.f_sh is True
        assert search_params.f_sp is True
        assert search_params.f_spf == 10
        assert search_params.f_spt == 30


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
        toplist_item.link = "https://exhentai.org/g/999/aabbccddee/"

        mock_api.get_toplist = AsyncMock(return_value=[toplist_item])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/toplist")

        assert response.status_code == 200
        mock_api.get_toplist.assert_called_once_with("15")

    def test_toplist_returns_gallery_item_format(self):
        mock_api = AsyncMock()
        from exhentai_api.models.toplist import TopListItem
        mock_api.get_toplist.return_value = [
            TopListItem(type="All-Time", name="Gallery A", link="https://exhentai.org/g/111/aaa1111111/"),
            TopListItem(type="All-Time", name="Gallery B", link="https://exhentai.org/g/222/bbb2222222/"),
        ]
        app = _make_app(mock_api)
        client = TestClient(app)

        resp = client.get("/api/toplist?tl=15")
        data = resp.json()
        assert len(data) == 2
        assert data[0]["gid"] == "111"
        assert data[0]["token"] == "aaa1111111"
        assert data[0]["title"] == "Gallery A"
        assert "category" in data[0]
        assert "thumb_url" in data[0]
        assert "url" in data[0]
        assert data[1]["gid"] == "222"


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

        response = client.get("/api/image/proxy?url=https://exhentai.org/images/img.jpg")

        assert response.status_code == 200
        assert response.content == b"\xff\xd8\xff\xe0cached"
        mock_image_service.proxy_image.assert_awaited_once_with("https://exhentai.org/images/img.jpg")

    def test_image_proxy_missing_url(self):
        """Request without url parameter returns 422."""
        mock_api = MagicMock()
        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/image/proxy")

        assert response.status_code == 422

    def test_image_proxy_rejects_non_allowlisted_url(self):
        mock_api = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.proxy_image.side_effect = PermissionError("nope")

        app = _make_app(mock_api, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/image/proxy?url=https://example.com/img.jpg")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid image URL"
        mock_image_service.proxy_image.assert_called_once_with("https://example.com/img.jpg")

    def test_image_proxy_hides_fetch_errors(self):
        mock_api = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.proxy_image.side_effect = RuntimeError("upstream failure leaked")

        app = _make_app(mock_api, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/image/proxy?url=https://exhentai.org/images/img.jpg")

        assert response.status_code == 502
        assert response.json()["detail"] == "Failed to fetch image"
