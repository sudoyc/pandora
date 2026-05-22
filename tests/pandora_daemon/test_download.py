"""Tests for pandora_daemon.download module — offline library builder."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from pandora_daemon.config import DownloadConfig
from pandora_daemon.download import DownloadManager, DownloadTask, _sanitize_filename


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def download_config(tmp_path):
    return DownloadConfig(path=str(tmp_path / "downloads"), gallery_concurrency=2)


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
    detail.viewer_urls = [
        "https://exhentai.org/s/abc/123-1",
        "https://exhentai.org/s/def/123-2",
        "https://exhentai.org/s/ghi/123-3",
    ]
    detail.thumb_urls = [
        "https://exhentai.org/t/thumb1.jpg",
        "https://exhentai.org/t/thumb2.jpg",
        "https://exhentai.org/t/thumb3.jpg",
    ]
    detail.gid = "123"
    detail.token = "abc"
    detail.url = "https://exhentai.org/g/123/abc/"
    detail.category = "Manga"
    detail.uploader = "testuser"
    detail.cover_url = "https://exhentai.org/t/cover.jpg"
    detail.tags = {"parody": ["fate"]}
    detail.size = "50 MB"
    detail.posted = "2026-01-01"
    detail.favorite_slot = None
    detail.rating = 4.5
    detail.rating_count = 100
    detail.favorite_count = 50
    detail.torrent_count = 2
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


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------

def test_sanitize_filename_removes_invalid_chars():
    assert _sanitize_filename('hello/world:foo<bar>baz') == "helloworldfoobarbaz"


def test_sanitize_filename_keeps_normal_chars():
    assert _sanitize_filename("test-gallery_123 (vol.1)") == "test-gallery_123 (vol.1)"


# ---------------------------------------------------------------------------
# DownloadTask
# ---------------------------------------------------------------------------

def test_download_task_creation():
    task = DownloadTask(
        gid="123",
        token="abc",
        title="My Gallery",
        total_pages=10,
        output_dir="/tmp/dl",
    )
    assert task.status == "queued"
    assert task.downloaded_pages == 0
    assert task.downloaded_thumbs == 0
    assert task.cover_downloaded is False
    assert task.metadata_saved is False
    assert task.error == ""
    assert task.created_at != ""
    assert task.viewer_urls == []
    assert task.thumb_urls == []


def test_download_task_to_dict():
    task = DownloadTask(
        gid="42",
        token="xyz",
        title="Gallery 42",
        total_pages=5,
        output_dir="/tmp/42",
    )
    d = task.to_dict()
    assert isinstance(d, dict)
    assert d["gid"] == "42"
    assert d["downloaded_thumbs"] == 0
    assert d["cover_downloaded"] is False
    assert d["metadata_saved"] is False
    assert d["thumb_urls"] == []


def test_download_task_to_public_dict_redacts_internal_fields():
    task = DownloadTask(
        gid="42",
        token="xyz",
        title="Gallery 42",
        total_pages=5,
        output_dir="/tmp/42",
    )
    d = task.to_public_dict()
    assert isinstance(d, dict)
    assert d["gid"] == "42"
    assert d["title"] == "Gallery 42"
    assert "token" not in d
    assert "output_dir" not in d
    assert "viewer_urls" not in d
    assert "thumb_urls" not in d
    assert "thumb_sprites" not in d


# ---------------------------------------------------------------------------
# DownloadManager.submit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_creates_task(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)

    task = await manager.submit("123", "abc")

    assert task.gid == "123"
    assert task.token == "abc"
    assert task.title == "Test Gallery"
    assert task.total_pages == 3
    assert len(task.viewer_urls) == 3
    assert len(task.thumb_urls) == 3
    assert task.status == "queued"


@pytest.mark.asyncio
async def test_submit_broadcasts_queued_event(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)

    await manager.submit("123", "abc")

    mock_ws.broadcast.assert_awaited_once()
    call_args = mock_ws.broadcast.call_args[0][0]
    assert call_args["event"] == "download_queued"
    assert call_args["gid"] == "123"


@pytest.mark.asyncio
async def test_submit_duplicate_rejected(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)

    await manager.submit("123", "abc")

    with pytest.raises(ValueError, match="123"):
        await manager.submit("123", "abc")


@pytest.mark.asyncio
async def test_submit_duplicate_rejected_under_concurrency(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)

    async def slow_detail(gid, token):
        await asyncio.sleep(0.01)
        return mock_api.get_gallery_details.return_value

    mock_api.get_gallery_details.side_effect = slow_detail
    results = await asyncio.gather(
        manager.submit("123", "abc"),
        manager.submit("123", "abc"),
        return_exceptions=True,
    )

    assert sum(isinstance(r, DownloadTask) for r in results) == 1
    assert sum(isinstance(r, ValueError) for r in results) == 1
    assert len(manager._tasks) == 1


@pytest.mark.asyncio
async def test_submit_saves_state(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)

    await manager.submit("123", "abc")

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert "123" in data


# ---------------------------------------------------------------------------
# DownloadManager.status / cancel
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_returns_all_tasks(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    await manager.submit("123", "abc")

    result = manager.status()
    assert len(result) == 1
    assert result[0].gid == "123"


@pytest.mark.asyncio
async def test_cancel_marks_cancelled(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    await manager.submit("123", "abc")

    result = await manager.cancel("123")

    assert result is True
    assert manager._tasks["123"].status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_nonexistent(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)

    result = await manager.cancel("999")

    assert result is False


@pytest.mark.asyncio
async def test_submit_clears_cancelled_state_for_same_gid(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    await manager.submit("123", "abc")
    await manager.cancel("123")
    manager._download_gallery = AsyncMock()

    await manager.submit("123", "abc")
    await manager.start()

    try:
        await asyncio.wait_for(manager._queue.join(), timeout=1)
    finally:
        await manager.shutdown()

    assert "123" not in manager._cancelled
    assert manager._download_gallery.await_count >= 1


@pytest.mark.asyncio
async def test_resume_clears_cancelled_state_for_same_gid(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    manager._tasks["123"] = DownloadTask(
        gid="123",
        token="abc",
        title="Test Gallery",
        total_pages=3,
        output_dir=str(Path(download_config.path) / "123-Test Gallery"),
        status="paused",
    )
    manager._cancelled.add("123")
    manager._download_gallery = AsyncMock()

    assert await manager.resume("123") is True
    await manager.start()

    try:
        await asyncio.wait_for(manager._queue.join(), timeout=1)
    finally:
        await manager.shutdown()

    assert "123" not in manager._cancelled
    assert manager._download_gallery.await_count >= 1


@pytest.mark.asyncio
async def test_retry_failed_clears_cancelled_state_for_same_gid(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    manager._tasks["123"] = DownloadTask(
        gid="123",
        token="abc",
        title="Test Gallery",
        total_pages=3,
        output_dir=str(Path(download_config.path) / "123-Test Gallery"),
        status="completed_with_errors",
        failed_pages=[2],
    )
    manager._cancelled.add("123")
    manager._download_gallery = AsyncMock()

    assert await manager.retry_failed("123") is True
    await manager.start()

    try:
        await asyncio.wait_for(manager._queue.join(), timeout=1)
    finally:
        await manager.shutdown()

    assert "123" not in manager._cancelled
    assert manager._download_gallery.await_count >= 1


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_and_load_state(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    await manager.submit("123", "abc")

    manager._save_state()

    data = json.loads(state_file.read_text())
    assert "123" in data
    assert data["123"]["gid"] == "123"
    assert data["123"]["title"] == "Test Gallery"


@pytest.mark.asyncio
async def test_load_state_requeues_pending(mock_api, mock_ws, mock_image_service, download_config, state_file):
    task = DownloadTask(
        gid="456",
        token="def",
        title="Persisted Gallery",
        total_pages=5,
        output_dir="/tmp/456",
        status="queued",
        viewer_urls=["https://exhentai.org/s/zzz/456-1"],
        thumb_urls=["https://exhentai.org/t/t1.jpg"],
    )
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"456": task.to_dict()}), encoding="utf-8")

    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    manager._load_state()

    assert "456" in manager._tasks
    assert manager._tasks["456"].title == "Persisted Gallery"


@pytest.mark.asyncio
async def test_load_state_normalizes_page_state_keys(mock_api, mock_ws, mock_image_service, download_config, state_file):
    task = DownloadTask(
        gid="456",
        token="def",
        title="Persisted Gallery",
        total_pages=2,
        output_dir="/tmp/456",
        status="queued",
        page_states={1: "done", 2: "failed"},
    )
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"456": task.to_dict()}), encoding="utf-8")

    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    manager._load_state()

    assert manager._tasks["456"].page_states == {1: "done", 2: "failed"}


@pytest.mark.asyncio
async def test_save_state_writes_atomically(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    await manager.submit("123", "abc")

    manager._save_state()

    assert state_file.exists()
    assert not state_file.with_suffix(state_file.suffix + ".tmp").exists()
    assert json.loads(state_file.read_text())["123"]["gid"] == "123"


# ---------------------------------------------------------------------------
# start / shutdown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_creates_workers(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    await manager.start()

    try:
        assert len(manager._workers) == download_config.gallery_concurrency
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_saves_state(mock_api, mock_ws, mock_image_service, download_config, state_file):
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)
    await manager.start()
    await manager.submit("123", "abc")

    await manager.shutdown()

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert "123" in data


# ---------------------------------------------------------------------------
# Metadata writing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_metadata(mock_api, mock_ws, mock_image_service, download_config, state_file):
    """_write_metadata creates a valid metadata.json in the output dir."""
    manager = DownloadManager(mock_api, download_config, mock_ws, mock_image_service, state_file)

    detail = mock_api.get_gallery_details.return_value
    output_dir = Path(download_config.path) / "123-Test Gallery"
    output_dir.mkdir(parents=True, exist_ok=True)

    manager._write_metadata(detail, str(output_dir))

    meta_path = output_dir / "metadata.json"
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["gid"] == "123"
    assert meta["token"] == "abc"
    assert meta["url"] == "https://exhentai.org/g/123/abc/"
    assert meta["title"] == "Test Gallery"
    assert "downloaded_at" in meta
