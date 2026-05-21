import pytest
import httpx
from unittest.mock import MagicMock, patch
from pandora_daemon.cli import (
    _watch_download_events,
    _normalize_argv,
    _run_http_command,
    build_daemon_url,
    build_parser,
    parse_gallery_url,
    resolve_gallery_target,
)


def test_parse_gallery_url_standard():
    gid, token = parse_gallery_url("https://exhentai.org/g/1234567/a1b2c3d4e5/")
    assert gid == "1234567"
    assert token == "a1b2c3d4e5"


def test_parse_gallery_url_e_hentai():
    gid, token = parse_gallery_url("https://e-hentai.org/g/9999/abcdef0123/")
    assert gid == "9999"
    assert token == "abcdef0123"


def test_parse_gallery_url_invalid():
    with pytest.raises(ValueError, match="Invalid gallery URL"):
        parse_gallery_url("https://example.com/not/a/gallery")


def test_build_daemon_url_default():
    url = build_daemon_url("127.0.0.1", 7860)
    assert url == "http://127.0.0.1:7860"


def test_build_daemon_url_custom():
    url = build_daemon_url("0.0.0.0", 8080)
    assert url == "http://0.0.0.0:8080"


def test_resolve_gallery_target_from_url():
    gid, token = resolve_gallery_target("https://exhentai.org/g/1234567/a1b2c3d4e5/")
    assert gid == "1234567"
    assert token == "a1b2c3d4e5"


def test_resolve_gallery_target_from_gid_and_token():
    gid, token = resolve_gallery_target("1234567", "a1b2c3d4e5")
    assert gid == "1234567"
    assert token == "a1b2c3d4e5"


def test_resolve_gallery_target_without_token_rejects_raw_gid():
    with pytest.raises(ValueError, match="token"):
        resolve_gallery_target("1234567")


def test_build_parser_exposes_download_and_status_commands():
    parser = build_parser()
    subcommands = next(action.choices for action in parser._actions if hasattr(action, "choices") and action.choices)

    assert "download" in subcommands
    assert "dl" in subcommands
    assert "status" in subcommands
    assert "st" in subcommands
    assert "health" in subcommands
    assert "config" in subcommands


def test_build_parser_exposes_download_management_subcommands():
    parser = build_parser()
    subcommands = next(action.choices for action in parser._actions if hasattr(action, "choices") and action.choices)
    download_parser = subcommands["download"]
    download_subcommands = next(
        action.choices for action in download_parser._actions if hasattr(action, "choices") and action.choices
    )

    assert set(download_subcommands) >= {"add", "list", "watch", "cancel", "resume", "retry", "pages"}


def test_normalize_argv_preserves_legacy_download_url_form():
    argv = _normalize_argv(["download", "https://exhentai.org/g/1234567/a1b2c3d4e5/", "--json"])
    assert argv == ["download", "legacy", "https://exhentai.org/g/1234567/a1b2c3d4e5/", "--json"]


def test_normalize_argv_preserves_legacy_dl_url_form():
    argv = _normalize_argv(["dl", "https://exhentai.org/g/1234567/a1b2c3d4e5/"])
    assert argv == ["dl", "legacy", "https://exhentai.org/g/1234567/a1b2c3d4e5/"]


def test_normalize_argv_leaves_download_subcommands_unchanged():
    argv = _normalize_argv(["download", "list", "--json"])
    assert argv == ["download", "list", "--json"]


class _FakeWebSocket:
    def __init__(self, messages):
        self._messages = iter(messages)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._messages)
        except StopIteration:
            raise StopAsyncIteration


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("event", "expected_code"),
    [
        ('{"event":"download_complete","gid":"123"}', 0),
        ('{"event":"download_complete_with_errors","gid":"123","failed_pages":[2]}', 1),
        ('{"event":"download_error","gid":"123","error":"boom"}', 1),
        ('{"event":"download_cancelled","gid":"123"}', 1),
        ('{"event":"download_paused","gid":"123","reason":"image_limit"}', 1),
        ('{"event":"download_auth_failed","gid":"123","error":"auth"}', 1),
    ],
)
async def test_watch_download_events_exits_on_all_terminal_events(event, expected_code):
    fake_connect = MagicMock(return_value=_FakeWebSocket([event]))
    with patch.dict("sys.modules", {"websockets": type("Ws", (), {"connect": fake_connect})}):
        code = await _watch_download_events("http://127.0.0.1:7860", gid="123", ndjson=True)

    assert code == expected_code


def _mock_http_client(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr("pandora_daemon.cli.httpx.AsyncClient", factory)


@pytest.mark.asyncio
async def test_health_json_calls_daemon_health(monkeypatch, capsys):
    seen_paths = []

    def handler(request):
        seen_paths.append(request.url.path)
        return httpx.Response(200, json={"ok": True, "service": "pandora-daemon"})

    _mock_http_client(monkeypatch, handler)
    args = build_parser().parse_args(["health", "--json", "--daemon-url", "http://daemon"])

    code = await _run_http_command(args)

    assert code == 0
    assert seen_paths == ["/api/health"]
    assert "pandora-daemon" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_config_json_calls_daemon_config_without_credentials(monkeypatch, capsys):
    def handler(request):
        assert request.url.path == "/api/config"
        return httpx.Response(200, json={"server": {"host": "127.0.0.1", "port": 7860}, "network": {"proxy_configured": True, "timeout": 30}})

    _mock_http_client(monkeypatch, handler)
    args = build_parser().parse_args(["config", "--json", "--daemon-url", "http://daemon"])

    code = await _run_http_command(args)

    out = capsys.readouterr().out
    assert code == 0
    assert "server" in out
    assert "credentials" not in out
    assert "proxy_configured" in out
    assert '"proxy"' not in out
