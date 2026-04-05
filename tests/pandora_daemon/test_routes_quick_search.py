"""Tests for pandora_daemon.routes.quick_search module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.quick_search import router
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
    "name": "My Search",
    "keyword": "artist:foo",
    "category": None,
    "min_rating": None,
    "page_from": None,
    "page_to": None,
    "time": 1700000000,
}


class TestListQuickSearches:
    def test_returns_200_with_list(self):
        mock_db = MagicMock()
        mock_db.get_quick_searches = AsyncMock(return_value=[_SAMPLE])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/quick-search")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["id"] == 1
        assert data[0]["name"] == "My Search"

    def test_returns_empty_list(self):
        mock_db = MagicMock()
        mock_db.get_quick_searches = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        response = client.get("/api/quick-search")

        assert response.status_code == 200
        assert response.json() == []

    def test_calls_get_quick_searches(self):
        mock_db = MagicMock()
        mock_db.get_quick_searches = AsyncMock(return_value=[])
        client = TestClient(_make_app(mock_db))

        client.get("/api/quick-search")

        mock_db.get_quick_searches.assert_called_once()


class TestAddQuickSearch:
    def test_returns_id(self):
        mock_db = MagicMock()
        mock_db.add_quick_search = AsyncMock(return_value=42)
        client = TestClient(_make_app(mock_db))

        response = client.post(
            "/api/quick-search",
            json={"name": "My Search", "keyword": "artist:foo"},
        )

        assert response.status_code == 200
        assert response.json() == {"id": 42}

    def test_calls_add_with_all_fields(self):
        mock_db = MagicMock()
        mock_db.add_quick_search = AsyncMock(return_value=1)
        client = TestClient(_make_app(mock_db))

        client.post(
            "/api/quick-search",
            json={
                "name": "Full Search",
                "keyword": "tag:foo",
                "category": 2,
                "min_rating": 3,
                "page_from": 10,
                "page_to": 50,
            },
        )

        mock_db.add_quick_search.assert_called_once_with(
            "Full Search",
            keyword="tag:foo",
            category=2,
            min_rating=3,
            page_from=10,
            page_to=50,
        )

    def test_optional_fields_default_to_none(self):
        mock_db = MagicMock()
        mock_db.add_quick_search = AsyncMock(return_value=1)
        client = TestClient(_make_app(mock_db))

        client.post("/api/quick-search", json={"name": "Minimal"})

        mock_db.add_quick_search.assert_called_once_with(
            "Minimal",
            keyword="",
            category=None,
            min_rating=None,
            page_from=None,
            page_to=None,
        )


class TestDeleteQuickSearch:
    def test_returns_ok(self):
        mock_db = MagicMock()
        mock_db.delete_quick_search = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        response = client.delete("/api/quick-search/1")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_calls_delete_with_id(self):
        mock_db = MagicMock()
        mock_db.delete_quick_search = AsyncMock(return_value=None)
        client = TestClient(_make_app(mock_db))

        client.delete("/api/quick-search/99")

        mock_db.delete_quick_search.assert_called_once_with(99)
