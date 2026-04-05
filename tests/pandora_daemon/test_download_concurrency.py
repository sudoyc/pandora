"""Tests for download concurrency, retry, and atomic write."""
from __future__ import annotations

from pathlib import Path

import pytest

from pandora_daemon.download import DownloadTask, _atomic_write


class TestDownloadTaskNewFields:
    def test_page_states_default_empty(self):
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=5, output_dir="/tmp/dl",
        )
        assert task.page_states == {}
        assert task.failed_pages == []

    def test_page_states_in_to_dict(self):
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=5, output_dir="/tmp/dl",
        )
        task.page_states = {1: "done", 2: "failed"}
        task.failed_pages = [2]
        d = task.to_dict()
        assert d["page_states"] == {1: "done", 2: "failed"}
        assert d["failed_pages"] == [2]

    def test_page_states_serialization_roundtrip(self):
        """page_states keys survive JSON roundtrip (int keys become str)."""
        import json
        task = DownloadTask(
            gid="1", token="t", title="T", total_pages=3, output_dir="/tmp/dl",
        )
        task.page_states = {1: "done", 2: "pending", 3: "failed"}
        d = task.to_dict()
        raw = json.dumps(d)
        loaded = json.loads(raw)
        assert loaded["page_states"]["1"] == "done"


class TestAtomicWrite:
    def test_atomic_write_creates_file(self, tmp_path):
        target = tmp_path / "test.jpg"
        _atomic_write(target, b"image data")
        assert target.exists()
        assert target.read_bytes() == b"image data"

    def test_atomic_write_no_tmp_left(self, tmp_path):
        target = tmp_path / "test.jpg"
        _atomic_write(target, b"data")
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert tmp_files == []

    def test_atomic_write_overwrites_existing(self, tmp_path):
        target = tmp_path / "test.jpg"
        target.write_bytes(b"old")
        _atomic_write(target, b"new")
        assert target.read_bytes() == b"new"


import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from pandora_daemon.config import DownloadConfig
from pandora_daemon.download import DownloadManager


@pytest.fixture
def dl_config(tmp_path):
    return DownloadConfig(path=str(tmp_path / "downloads"), gallery_concurrency=1, page_concurrency=2)


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "downloads.json"


@pytest.fixture
def mock_api():
    api = AsyncMock()
    detail = MagicMock()
    detail.title = "Test Gallery"
    detail.title_jpn = "Test JPN"
    detail.pages = 3
    detail.preview_pages = 1
    detail.preview_urls = ["https://ex.org/s/a/1-1", "https://ex.org/s/b/1-2", "https://ex.org/s/c/1-3"]
    detail.thumb_urls = ["https://ex.org/t/1.jpg", "https://ex.org/t/2.jpg", "https://ex.org/t/3.jpg"]
    detail.thumb_sprites = []
    detail.gid = "1"
    detail.token = "t"
    detail.url = "https://ex.org/g/1/t/"
    detail.category = "Manga"
    detail.uploader = "user"
    detail.cover_url = "https://ex.org/t/cover.jpg"
    detail.tags = {}
    detail.size = "10 MB"
    detail.posted = "2026-01-01"
    detail.favorite_slot = None
    detail.rating = 4.0
    detail.rating_count = 10
    detail.favorite_count = 5
    detail.torrent_count = 0
    detail.comments = []
    detail.comments_has_more = False
    api.get_gallery_details.return_value = detail
    return api


@pytest.fixture
def mock_ws():
    return AsyncMock()


@pytest.fixture
def mock_image_service():
    svc = AsyncMock()
    svc.proxy_image.return_value = b"fake image bytes"
    return svc


class TestDownloadManagerInit:
    def test_constructor_accepts_image_service(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        assert mgr._image_service is mock_image_service

    def test_constructor_no_cache_param(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        assert not hasattr(mgr, '_cache')


class TestFetchImage:
    @pytest.mark.asyncio
    async def test_fetch_image_uses_image_service(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        result = await mgr._fetch_image("https://example.com/img.jpg")
        mock_image_service.proxy_image.assert_awaited_once_with("https://example.com/img.jpg")
        assert result == b"fake image bytes"


class TestDebounce:
    @pytest.mark.asyncio
    async def test_mark_dirty_creates_save_task(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        mgr._mark_dirty()
        assert mgr._save_task is not None
        assert not mgr._save_task.done()
        mgr._save_task.cancel()

    @pytest.mark.asyncio
    async def test_shutdown_cancels_debounce_and_saves(self, mock_api, mock_ws, mock_image_service, dl_config, state_file):
        mgr = DownloadManager(mock_api, dl_config, mock_ws, mock_image_service, state_file)
        await mgr.start()
        await mgr.submit("1", "t")
        mgr._mark_dirty()
        await mgr.shutdown()
        assert state_file.exists()
        assert mgr._save_task is None or mgr._save_task.done() or mgr._save_task.cancelled()
