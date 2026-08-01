"""Tests verifying auto-trigger of db.put_history and db.update_bookmark."""
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
    d.title = "Test Gallery"
    d.title_jpn = "テスト"
    d.category = "Manga"
    d.uploader = "user"
    d.cover_url = "https://ex.com/cover.jpg"
    d.tags = {"parody": ["fate"]}
    d.pages = 20
    d.size = "50 MB"
    d.posted = "2026-01-01"
    d.favorite_slot = None
    d.preview_pages = 1
    d.viewer_urls = []
    d.thumb_urls = []
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


def _make_app(mock_provider, mock_cache, mock_db, mock_image_service=None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.provider = mock_provider
    state.cache = mock_cache
    state.db = mock_db
    state.image_service = mock_image_service or MagicMock()
    app.state.pandora = state
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_get_gallery_detail_calls_put_history():
    """GET /api/gallery/{gid}/{token} should call db.put_history with the detail."""
    detail = _make_detail()

    mock_provider = MagicMock()
    mock_cache = MagicMock()
    mock_cache.get_gallery.return_value = detail  # cache hit — skip api call
    mock_db = MagicMock()
    mock_db.put_history = AsyncMock()

    app = _make_app(mock_provider, mock_cache, mock_db)
    client = TestClient(app)

    resp = client.get("/api/gallery/123/abc")
    assert resp.status_code == 200

    mock_db.put_history.assert_awaited_once_with(detail)


def test_get_gallery_detail_calls_put_history_on_cache_miss():
    """put_history is also called when detail comes from the API (cache miss)."""
    detail = _make_detail()

    mock_provider = MagicMock()
    mock_provider.get_gallery_details = AsyncMock(return_value=detail)
    mock_cache = MagicMock()
    mock_cache.get_gallery.return_value = None  # cache miss
    mock_db = MagicMock()
    mock_db.put_history = AsyncMock()

    app = _make_app(mock_provider, mock_cache, mock_db)
    client = TestClient(app)

    resp = client.get("/api/gallery/123/abc")
    assert resp.status_code == 200

    mock_db.put_history.assert_awaited_once_with(detail)


def test_prefetch_pages_calls_update_bookmark():
    """POST /api/gallery/{gid}/{token}/prefetch should call db.update_bookmark."""
    detail = _make_detail()

    mock_provider = MagicMock()
    mock_cache = MagicMock()
    mock_cache.get_gallery.return_value = detail
    mock_db = MagicMock()
    mock_db.update_bookmark = AsyncMock()
    mock_image_service = MagicMock()
    mock_image_service.prefetch = AsyncMock()

    app = _make_app(mock_provider, mock_cache, mock_db, mock_image_service)
    client = TestClient(app)

    resp = client.post("/api/gallery/123/abc/prefetch", json={"current_page": 5})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    mock_db.update_bookmark.assert_awaited_once_with(
        gid="123",
        token="abc",
        title=detail.title,
        thumb_url=detail.cover_url,
        page=5,
        total=detail.pages,
    )


def test_prefetch_pages_still_calls_image_service_prefetch():
    """update_bookmark does not replace the image_service.prefetch call."""
    detail = _make_detail()

    mock_provider = MagicMock()
    mock_cache = MagicMock()
    mock_cache.get_gallery.return_value = detail
    mock_db = MagicMock()
    mock_db.update_bookmark = AsyncMock()
    mock_image_service = MagicMock()
    mock_image_service.prefetch = AsyncMock()

    app = _make_app(mock_provider, mock_cache, mock_db, mock_image_service)
    client = TestClient(app)

    client.post("/api/gallery/123/abc/prefetch", json={"current_page": 3})

    mock_image_service.prefetch.assert_awaited_once_with("123", "abc", 3, detail.pages)
