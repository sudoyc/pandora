"""Tests for pandora_daemon.routes.gallery module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.gallery import router
from pandora_daemon.providers.contracts import GalleryComment, GalleryDetail
from pandora_daemon.state import AppState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_detail(*, pages: int = 10) -> GalleryDetail:
    return GalleryDetail(
        gid="123",
        token="abc",
        title="Test",
        title_jpn="テスト",
        category="Manga",
        uploader="user",
        cover_url="https://example.test/cover.jpg",
        tags={"parody": ["fate"]},
        pages=pages,
        size="50 MB",
        posted="2026-01-01",
        favorite_slot=None,
        url="https://example.test/g/123/abc/",
        provider_data=object(),
        preview_page_count=1,
        rating=4.5,
        rating_count=100,
        favorite_count=50,
        torrent_count=2,
        comments=(
            GalleryComment(
                id=7,
                user="reader",
                comment="Great gallery!",
                score=2,
                time="2026-01-01",
            ),
        ),
        comments_has_more=False,
    )


def _make_app(mock_provider, mock_cache=None, mock_image_service=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.provider = mock_provider
    state.cache = mock_cache or MagicMock()
    state.image_service = mock_image_service or MagicMock()
    mock_db = MagicMock()
    mock_db.put_history = AsyncMock()
    mock_db.update_bookmark = AsyncMock()
    state.db = mock_db
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
    def test_gallery_detail_serializes_exact_v1_shape(self):
        """Fetch gallery detail and preserve the exact v1 response shape."""
        mock_provider = MagicMock()
        detail = _make_detail()
        mock_provider.get_gallery_details = AsyncMock(return_value=detail)
        mock_cache = _make_cache_miss()

        app = _make_app(mock_provider, mock_cache)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc")

        assert response.status_code == 200
        data = response.json()
        assert data == {
            "gid": "123",
            "title": "Test",
            "title_jpn": "テスト",
            "category": "Manga",
            "uploader": "user",
            "cover_url": "https://example.test/cover.jpg",
            "tags": {"parody": ["fate"]},
            "pages": 10,
            "size": "50 MB",
            "posted": "2026-01-01",
            "favorite_slot": None,
            "preview_pages": 1,
            "rating": 4.5,
            "rating_count": 100,
            "favorite_count": 50,
            "torrent_count": 2,
            "comments": [
                {
                    "id": 7,
                    "user": "reader",
                    "comment": "Great gallery!",
                    "score": 2,
                    "time": "2026-01-01",
                    "is_uploader": False,
                    "vote_up_able": False,
                    "vote_down_able": False,
                    "vote_up_ed": False,
                    "vote_down_ed": False,
                    "editable": False,
                    "last_edited": "",
                }
            ],
            "comments_has_more": False,
            "url": "https://example.test/g/123/abc/",
        }
        mock_provider.get_gallery_details.assert_called_once_with("123", "abc")
        mock_cache.put_gallery.assert_called_once_with(detail)

    def test_gallery_detail_uses_cache(self):
        """When cache hits, the provider should not be called."""
        mock_provider = MagicMock()
        mock_provider.get_gallery_details = AsyncMock()
        detail = _make_detail()

        mock_cache = MagicMock()
        mock_cache.get_gallery = MagicMock(return_value=detail)

        app = _make_app(mock_provider, mock_cache)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc")

        assert response.status_code == 200
        data = response.json()
        assert data["gid"] == "123"
        # The provider must not be called because cache returned a hit.
        mock_provider.get_gallery_details.assert_not_called()
        mock_cache.get_gallery.assert_called_once_with("123", "abc")




class TestCommentGallery:
    def test_comment_gallery(self):
        """Post a comment and verify the provider call."""
        mock_provider = MagicMock()
        mock_provider.comment_gallery = AsyncMock(return_value={"status": "ok"})

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/comment",
            json={"comment": "Great gallery!", "edit_id": None},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        mock_provider.comment_gallery.assert_called_once_with(
            "123", "abc", "Great gallery!", edit_id=None
        )

    def test_comment_gallery_with_edit_id(self):
        """Post an edit comment with a specific edit_id."""
        mock_provider = MagicMock()
        mock_provider.comment_gallery = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/comment",
            json={"comment": "Edited comment", "edit_id": 42},
        )

        assert response.status_code == 200
        mock_provider.comment_gallery.assert_called_once_with(
            "123", "abc", "Edited comment", edit_id=42
        )


class TestRateGallery:
    def test_rate_gallery(self):
        """Post a rating with the normalized gallery detail."""
        mock_provider = MagicMock()
        mock_provider.rate_gallery = AsyncMock(return_value={"rating_avg": 4.5})
        detail = _make_detail()

        mock_cache = MagicMock()
        mock_cache.get_gallery = MagicMock(return_value=detail)

        app = _make_app(mock_provider, mock_cache)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/rate",
            json={"rating": 8},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        mock_provider.rate_gallery.assert_awaited_once_with(detail, 8)

    def test_rate_gallery_fetches_detail_on_cache_miss(self):
        """When cache misses, fetch a normalized gallery detail."""
        mock_provider = MagicMock()
        detail = _make_detail()
        mock_provider.get_gallery_details = AsyncMock(return_value=detail)
        mock_provider.rate_gallery = AsyncMock(return_value={})

        mock_cache = _make_cache_miss()

        app = _make_app(mock_provider, mock_cache)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/rate",
            json={"rating": 6},
        )

        assert response.status_code == 200
        mock_provider.get_gallery_details.assert_called_once_with("123", "abc")
        mock_provider.rate_gallery.assert_awaited_once_with(detail, 6)


class TestTorrents:
    def test_torrents(self):
        """Verify torrent list is returned correctly."""
        mock_provider = MagicMock()
        torrent = MagicMock()
        torrent.name = "Test Torrent"
        torrent.url = "https://exhentai.org/torrent/123/test.torrent"
        mock_provider.get_torrent_list = AsyncMock(return_value=[torrent])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/torrents")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Torrent"
        assert data[0]["url"] == "https://exhentai.org/torrent/123/test.torrent"
        mock_provider.get_torrent_list.assert_called_once_with("123", "abc")

    def test_torrents_empty(self):
        """Empty torrent list returns an empty array."""
        mock_provider = MagicMock()
        mock_provider.get_torrent_list = AsyncMock(return_value=[])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/torrents")

        assert response.status_code == 200
        assert response.json() == []


class TestArchive:
    def test_archive(self):
        """Verify archive data is returned correctly."""
        mock_provider = MagicMock()
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
        mock_provider.get_archive_list = AsyncMock(return_value=archive)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/archive")

        assert response.status_code == 200
        data = response.json()
        assert data["funds"] == "5000 GP"
        assert data["original"]["size"] == "100 MB"
        assert data["original"]["cost"] == "1000 GP"
        assert data["resample"]["url"] == "https://exhentai.org/archiver.php?res"
        mock_provider.get_archive_list.assert_called_once_with("123", "abc")

    def test_archive_no_options(self):
        """Archive with no original/resample returns only funds."""
        mock_provider = MagicMock()
        archive = MagicMock()
        archive.funds = "0 GP"
        archive.original = None
        archive.resample = None
        mock_provider.get_archive_list = AsyncMock(return_value=archive)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/archive")

        assert response.status_code == 200
        data = response.json()
        assert data == {"funds": "0 GP"}


class TestVoteComment:
    def test_vote_comment(self):
        """Vote on a comment with the normalized gallery detail."""
        mock_provider = MagicMock()
        mock_provider.vote_comment = AsyncMock(return_value={"comment_score": 5})
        detail = _make_detail()

        mock_cache = MagicMock()
        mock_cache.get_gallery = MagicMock(return_value=detail)

        app = _make_app(mock_provider, mock_cache)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/vote_comment",
            json={"comment_id": 1, "vote": 1},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        mock_provider.vote_comment.assert_awaited_once_with(detail, 1, 1)


class TestPageImage:
    def test_page_image_returns_bytes(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_page_image = AsyncMock(return_value=b"\xff\xd8page_image")

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/page/5")

        assert response.status_code == 200
        assert response.content == b"\xff\xd8page_image"
        mock_image_service.get_page_image.assert_awaited_once_with("123", "abc", 5)

    def test_page_image_invalid_page(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_page_image = AsyncMock(side_effect=ValueError("Page 99 out of range"))

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/page/99")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid page image request"
        assert "Page 99 out of range" not in response.json()["detail"]

    def test_page_image_runtime_error_is_sanitized_to_bad_request(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_page_image = AsyncMock(
            side_effect=RuntimeError("viewer token leaked")
        )

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/page/5")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid page image request"
        assert "viewer token leaked" not in response.json()["detail"]

    def test_page_image_upstream_failure_hides_exception_detail(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_page_image = AsyncMock(side_effect=Exception("upstream token leaked"))

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/page/5")

        assert response.status_code == 502
        assert response.json()["detail"] == "Failed to fetch page image"
        assert "upstream token leaked" not in response.json()["detail"]


class TestThumbnail:
    @pytest.mark.parametrize(
        ("image_bytes", "media_type"),
        [
            (b"\x89PNGthumbnail", "image/png"),
            (b"GIF89athumbnail", "image/gif"),
            (b"RIFF\x00\x00\x00\x00WEBPthumbnail", "image/webp"),
            (b"\xff\xd8thumbnail", "image/jpeg"),
        ],
    )
    def test_thumb_image_delegates_and_detects_media_type(self, image_bytes, media_type):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_thumbnail = AsyncMock(return_value=image_bytes)

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/thumb/5")

        assert response.status_code == 200
        assert response.content == image_bytes
        assert response.headers["content-type"] == media_type
        mock_image_service.get_thumbnail.assert_awaited_once_with("123", "abc", 5)
        mock_provider.get_gallery_details.assert_not_called()
        mock_cache.get_gallery.assert_not_called()

    def test_thumb_image_invalid_page_is_sanitized(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_thumbnail = AsyncMock(
            side_effect=ValueError("Page 99 out of range")
        )

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/thumb/99")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid thumbnail request"
        assert "Page 99 out of range" not in response.json()["detail"]

    def test_thumb_image_runtime_error_is_sanitized_to_bad_request(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_thumbnail = AsyncMock(
            side_effect=RuntimeError("provider preview URL leaked")
        )

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/thumb/5")

        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid thumbnail request"
        assert "provider preview URL leaked" not in response.json()["detail"]

    def test_thumb_image_missing_is_sanitized(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_thumbnail = AsyncMock(
            side_effect=LookupError("provider thumbnail URL leaked")
        )

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/thumb/5")

        assert response.status_code == 404
        assert response.json()["detail"] == "No thumbnail for page 5"
        assert "provider thumbnail URL leaked" not in response.json()["detail"]

    def test_thumb_image_upstream_failure_hides_exception_detail(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_image_service = MagicMock()
        mock_image_service.get_thumbnail = AsyncMock(
            side_effect=Exception("upstream token leaked")
        )

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.get("/api/gallery/123/abc/thumb/5")

        assert response.status_code == 502
        assert response.json()["detail"] == "Failed to fetch thumbnail"
        assert "upstream token leaked" not in response.json()["detail"]


class TestPrefetch:
    def test_prefetch_returns_ok(self):
        mock_provider = MagicMock()
        mock_cache = MagicMock()
        mock_cache.get_gallery = MagicMock(return_value=MagicMock(pages=20))
        mock_image_service = MagicMock()
        mock_image_service.prefetch = AsyncMock()

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/prefetch",
            json={"current_page": 5},
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_image_service.prefetch.assert_awaited_once()

    def test_prefetch_fetches_detail_on_cache_miss(self):
        mock_provider = MagicMock()
        detail = _make_detail(pages=20)
        mock_provider.get_gallery_details = AsyncMock(return_value=detail)
        mock_cache = _make_cache_miss()
        mock_image_service = MagicMock()
        mock_image_service.prefetch = AsyncMock()

        app = _make_app(mock_provider, mock_cache, mock_image_service=mock_image_service)
        client = TestClient(app)

        response = client.post(
            "/api/gallery/123/abc/prefetch",
            json={"current_page": 3},
        )

        assert response.status_code == 200
