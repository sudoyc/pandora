"""Cross-surface compatibility, error, and exit-code contract tests."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import validate

from pandora_daemon.providers.errors import (
    ProviderAuthenticationError,
    ProviderContentBlockedError,
    ProviderError,
    ProviderGalleryNotFoundError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderQuotaError,
    ProviderSessionError,
    ProviderUpstreamError,
)
from pandora_daemon.app import create_app
from pandora_daemon.cli import (
    _DOWNLOAD_FAILURE_EVENTS,
    _DOWNLOAD_SUCCESS_EVENTS,
    _consume_download_events,
    _machine_error,
)
from pandora_daemon.config import PandoraConfig
from pandora_daemon.routes.config import router as config_router
from pandora_daemon.state import AppState


REST_ERROR_MATRIX = [
    pytest.param(ProviderAuthenticationError("private"), 401, "auth", id="auth"),
    pytest.param(ProviderSessionError("private"), 401, "session", id="session"),
    pytest.param(ProviderUpstreamError(status_code=503), 502, "upstream", id="upstream"),
    pytest.param(ProviderGalleryNotFoundError("private"), 404, "gallery_not_found", id="not-found"),
    pytest.param(ProviderQuotaError("private"), 429, "image_limit", id="image-limit"),
    pytest.param(ProviderContentBlockedError("private"), 451, "offensive", id="offensive"),
    pytest.param(ProviderParseError("private"), 502, "parse", id="parse"),
    pytest.param(ProviderNetworkError("private"), 502, "network", id="network"),
    pytest.param(ProviderError("private", public_code="exhentai"), 500, "exhentai", id="upstream-fallback"),
    pytest.param(RuntimeError("private"), 500, "internal", id="runtime"),
    pytest.param(Exception("private"), 500, "internal", id="unhandled"),
]

CLI_MACHINE_ERROR_CODES = {
    "connect_error",
    "http_error",
    "invalid_argument",
    "invalid_gallery_target",
    "usage_error",
    "websocket_error",
    "websocket_dependency_missing",
}

DOWNLOAD_EVENT_EXIT_MATRIX = {
    "download_complete": 0,
    "download_complete_with_errors": 1,
    "download_error": 1,
    "download_cancelled": 1,
    "download_paused": 1,
    "download_auth_failed": 1,
}


def _load_schema(name: str) -> dict:
    path = Path("docs/agent/schemas") / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("error", "status", "code"), REST_ERROR_MATRIX)
def test_rest_service_error_matrix_matches_status_code_and_schema(error, status, code):
    app = create_app()

    async def raise_error():
        raise error

    app.add_api_route("/contract-error", raise_error, methods=["GET"])
    response = TestClient(app, raise_server_exceptions=False).get("/contract-error")

    assert response.status_code == status
    assert response.json()["error"] == code
    validate(response.json(), _load_schema("upstream-error.schema.json"))


def test_health_advertises_machine_contract_major():
    app = FastAPI()
    app.include_router(config_router)
    state = MagicMock(spec=AppState)
    state.config = PandoraConfig()
    state.provider = MagicMock(auth_configured=False)
    app.state.pandora = state

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    assert response.json()["contract_version"] == "1"


def test_cli_error_schema_covers_every_generic_machine_error_code():
    schema = _load_schema("cli-error-envelope.schema.json")

    assert set(schema["properties"]["error"]["properties"]["code"]["enum"]) == CLI_MACHINE_ERROR_CODES
    for code in CLI_MACHINE_ERROR_CODES:
        validate(_machine_error(code, "message"), schema)


@pytest.mark.asyncio
@pytest.mark.parametrize(("event_name", "expected_exit"), DOWNLOAD_EVENT_EXIT_MATRIX.items())
async def test_download_terminal_event_exit_matrix(event_name, expected_exit, capsys):
    async def messages():
        yield json.dumps({"event": event_name, "gid": "123"})

    exit_code = await _consume_download_events(messages(), gid="123", ndjson=True)

    assert exit_code == expected_exit
    assert json.loads(capsys.readouterr().out)["event"] == event_name


def test_download_terminal_event_sets_match_exit_matrix():
    assert _DOWNLOAD_SUCCESS_EVENTS == {
        event for event, exit_code in DOWNLOAD_EVENT_EXIT_MATRIX.items() if exit_code == 0
    }
    assert _DOWNLOAD_FAILURE_EVENTS == {
        event for event, exit_code in DOWNLOAD_EVENT_EXIT_MATRIX.items() if exit_code == 1
    }


@pytest.mark.asyncio
async def test_download_stream_closed_before_terminal_is_failure(capsys):
    async def messages():
        yield json.dumps(
            {"event": "download_progress", "gid": "123", "phase": "pages", "page": 1, "total": 2}
        )

    exit_code = await _consume_download_events(messages(), gid="123", ndjson=True)
    output = [json.loads(line) for line in capsys.readouterr().out.splitlines()]

    assert exit_code == 1
    assert output[-1] == {
        "ok": False,
        "error": {
            "code": "websocket_error",
            "message": "WebSocket closed before a terminal event",
        },
    }


@pytest.mark.asyncio
async def test_download_stream_closed_before_terminal_uses_json_error_envelope(capsys):
    async def messages():
        if False:
            yield ""

    exit_code = await _consume_download_events(messages(), gid="123", json_output=True)

    assert exit_code == 1
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "error": {
            "code": "websocket_error",
            "message": "WebSocket closed before a terminal event",
        },
    }


def test_compatibility_and_deprecation_policy_is_canonical_and_cross_referenced():
    contract = Path("docs/agent/contract.md").read_text(encoding="utf-8")
    decisions = Path("docs/architecture/decisions.md").read_text(encoding="utf-8")
    api_reference = Path("docs/api_reference.md").read_text(encoding="utf-8")
    skill = Path(".agents/skills/pandora/SKILL.md").read_text(encoding="utf-8")

    for required in (
        "contract_version",
        "Compatible changes",
        "Breaking changes",
        "Deprecation",
        "exit 130",
        "invalid_argument",
    ):
        assert required in contract
    assert "ADR-009" in decisions
    assert "contract_version" in api_reference
    assert "contract_version" in skill
