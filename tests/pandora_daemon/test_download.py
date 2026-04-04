"""Tests for pandora_daemon.download module."""
from __future__ import annotations

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
    return DownloadConfig(path=str(tmp_path / "downloads"), concurrency=2)


@pytest.fixture
def state_file(tmp_path):
    return tmp_path / "downloads.json"


@pytest.fixture
def mock_api():
    api = AsyncMock()
    detail = MagicMock()
    detail.title = "Test Gallery"
    detail.pages = 3
    detail.preview_pages = 1
    detail.preview_urls = [
        "https://exhentai.org/s/abc/123-1",
        "https://exhentai.org/s/def/123-2",
        "https://exhentai.org/s/ghi/123-3",
    ]
    detail.gid = "123"
    detail.token = "abc"
    detail.url = "https://exhentai.org/g/123/abc/"
    api.get_gallery_details.return_value = detail
    return api


@pytest.fixture
def mock_ws():
    return AsyncMock()


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------


def test_sanitize_filename_removes_invalid_chars():
    """Characters invalid in filenames are stripped."""
    assert _sanitize_filename('hello/world:foo<bar>baz') == "helloworldfoobarbaz"


def test_sanitize_filename_keeps_normal_chars():
    """Normal alphanumeric characters are kept intact."""
    assert _sanitize_filename("test-gallery_123 (vol.1)") == "test-gallery_123 (vol.1)"


# ---------------------------------------------------------------------------
# DownloadTask
# ---------------------------------------------------------------------------


def test_download_task_creation():
    """DownloadTask is created with correct defaults."""
    task = DownloadTask(
        gid="123",
        token="abc",
        title="My Gallery",
        total_pages=10,
        output_dir="/tmp/dl",
    )
    assert task.status == "queued"
    assert task.downloaded_pages == 0
    assert task.error == ""
    assert task.created_at != ""
    assert task.preview_urls == []


def test_download_task_to_dict():
    """to_dict() returns a plain dict with all expected fields."""
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
    assert d["token"] == "xyz"
    assert d["title"] == "Gallery 42"
    assert d["total_pages"] == 5
    assert d["output_dir"] == "/tmp/42"
    assert d["status"] == "queued"
    assert d["downloaded_pages"] == 0
    assert d["error"] == ""
    assert "created_at" in d
    assert d["preview_urls"] == []


# ---------------------------------------------------------------------------
# DownloadManager.submit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_creates_task(mock_api, mock_ws, download_config, state_file):
    """submit() creates a task with the correct fields."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)

    task = await manager.submit("123", "abc")

    assert task.gid == "123"
    assert task.token == "abc"
    assert task.title == "Test Gallery"
    assert task.total_pages == 3
    assert len(task.preview_urls) == 3
    assert task.status == "queued"


@pytest.mark.asyncio
async def test_submit_broadcasts_queued_event(mock_api, mock_ws, download_config, state_file):
    """submit() broadcasts a download_queued WebSocket event."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)

    await manager.submit("123", "abc")

    mock_ws.broadcast.assert_awaited_once()
    call_args = mock_ws.broadcast.call_args[0][0]
    assert call_args["event"] == "download_queued"
    assert call_args["gid"] == "123"


@pytest.mark.asyncio
async def test_submit_duplicate_rejected(mock_api, mock_ws, download_config, state_file):
    """A second submit with the same gid raises ValueError."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)

    await manager.submit("123", "abc")

    with pytest.raises(ValueError, match="123"):
        await manager.submit("123", "abc")


@pytest.mark.asyncio
async def test_submit_saves_state(mock_api, mock_ws, download_config, state_file):
    """submit() persists state to the JSON file."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)

    await manager.submit("123", "abc")

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert "123" in data


# ---------------------------------------------------------------------------
# DownloadManager.status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_returns_all_tasks(mock_api, mock_ws, download_config, state_file):
    """status() returns a list containing all submitted tasks."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)

    await manager.submit("123", "abc")

    result = manager.status()
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].gid == "123"


@pytest.mark.asyncio
async def test_status_empty_initially(mock_api, mock_ws, download_config, state_file):
    """status() returns an empty list when no tasks have been submitted."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)

    result = manager.status()

    assert result == []


# ---------------------------------------------------------------------------
# DownloadManager.cancel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_marks_cancelled(mock_api, mock_ws, download_config, state_file):
    """cancel() sets status to 'cancelled' and returns True."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)
    await manager.submit("123", "abc")

    result = await manager.cancel("123")

    assert result is True
    assert manager._tasks["123"].status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_broadcasts_event(mock_api, mock_ws, download_config, state_file):
    """cancel() broadcasts a download_cancelled WebSocket event."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)
    await manager.submit("123", "abc")
    mock_ws.broadcast.reset_mock()

    await manager.cancel("123")

    mock_ws.broadcast.assert_awaited_once()
    call_args = mock_ws.broadcast.call_args[0][0]
    assert call_args["event"] == "download_cancelled"
    assert call_args["gid"] == "123"


@pytest.mark.asyncio
async def test_cancel_nonexistent(mock_api, mock_ws, download_config, state_file):
    """cancel() returns False for an unknown gid."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)

    result = await manager.cancel("999")

    assert result is False


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_and_load_state(mock_api, mock_ws, download_config, state_file):
    """After _save_state(), JSON file contains correct task data."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)
    await manager.submit("123", "abc")

    manager._save_state()

    data = json.loads(state_file.read_text())
    assert "123" in data
    assert data["123"]["gid"] == "123"
    assert data["123"]["title"] == "Test Gallery"
    assert data["123"]["total_pages"] == 3


@pytest.mark.asyncio
async def test_load_state_requeues_pending(mock_api, mock_ws, download_config, state_file):
    """_load_state() reads existing JSON and populates _tasks."""
    task = DownloadTask(
        gid="456",
        token="def",
        title="Persisted Gallery",
        total_pages=5,
        output_dir="/tmp/456",
        status="queued",
        preview_urls=["https://exhentai.org/s/zzz/456-1"],
    )
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"456": task.to_dict()}), encoding="utf-8")

    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)
    manager._load_state()

    assert "456" in manager._tasks
    assert manager._tasks["456"].title == "Persisted Gallery"
    assert manager._tasks["456"].status == "queued"


@pytest.mark.asyncio
async def test_load_state_missing_file(mock_api, mock_ws, download_config, state_file):
    """_load_state() is a no-op when the state file does not exist."""
    assert not state_file.exists()

    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)
    manager._load_state()

    assert manager._tasks == {}


# ---------------------------------------------------------------------------
# start() / shutdown()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_creates_workers(mock_api, mock_ws, download_config, state_file):
    """start() creates as many worker tasks as config.concurrency."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)

    await manager.start()

    try:
        assert len(manager._workers) == download_config.concurrency
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_saves_state(mock_api, mock_ws, download_config, state_file):
    """shutdown() persists state to disk."""
    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)
    await manager.start()
    await manager.submit("123", "abc")

    await manager.shutdown()

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert "123" in data


@pytest.mark.asyncio
async def test_start_requeues_unfinished_tasks(mock_api, mock_ws, download_config, state_file):
    """start() re-queues tasks that were queued/downloading when state was saved."""
    task = DownloadTask(
        gid="789",
        token="ghi",
        title="Interrupted Gallery",
        total_pages=2,
        output_dir="/tmp/789",
        status="downloading",
        preview_urls=[],
    )
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps({"789": task.to_dict()}), encoding="utf-8")

    manager = DownloadManager(mock_api, download_config, mock_ws, state_file)
    await manager.start()

    try:
        # Task should have been loaded and re-queued (status reset to "queued")
        assert "789" in manager._tasks
        assert manager._tasks["789"].status == "queued"
    finally:
        await manager.shutdown()
