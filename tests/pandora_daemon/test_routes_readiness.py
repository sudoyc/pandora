from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from pandora_daemon.providers.errors import (
    ProviderAuthenticationError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderSessionError,
    ProviderUpstreamError,
)
from pandora_daemon.config import PandoraConfig, ProviderConfig
from pandora_daemon.providers import GallerySearchQuery
from pandora_daemon.routes import router
from pandora_daemon.routes.readiness import _run_probe
from pandora_daemon.state import AppState


SCHEMA_PATH = Path("docs/agent/schemas/readiness-response.schema.json")
CHECK_NAMES = ("homepage", "search", "popular", "home")


def _make_app(
    provider_config: ProviderConfig | None = None,
    *,
    auth_configured: bool = False,
):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.config = PandoraConfig(provider=provider_config or ProviderConfig())
    provider = MagicMock()
    provider.auth_configured = auth_configured
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


def test_readiness_without_configured_provider_is_deterministic_and_does_not_probe():
    app, provider = _make_app(
        ProviderConfig(
            id="fixture-provider",
            credentials={"opaque": "sensitive-partial-cookie"},
        ),
        auth_configured=False,
    )

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
    app, provider = _make_app(
        ProviderConfig(
            id="fixture-provider",
            credentials={
                "opaque_a": "sensitive-credential-a",
                "opaque_b": "sensitive-credential-b",
            },
        ),
        auth_configured=True,
    )

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
    assert "sensitive-credential-a" not in response.text
    assert "sensitive-credential-b" not in response.text


@pytest.mark.parametrize(
    ("exception", "status", "session"),
    [
        (ProviderAuthenticationError("sensitive auth detail"), "auth", "invalid"),
        (ProviderSessionError("sensitive session detail"), "session", "invalid"),
        (ProviderUpstreamError("sensitive upstream detail"), "upstream", "valid"),
        (ProviderParseError("sensitive parse detail"), "parse", "valid"),
        (ProviderNetworkError("sensitive network detail"), "network", "valid"),
    ],
)
def test_readiness_classifies_failures_without_short_circuiting_or_leaking(
    exception,
    status,
    session,
):
    app, provider = _make_app(
        ProviderConfig(id="fixture-provider"),
        auth_configured=True,
    )
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
    app, provider = _make_app(
        ProviderConfig(id="fixture-provider"),
        auth_configured=True,
    )
    for method in (
        provider.get_homepage,
        provider.search,
        provider.get_popular,
        provider.get_home_detail,
    ):
        method.side_effect = ProviderNetworkError("sensitive network detail")

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
