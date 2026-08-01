"""Tests for pandora_daemon.routes.user module."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes.user import router
from pandora_daemon.state import AppState


def _make_app(mock_provider):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.provider = mock_provider
    app.state.pandora = state
    return app


def _make_home_detail(image_used=50, image_total=5000, reset_cost=50):
    detail = MagicMock()
    detail.image_used = image_used
    detail.image_total = image_total
    detail.reset_cost = reset_cost
    return detail


def _make_profile(display_name="TestUser", avatar_url="https://example.com/avatar.jpg"):
    profile = MagicMock()
    profile.display_name = display_name
    profile.avatar_url = avatar_url
    return profile


def _make_watched_tag(id=1, name="artist:test", watched=True, hidden=False, color="#ff0000", weight=10):
    tag = MagicMock()
    tag.id = id
    tag.name = name
    tag.watched = watched
    tag.hidden = hidden
    tag.color = color
    tag.weight = weight
    return tag


class TestGetHome:
    def test_get_home_returns_200_and_correct_fields(self):
        mock_provider = MagicMock()
        detail = _make_home_detail(image_used=100, image_total=5000, reset_cost=50)
        mock_provider.get_home_detail = AsyncMock(return_value=detail)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/home")

        assert response.status_code == 200
        data = response.json()
        assert data["image_used"] == 100
        assert data["image_total"] == 5000
        assert data["reset_cost"] == 50
        mock_provider.get_home_detail.assert_called_once()

    def test_get_home_calls_provider(self):
        mock_provider = MagicMock()
        mock_provider.get_home_detail = AsyncMock(return_value=_make_home_detail())

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.get("/api/home")

        mock_provider.get_home_detail.assert_called_once_with()


class TestResetLimit:
    def test_reset_limit_returns_200_and_home_fields(self):
        mock_provider = MagicMock()
        detail = _make_home_detail(image_used=0, image_total=5000, reset_cost=50)
        mock_provider.reset_image_limit = AsyncMock(return_value=detail)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.post("/api/home/reset_limit")

        assert response.status_code == 200
        data = response.json()
        assert data["image_used"] == 0
        assert data["image_total"] == 5000
        assert data["reset_cost"] == 50
        mock_provider.reset_image_limit.assert_called_once()

    def test_reset_limit_calls_reset_image_limit(self):
        mock_provider = MagicMock()
        mock_provider.reset_image_limit = AsyncMock(return_value=_make_home_detail())

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.post("/api/home/reset_limit")

        mock_provider.reset_image_limit.assert_called_once_with()


class TestGetProfile:
    def test_get_profile_returns_200_and_display_name(self):
        mock_provider = MagicMock()
        profile = _make_profile(display_name="SadPanda", avatar_url="https://example.com/panda.jpg")
        mock_provider.get_profile = AsyncMock(return_value=profile)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "SadPanda"
        assert data["avatar_url"] == "https://example.com/panda.jpg"

    def test_get_profile_calls_provider(self):
        mock_provider = MagicMock()
        mock_provider.get_profile = AsyncMock(return_value=_make_profile())

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.get("/api/profile")

        mock_provider.get_profile.assert_called_once_with()


class TestGetTags:
    def test_get_tags_returns_200_with_tag_list(self):
        mock_provider = MagicMock()
        tag = _make_watched_tag(id=7, name="artist:niku", watched=True, hidden=False, color="#123456", weight=5)
        mock_provider.get_user_tags = AsyncMock(return_value=[tag])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/tags")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == 7
        assert data[0]["name"] == "artist:niku"
        assert data[0]["watched"] is True
        assert data[0]["hidden"] is False
        assert data[0]["color"] == "#123456"
        assert data[0]["weight"] == 5

    def test_get_tags_returns_empty_list(self):
        mock_provider = MagicMock()
        mock_provider.get_user_tags = AsyncMock(return_value=[])

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.get("/api/tags")

        assert response.status_code == 200
        assert response.json() == []
        mock_provider.get_user_tags.assert_called_once_with()


class TestAddTag:
    def test_add_tag_returns_ok(self):
        mock_provider = MagicMock()
        mock_provider.add_tag = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.post(
            "/api/tags",
            json={"name": "artist:test", "watched": True, "hidden": False, "color": "#ff0000", "weight": 10},
        )

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_add_tag_calls_provider_with_correct_args(self):
        mock_provider = MagicMock()
        mock_provider.add_tag = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.post(
            "/api/tags",
            json={"name": "parody:bleach", "watched": False, "hidden": True, "color": "#aabbcc", "weight": 20},
        )

        mock_provider.add_tag.assert_called_once_with(
            "parody:bleach",
            watched=False,
            hidden=True,
            color="#aabbcc",
            weight=20,
        )

    def test_add_tag_uses_defaults(self):
        mock_provider = MagicMock()
        mock_provider.add_tag = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.post("/api/tags", json={"name": "language:english"})

        mock_provider.add_tag.assert_called_once_with(
            "language:english",
            watched=False,
            hidden=False,
            color="",
            weight=0,
        )


class TestDeleteTag:
    def test_delete_tag_returns_ok(self):
        mock_provider = MagicMock()
        mock_provider.delete_tag = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        response = client.delete("/api/tags/42")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_delete_tag_calls_provider_with_tag_id(self):
        mock_provider = MagicMock()
        mock_provider.delete_tag = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.delete("/api/tags/42")

        mock_provider.delete_tag.assert_called_once_with(42)

    def test_delete_tag_passes_correct_id(self):
        mock_provider = MagicMock()
        mock_provider.delete_tag = AsyncMock(return_value=None)

        app = _make_app(mock_provider)
        client = TestClient(app)

        client.delete("/api/tags/99")

        mock_provider.delete_tag.assert_called_once_with(99)
