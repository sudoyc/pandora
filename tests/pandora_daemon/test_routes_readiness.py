from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from exhentai_api.exceptions import (
    AuthenticationError,
    NetworkError,
    ParseError,
    SessionError,
    UpstreamError,
)
from pandora_daemon.config import CredentialsConfig, PandoraConfig
from pandora_daemon.providers import GallerySearchQuery
from pandora_daemon.routes import router
from pandora_daemon.routes.readiness import _run_probe
from pandora_daemon.state import AppState


SCHEMA_PATH = Path("docs/agent/schemas/readiness-response.schema.json")
CHECK_NAMES = ("homepage", "search", "popular", "home")


def _make_app(credentials: CredentialsConfig | None = None):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.config = PandoraConfig(credentials=credentials or CredentialsConfig())
    provider = MagicMock()
    provider.get_homepage = AsyncMock(return_value=[])
    provider.search = AsyncMock(return_value=[])
    provider.get_popular = AsyncMock(return_value=[])
    provider.get_home_detail = AsyncMock()
    state.provider = provider
    app.state.pandora = state
    return app, provider


def _validate_schema(data: dict) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(data)


@pytest.mark.asyncio
async def test_readiness_probe_timeout_is_classified_as_network():
    async def never_returns():
        await asyncio.Event().wait()

    with patch("pandora_daemon.routes.readiness._PROBE_TIMEOUT_SECONDS", 0.01):
        status = await asyncio.wait_for(_run_probe(never_returns), timeout=0.1)

    assert status == "network"


def test_readiness_without_credentials_is_deterministic_and_does_not_probe():
    app, provider = _make_app(CredentialsConfig(igneous="sensitive-partial-cookie"))

    response = TestClient(app).get("/api/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "ready": False,
        "auth_configured": False,
        "session": "not_configured",
        "checks": {name: "not_checked" for name in CHECK_NAMES},
    }
    _validate_schema(response.json())
    assert "sensitive-partial-cookie" not in response.text
    provider.get_homepage.assert_not_awaited()
    provider.search.assert_not_awaited()
    provider.get_popular.assert_not_awaited()
    provider.get_home_detail.assert_not_awaited()


def test_readiness_reports_ready_only_after_all_four_probes_succeed():
    credentials = CredentialsConfig(
        igneous="sensitive-igneous",
        ipb_member_id="sensitive-member",
    )
    app, provider = _make_app(credentials)

    response = TestClient(app).get("/api/readiness")

    assert response.status_code == 200
    assert response.json() == {
        "ready": True,
        "auth_configured": True,
        "session": "valid",
        "checks": {name: "ok" for name in CHECK_NAMES},
    }
    _validate_schema(response.json())
    provider.get_homepage.assert_awaited_once_with()
    provider.search.assert_awaited_once()
    search_query = provider.search.await_args.args[0]
    assert isinstance(search_query, GallerySearchQuery)
    assert search_query.keyword == "pandora-readiness-probe"
    provider.get_popular.assert_awaited_once_with()
    provider.get_home_detail.assert_awaited_once_with()
    assert "sensitive-igneous" not in response.text
    assert "sensitive-member" not in response.text


@pytest.mark.parametrize(
    ("exception", "status", "session"),
    [
        (AuthenticationError("sensitive auth detail"), "auth", "invalid"),
        (SessionError("sensitive session detail"), "session", "invalid"),
        (UpstreamError("sensitive upstream detail"), "upstream", "valid"),
        (ParseError("sensitive parse detail"), "parse", "valid"),
        (NetworkError("sensitive network detail"), "network", "valid"),
    ],
)
def test_readiness_classifies_failures_without_short_circuiting_or_leaking(
    exception,
    status,
    session,
):
    credentials = CredentialsConfig(igneous="fixture", ipb_member_id="fixture")
    app, provider = _make_app(credentials)
    provider.get_homepage.side_effect = exception

    response = TestClient(app).get("/api/readiness")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "ready": False,
        "auth_configured": True,
        "session": session,
        "checks": {
            "homepage": status,
            "search": "ok",
            "popular": "ok",
            "home": "ok",
        },
    }
    _validate_schema(data)
    provider.search.assert_awaited_once()
    provider.get_popular.assert_awaited_once_with()
    provider.get_home_detail.assert_awaited_once_with()
    assert "sensitive" not in response.text


def test_readiness_reports_unknown_session_when_transport_prevents_all_probes():
    credentials = CredentialsConfig(igneous="fixture", ipb_member_id="fixture")
    app, provider = _make_app(credentials)
    for method in (
        provider.get_homepage,
        provider.search,
        provider.get_popular,
        provider.get_home_detail,
    ):
        method.side_effect = NetworkError("sensitive network detail")

    response = TestClient(app).get("/api/readiness")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "ready": False,
        "auth_configured": True,
        "session": "unknown",
        "checks": {name: "network" for name in CHECK_NAMES},
    }
    _validate_schema(data)
    assert "sensitive" not in response.text
