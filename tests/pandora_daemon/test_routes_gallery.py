"""Tests for pandora_daemon.routes.gallery module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.gallery import router
from pandora_daemon.state import AppState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detail():
    d = MagicMock()
    d.gid = "123"
    d.token = "abc"
    d.title = "Test"
    d.title_jpn = "テスト"
    d.category = "Manga"
    d.uploader = "user"
    d.cover_url = "https://ex.com/cover.jpg"
    d.tags = {"parody": ["fate"]}
    d.pages = 10
    d.size = "50 MB"
    d.posted = "2026-01-01"
    d.favorite_slot = None
    d.preview_pages = 1
    d.preview_urls = []
    d.rating = 4.5
    d.rating_count = 100
    d.favorite_count = 50
    d.torrent_count = 2
    d.torrent_url = ""
    d.archive_url = ""
    d.parent_url = None
    d.newer_versions = []
    d.comments = []
    d.comments_has_more = False
    d.api_uid = "uid1"
    d.api_key = "key1"
    d.url = "https://exhentai.org/g/123/abc/"
    return d


def _make_app(mock_api, mock_cache=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.api = mock_api
    state.cache = mock_cache or MagicMock()
    app.state.pandora = state
    return app


def _make_cache_miss():
    """Return a MagicMock cache that always misses."""
    cache = MagicMock()
    cache.get_gallery = MagicMock(return_value=None)
    cache.put_gallery = MagicMock()
    return cache


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGalleryDetail:
    def test_gallery_detail(self):
        """Fetch gallery detail, verify 200 and serialized data."""
        mock_api = MagicMock()
        detail = _make_detail()
        mock_api.get_gallery_details = AsyncMock(return_value=detail)
        mock_cache = _make_cache_miss()

        app = _make_app(mock_api, mock_cache)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc")

        assert response.status_code == 200
        data = response.json()
        assert data["gid"] == "123"
        assert data["token"] == "abc"
        assert data["title"] == "Test"
        assert data["title_jpn"] == "テスト"
        assert data["category"] == "Manga"
        assert data["uploader"] == "user"
        assert data["pages"] == 10
        assert data["rating"] == 4.5
        assert data["rating_count"] == 100
        assert data["api_uid"] == "uid1"
        assert data["api_key"] == "key1"
        assert data["url"] == "https://exhentai.org/g/123/abc/"
        mock_api.get_gallery_details.assert_called_once_with("123", "abc")
        mock_cache.put_gallery.assert_called_once_with(detail)

    def test_gallery_detail_uses_cache(self):
        """When cache hits, API should NOT be called."""
        mock_api = MagicMock()
        mock_api.get_gallery_details = AsyncMock()
        detail = _make_detail()

        mock_cache = MagicMock()
        mock_cache.get_gallery = MagicMock(return_value=detail)

        app = _make_app(mock_api, mock_cache)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc")

        assert response.status_code == 200
        data = response.json()
        assert data["gid"] == "123"
        # API must NOT have been called because cache returned a hit
        mock_api.get_gallery_details.assert_not_called()
        mock_cache.get_gallery.assert_called_once_with("123", "abc")


class TestCommentGallery:
    def test_comment_gallery(self):
        """Post a comment, verify api.comment_gallery called correctly."""
        mock_api = MagicMock()
        mock_api.comment_gallery = AsyncMock(return_value={"status": "ok"})

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/comment",
            json={"comment": "Great gallery!", "edit_id": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        mock_api.comment_gallery.assert_called_once_with(
            "123", "abc", "Great gallery!", edit_id=None
        )

    def test_comment_gallery_with_edit_id(self):
        """Post an edit comment with a specific edit_id."""
        mock_api = MagicMock()
        mock_api.comment_gallery = AsyncMock(return_value=None)

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/comment",
            json={"comment": "Edited comment", "edit_id": 42},
        )

        assert response.status_code == 200
        mock_api.comment_gallery.assert_called_once_with(
            "123", "abc", "Edited comment", edit_id=42
        )


class TestRateGallery:
    def test_rate_gallery(self):
        """Post a rating, verify result. Cache provides api_uid/api_key."""
        mock_api = MagicMock()
        mock_api.rate_gallery = AsyncMock(return_value={"rating_avg": 4.5})
        detail = _make_detail()

        mock_cache = MagicMock()
        mock_cache.get_gallery = MagicMock(return_value=detail)

        app = _make_app(mock_api, mock_cache)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/rate",
            json={"rating": 8},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        mock_api.rate_gallery.assert_called_once_with("uid1", "key1", 123, "abc", 8)

    def test_rate_gallery_fetches_detail_on_cache_miss(self):
        """When cache misses, detail is fetched for api_uid/api_key."""
        mock_api = MagicMock()
        detail = _make_detail()
        mock_api.get_gallery_details = AsyncMock(return_value=detail)
        mock_api.rate_gallery = AsyncMock(return_value={})

        mock_cache = _make_cache_miss()

        app = _make_app(mock_api, mock_cache)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/rate",
            json={"rating": 6},
        )

        assert response.status_code == 200
        mock_api.get_gallery_details.assert_called_once_with("123", "abc")
        mock_api.rate_gallery.assert_called_once_with("uid1", "key1", 123, "abc", 6)


class TestTorrents:
    def test_torrents(self):
        """Verify torrent list is returned correctly."""
        mock_api = MagicMock()
        torrent = MagicMock()
        torrent.name = "Test Torrent"
        torrent.url = "https://exhentai.org/torrent/123/test.torrent"
        mock_api.get_torrent_list = AsyncMock(return_value=[torrent])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/torrents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Torrent"
        assert data[0]["url"] == "https://exhentai.org/torrent/123/test.torrent"
        mock_api.get_torrent_list.assert_called_once_with("123", "abc")

    def test_torrents_empty(self):
        """Empty torrent list returns an empty array."""
        mock_api = MagicMock()
        mock_api.get_torrent_list = AsyncMock(return_value=[])

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/torrents")

        assert response.status_code == 200
        assert response.json() == []


class TestArchive:
    def test_archive(self):
        """Verify archive data is returned correctly."""
        mock_api = MagicMock()
        archive = MagicMock()
        archive.funds = "5000 GP"
        archive.original = MagicMock()
        archive.original.url = "https://exhentai.org/archiver.php?orig"
        archive.original.size = "100 MB"
        archive.original.cost = "1000 GP"
        archive.resample = MagicMock()
        archive.resample.url = "https://exhentai.org/archiver.php?res"
        archive.resample.size = "20 MB"
        archive.resample.cost = "200 GP"
        mock_api.get_archive_list = AsyncMock(return_value=archive)

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/archive")

        assert response.status_code == 200
        data = response.json()
        assert data["funds"] == "5000 GP"
        assert data["original"]["size"] == "100 MB"
        assert data["original"]["cost"] == "1000 GP"
        assert data["resample"]["url"] == "https://exhentai.org/archiver.php?res"
        mock_api.get_archive_list.assert_called_once_with("123", "abc")

    def test_archive_no_options(self):
        """Archive with no original/resample returns only funds."""
        mock_api = MagicMock()
        archive = MagicMock()
        archive.funds = "0 GP"
        archive.original = None
        archive.resample = None
        mock_api.get_archive_list = AsyncMock(return_value=archive)

        app = _make_app(mock_api)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/archive")

        assert response.status_code == 200
        data = response.json()
        assert data == {"funds": "0 GP"}


class TestVoteComment:
    def test_vote_comment(self):
        """Vote on a comment, verify api.vote_comment called correctly."""
        mock_api = MagicMock()
        mock_api.vote_comment = AsyncMock(return_value={"comment_score": 5})
        detail = _make_detail()

        mock_cache = MagicMock()
        mock_cache.get_gallery = MagicMock(return_value=detail)

        app = _make_app(mock_api, mock_cache)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/vote_comment",
            json={"comment_id": 1, "vote": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        mock_api.vote_comment.assert_called_once_with("uid1", "key1", 123, "abc", 1, 1)
