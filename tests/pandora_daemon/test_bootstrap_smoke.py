from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from pandora_daemon import cli
from pandora_daemon.app import create_app
from pandora_daemon.config import PandoraConfig
from pandora_daemon.state import AppState


@pytest.mark.asyncio
async def test_fixture_daemon_bootstrap_cli_smoke(monkeypatch, capsys, tmp_path):
    state = MagicMock(spec=AppState)
    state.config = PandoraConfig()
    state.config_path = tmp_path / "config.toml"
    provider = MagicMock()
    provider.auth_configured = False
    provider.get_homepage = AsyncMock()
    provider.search = AsyncMock()
    provider.get_popular = AsyncMock()
    provider.get_home_detail = AsyncMock()
    state.provider = provider
    state.downloads = MagicMock()
    state.downloads.status.return_value = []

    app = create_app()
    app.state.pandora = state
    real_client = httpx.AsyncClient

    def fixture_client(*args, **kwargs):
        kwargs["transport"] = httpx.ASGITransport(app=app)
        return real_client(*args, **kwargs)

    monkeypatch.setattr("pandora_daemon.cli.httpx.AsyncClient", fixture_client)

    results = []
    for command in ("health", "config", "readiness", "status"):
        args = cli.build_parser().parse_args([
            command,
            "--json",
            "--daemon-url",
            "http://fixture-daemon",
        ])
        exit_code = await cli._run_http_command(args)
        results.append((command, exit_code, json.loads(capsys.readouterr().out)))

    assert [result[:2] for result in results] == [
        ("health", 0),
        ("config", 0),
        ("readiness", 1),
        ("status", 0),
    ]
    assert results[0][2]["service"] == "pandora-daemon"
    assert "credentials" not in results[1][2]
    assert results[2][2] == {
        "ready": False,
        "auth_configured": False,
        "session": "not_configured",
        "checks": {
            "homepage": "not_checked",
            "search": "not_checked",
            "popular": "not_checked",
            "home": "not_checked",
        },
    }
    assert results[3][2] == {"tasks": []}
    provider.get_homepage.assert_not_awaited()
    provider.search.assert_not_awaited()
    provider.get_popular.assert_not_awaited()
    provider.get_home_detail.assert_not_awaited()
