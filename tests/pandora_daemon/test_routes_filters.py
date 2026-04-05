"""Tests for pandora_daemon.routes.filters module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.filters import router
from pandora_daemon.state import AppState


def _make_app(mock_db):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.db = mock_db
    app.state.pandora = state
    return app


_SAMPLE = {
    "id": 1,
    "mode": 0,
    "text": "bad uploader",
    "enabled": True,
}


class TestListFilters:
    def test_returns_200_with_list(self):
        mock_db = MagicMock()
        mock_db.get_filters = AsyncMock(return_value=[_SAMPLE])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/filters")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["id"] == 1
        assert data[0]["mode"] == 0

    def test_returns_empty_list(self):
        mock_db = MagicMock()
        mock_db.get_filters = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/filters")

        assert response.status_code == 200
        assert response.json() == []

    def test_calls_get_filters(self):
        mock_db = MagicMock()
        mock_db.get_filters = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        client.get("/api/filters")

        mock_db.get_filters.assert_called_once()


class TestAddFilter:
    def test_returns_id(self):
        mock_db = MagicMock()
        mock_db.add_filter = AsyncMock(return_value=7)
        client = TestClient(_make_app(mock_db))

        response = client.post("/api/filters", json={"mode": 0, "text": "bad uploader"})

        assert response.status_code == 200
        assert response.json() == {"id": 7}

    def test_calls_add_with_mode_and_text(self):
        mock_db = MagicMock()
        mock_db.add_filter = AsyncMock(return_value=1)
        client = TestClient(_make_app(mock_db))

        client.post("/api/filters", json={"mode": 2, "text": "tag:foo"})

        mock_db.add_filter.assert_called_once_with(2, "tag:foo")


class TestToggleFilter:
    def test_returns_ok(self):
        mock_db = MagicMock()
        mock_db.toggle_filter = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.put("/api/filters/1")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_calls_toggle_with_id(self):
        mock_db = MagicMock()
        mock_db.toggle_filter = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        client.put("/api/filters/42")

        mock_db.toggle_filter.assert_called_once_with(42)


class TestDeleteFilter:
    def test_returns_ok(self):
        mock_db = MagicMock()
        mock_db.delete_filter = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.delete("/api/filters/1")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_calls_delete_with_id(self):
        mock_db = MagicMock()
        mock_db.delete_filter = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        client.delete("/api/filters/55")

        mock_db.delete_filter.assert_called_once_with(55)
