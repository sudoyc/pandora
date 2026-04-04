"""Tests for pandora_daemon.routes.downloads module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.download import DownloadTask
from pandora_daemon.routes.downloads import router
from pandora_daemon.state import AppState


def _make_app(mock_downloads):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.downloads = mock_downloads
    app.state.pandora = state
    return app


def _make_task(
    gid="123",
    token="abc",
    title="Test Gallery",
    total_pages=10,
    output_dir="/tmp/dl",
    status="queued",
    downloaded_pages=0,
):
    return DownloadTask(
        gid=gid,
        token=token,
        title=title,
        total_pages=total_pages,
        output_dir=output_dir,
        status=status,
        downloaded_pages=downloaded_pages,
    )


class TestSubmitDownload:
    def test_submit_download_returns_200_with_task_dict(self):
        mock_downloads = MagicMock()
        task = _make_task()
        mock_downloads.submit = AsyncMock(return_value=task)

        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.post("/api/downloads", json={"gid": "123", "token": "abc"})

        assert response.status_code == 200
        data = response.json()
        assert data["gid"] == "123"
        assert data["token"] == "abc"
        assert data["title"] == "Test Gallery"
        assert data["total_pages"] == 10
        assert data["status"] == "queued"

    def test_submit_download_calls_downloads_submit_with_correct_args(self):
        mock_downloads = MagicMock()
        task = _make_task()
        mock_downloads.submit = AsyncMock(return_value=task)

        app = _make_app(mock_downloads)
        client = TestClient(app)

        client.post("/api/downloads", json={"gid": "456", "token": "xyz"})

        mock_downloads.submit.assert_called_once_with("456", "xyz")

    def test_submit_download_duplicate_returns_409(self):
        mock_downloads = MagicMock()
        mock_downloads.submit = AsyncMock(
            side_effect=ValueError("Gallery 123 is already queued or downloading")
        )

        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.post("/api/downloads", json={"gid": "123", "token": "abc"})

        assert response.status_code == 409
        data = response.json()
        assert "123" in data["detail"]


class TestListDownloads:
    def test_get_downloads_returns_200_with_task_list(self):
        mock_downloads = MagicMock()
        task = _make_task()
        mock_downloads.status = MagicMock(return_value=[task])

        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.get("/api/downloads")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["gid"] == "123"
        assert data[0]["title"] == "Test Gallery"

    def test_get_downloads_returns_empty_list_when_no_tasks(self):
        mock_downloads = MagicMock()
        mock_downloads.status = MagicMock(return_value=[])

        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.get("/api/downloads")

        assert response.status_code == 200
        assert response.json() == []

    def test_get_downloads_returns_multiple_tasks(self):
        mock_downloads = MagicMock()
        tasks = [
            _make_task(gid="1", token="t1", title="Gallery 1"),
            _make_task(gid="2", token="t2", title="Gallery 2", status="downloading"),
            _make_task(gid="3", token="t3", title="Gallery 3", status="completed"),
        ]
        mock_downloads.status = MagicMock(return_value=tasks)

        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.get("/api/downloads")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["gid"] == "1"
        assert data[1]["status"] == "downloading"
        assert data[2]["status"] == "completed"


class TestCancelDownload:
    def test_cancel_download_returns_success_true(self):
        mock_downloads = MagicMock()
        mock_downloads.cancel = AsyncMock(return_value=True)

        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.delete("/api/downloads/123")

        assert response.status_code == 200
        assert response.json() == {"success": True}

    def test_cancel_download_calls_cancel_with_gid(self):
        mock_downloads = MagicMock()
        mock_downloads.cancel = AsyncMock(return_value=True)

        app = _make_app(mock_downloads)
        client = TestClient(app)

        client.delete("/api/downloads/456")

        mock_downloads.cancel.assert_called_once_with("456")

    def test_cancel_nonexistent_returns_success_false(self):
        mock_downloads = MagicMock()
        mock_downloads.cancel = AsyncMock(return_value=False)

        app = _make_app(mock_downloads)
        client = TestClient(app)

        response = client.delete("/api/downloads/nonexistent")

        assert response.status_code == 200
        assert response.json() == {"success": False}
