"""Tests for pandora_daemon.routes.browse module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.browse import router
from pandora_daemon.state import AppState
from pandora_daemon.providers import GallerySearchQuery, GallerySummary


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
    return GallerySummary(
        gid=gid,
        token=token,
        title=title,
        category=category,
        uploader=uploader,
        thumb_url=thumb_url,
        posted=posted,
        rating=rating,
        pages=pages,
        rated=rated,
        thumb_width=thumb_width,
        thumb_height=thumb_height,
        url=url,
    )


def _make_app(mock_provider, mock_cache=None, mock_image_service=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.provider = mock_provider
    state.cache = mock_cache or MagicMock()
    state.image_service = mock_image_service or MagicMock()
    app.state.pandora = state
    return app


class TestHomepage:
    def test_homepage_returns_200_and_data(self):
        mock_provider = MagicMock()
        gallery = _make_gallery_item()
        mock_provider.get_homepage = AsyncMock(return_value=[gallery])

        app = _make_app(mock_provider)
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
        mock_provider.get_homepage.assert_called_once()

    def test_homepage_forwards_next_cursor(self):
        mock_provider = MagicMock()
        mock_provider.get_homepage = AsyncMock(return_value=[])

        response = TestClient(_make_app(mock_provider)).get("/api/homepage?next=4075469")

        assert response.status_code == 200
        mock_provider.get_homepage.assert_called_once_with(next_gid="4075469")


class TestSearch:
    def test_search_returns_200_and_calls_with_search_params(self):
        mock_provider = MagicMock()
        gallery = _make_gallery_item()
        mock_provider.search = AsyncMock(return_value=[gallery])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/search?keyword=test+gallery&page=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        call_args = mock_provider.search.call_args
        search_query = call_args[0][0]
        assert isinstance(search_query, GallerySearchQuery)
        assert search_query.keyword == "test gallery"
        assert call_args[1]["page"] == 1

    def test_search_forwards_next_cursor_instead_of_numeric_page(self):
        mock_provider = MagicMock()
        mock_provider.search = AsyncMock(return_value=[])

        response = TestClient(_make_app(mock_provider)).get(
            "/api/search?keyword=fixture&page=3&next=4075469"
        )

        assert response.status_code == 200
        call_args = mock_provider.search.call_args
        assert call_args[0][0].keyword == "fixture"
        assert call_args[1] == {"page": 3, "next_gid": "4075469"}

    def test_search_with_min_rating_sets_minimum_rating(self):
        mock_provider = MagicMock()
        mock_provider.search = AsyncMock(return_value=[])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/search?keyword=hello&min_rating=3")

        assert response.status_code == 200
        call_args = mock_provider.search.call_args
        search_query = call_args[0][0]
        assert isinstance(search_query, GallerySearchQuery)
        assert search_query.minimum_rating == 3

    def test_search_with_category_sets_category(self):
        mock_provider = MagicMock()
        mock_provider.search = AsyncMock(return_value=[])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/search?category=2")

        assert response.status_code == 200
        call_args = mock_provider.search.call_args
        search_query = call_args[0][0]
        assert isinstance(search_query, GallerySearchQuery)
        assert search_query.category == 2

    def test_search_default_params(self):
        mock_provider = MagicMock()
        mock_provider.search = AsyncMock(return_value=[])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/search")

        assert response.status_code == 200
        call_args = mock_provider.search.call_args
        search_query = call_args[0][0]
        assert isinstance(search_query, GallerySearchQuery)
        assert search_query.keyword == ""
        assert search_query.category is None
        assert search_query.minimum_rating is None
        assert search_query.search_name is False
        assert search_query.search_tags is False
        assert search_query.search_description is False
        assert search_query.search_torrents is False
        assert search_query.search_low_power_tags is False
        assert search_query.disable_language_filter is False
        assert search_query.show_expunged is False
        assert search_query.minimum_pages is None
        assert search_query.maximum_pages is None
        assert call_args[1]["page"] == 0

    def test_search_forwards_complete_advanced_parameters(self):
        mock_provider = MagicMock()
        mock_provider.search = AsyncMock(return_value=[])

        app = _make_app(mock_provider)
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
        call_args = mock_provider.search.call_args
        search_query = call_args[0][0]
        assert isinstance(search_query, GallerySearchQuery)
        assert search_query.keyword == "stocking"
        assert call_args[1]["page"] == 2
        assert search_query.category == 1
        assert search_query.minimum_rating == 4
        assert search_query.search_name is True
        assert search_query.search_tags is True
        assert search_query.search_description is True
        assert search_query.search_torrents is True
        assert search_query.search_low_power_tags is True
        assert search_query.disable_language_filter is True
        assert search_query.show_expunged is True
        assert search_query.minimum_pages == 10
        assert search_query.maximum_pages == 30


class TestPopular:
    def test_popular_returns_200(self):
        mock_provider = MagicMock()
        gallery1 = _make_gallery_item(gid="1", token="aaa", title="Popular 1")
        gallery2 = _make_gallery_item(gid="2", token="bbb", title="Popular 2")
        mock_provider.get_popular = AsyncMock(return_value=[gallery1, gallery2])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/popular")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["gid"] == "1"
        assert data[1]["gid"] == "2"
        mock_provider.get_popular.assert_called_once()


class TestToplist:
    def test_toplist_called_with_default_tl(self):
        mock_provider = MagicMock()

        toplist_item = _make_gallery_item(
            gid="999",
            token="aabbccddee",
            title="Test Doujin",
            category="Doujinshi",
        )

        mock_provider.get_toplist = AsyncMock(return_value=[toplist_item])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/toplist")

        assert response.status_code == 200
        mock_provider.get_toplist.assert_called_once_with("15")

    def test_toplist_returns_normalized_gallery_summary_format(self):
        mock_provider = MagicMock()
        mock_provider.get_toplist = AsyncMock(
            return_value=[
                _make_gallery_item(
                    gid="111",
                    token="aaa1111111",
                    title="Gallery A",
                    category="All-Time",
                    url="provider://toplist/gallery-a",
                ),
                _make_gallery_item(
                    gid="222",
                    token="bbb2222222",
                    title="Gallery B",
                    category="All-Time",
                    url="provider://toplist/gallery-b",
                ),
            ]
        )
        app = _make_app(mock_provider)
        client = TestClient(app)

        resp = client.get("/api/toplist?tl=15")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["gid"] == "111"
        assert data[0]["token"] == "aaa1111111"
        assert data[0]["title"] == "Gallery A"
        assert "category" in data[0]
        assert "thumb_url" in data[0]
        assert "url" in data[0]
        assert data[0]["category"] == "All-Time"
        assert data[0]["url"] == "provider://toplist/gallery-a"
        assert data[1]["gid"] == "222"


class TestWatched:
    def test_watched_called_with_page(self):
        mock_provider = MagicMock()
        gallery = _make_gallery_item()
        mock_provider.get_watched = AsyncMock(return_value=[gallery])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/watched?page=2")

        assert response.status_code == 200
        mock_provider.get_watched.assert_called_once_with(page=2)

    def test_watched_forwards_next_cursor(self):
        mock_provider = MagicMock()
        mock_provider.get_watched = AsyncMock(return_value=[])

        response = TestClient(_make_app(mock_provider)).get(
            "/api/watched?page=2&next=4075469"
        )

        assert response.status_code == 200
        mock_provider.get_watched.assert_called_once_with(
            page=2,
            next_gid="4075469",
        )

    def test_watched_default_page_zero(self):
        mock_provider = MagicMock()
        mock_provider.get_watched = AsyncMock(return_value=[])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/watched")

        assert response.status_code == 200
        mock_provider.get_watched.assert_called_once_with(page=0)


class TestImageProxy:
    def test_image_proxy_cached(self):
        """When cache has the image, return it without fetching."""
        mock_provider = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.proxy_image = AsyncMock(return_value=b"\xff\xd8\xff\xe0cached")

        app = _make_app(mock_provider, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/image/proxy?url=https://exhentai.org/images/img.jpg")

        assert response.status_code == 200
        assert response.content == b"\xff\xd8\xff\xe0cached"
        mock_image_service.proxy_image.assert_awaited_once_with("https://exhentai.org/images/img.jpg")

    def test_image_proxy_missing_url(self):
        """Request without url parameter returns 422."""
        mock_provider = MagicMock()
        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/image/proxy")

        assert response.status_code == 422

    def test_image_proxy_rejects_non_allowlisted_url(self):
        mock_provider = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.proxy_image.side_effect = PermissionError("nope")

        app = _make_app(mock_provider, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/image/proxy?url=https://example.com/img.jpg")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid image URL"
        mock_image_service.proxy_image.assert_called_once_with("https://example.com/img.jpg")

    def test_image_proxy_hides_fetch_errors(self):
        mock_provider = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.proxy_image.side_effect = RuntimeError("upstream failure leaked")

        app = _make_app(mock_provider, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/image/proxy?url=https://exhentai.org/images/img.jpg")

        assert response.status_code == 502
        assert response.json()["detail"] == "Failed to fetch image"
