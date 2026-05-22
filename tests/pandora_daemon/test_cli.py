import pytest
import httpx
from unittest.mock import MagicMock, patch
from pandora_daemon.cli import (
    _machine_error,
    _finalize_common_option_defaults,
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


def test_normalize_argv_leaves_parent_options_before_download_subcommand_unchanged():
    argv = _normalize_argv(["download", "--json", "watch", "123"])
    assert argv == ["download", "--json", "watch", "123"]


def test_parent_json_option_before_download_subcommand_is_preserved():
    args = build_parser().parse_args(["download", "--json", "watch", "123"])

    assert args.download_command == "watch"
    assert args.gid == "123"
    assert args.json is True


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


def _json_out(capsys):
    return capsys.readouterr().out.strip()


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("argv", "method", "path", "expected_json"),
    [
        (["download", "add", "https://exhentai.org/g/1234567/a1b2c3d4e5/", "--json", "--daemon-url", "http://daemon"], "POST", "/api/downloads", {"gid": "1234567", "token": "a1b2c3d4e5"}),
        (["download", "list", "--json", "--daemon-url", "http://daemon"], "GET", "/api/downloads", None),
        (["download", "pages", "123", "--json", "--daemon-url", "http://daemon"], "GET", "/api/downloads/123/pages", None),
        (["download", "cancel", "123", "--json", "--daemon-url", "http://daemon"], "DELETE", "/api/downloads/123", None),
        (["download", "resume", "123", "--json", "--daemon-url", "http://daemon"], "POST", "/api/downloads/123/resume", None),
        (["download", "retry", "123", "--json", "--daemon-url", "http://daemon"], "POST", "/api/downloads/123/retry", None),
        (["search", "tag", "--page", "2", "--json", "--daemon-url", "http://daemon"], "GET", "/api/search", None),
        (["gallery", "https://exhentai.org/g/1234567/a1b2c3d4e5/", "--json", "--daemon-url", "http://daemon"], "GET", "/api/gallery/1234567/a1b2c3d4e5", None),
        (["library", "list", "--json", "--daemon-url", "http://daemon"], "GET", "/api/library", None),
        (["tags", "suggest", "artist", "--json", "--daemon-url", "http://daemon"], "GET", "/api/tags/suggest", None),
        (["favorites", "list", "--json", "--daemon-url", "http://daemon"], "GET", "/api/favorites", None),
        (["popular", "--json", "--daemon-url", "http://daemon"], "GET", "/api/popular", None),
        (["toplist", "--tl", "13", "--json", "--daemon-url", "http://daemon"], "GET", "/api/toplist", None),
        (["watched", "--page", "4", "--json", "--daemon-url", "http://daemon"], "GET", "/api/watched", None),
    ],
)
async def test_cli_machine_mode_commands_call_expected_daemon_routes(monkeypatch, capsys, argv, method, path, expected_json):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, dict(request.url.params), request.content.decode() if request.content else ""))
        if expected_json is not None:
            assert request.headers["content-type"].startswith("application/json")
            assert request.read() == httpx.Request(method, "http://daemon", json=expected_json).read()
        if request.url.path == "/api/downloads":
            return httpx.Response(200, json={"gid": "123", "title": "Queued"})
        if request.url.path == "/api/search":
            assert request.url.params["keyword"] == "tag"
            assert request.url.params["page"] == "2"
            return httpx.Response(200, json={"galleries": []})
        if request.url.path == "/api/tags/suggest":
            assert request.url.params["q"] == "artist"
            return httpx.Response(200, json={"suggestions": []})
        if request.url.path == "/api/favorites":
            assert request.url.params["slot"] == "-1"
            assert request.url.params["page"] == "0"
            return httpx.Response(200, json={"galleries": []})
        if request.url.path == "/api/toplist":
            assert request.url.params["tl"] == "13"
            return httpx.Response(200, json={"galleries": []})
        if request.url.path == "/api/watched":
            assert request.url.params["page"] == "4"
            return httpx.Response(200, json={"galleries": []})
        return httpx.Response(200, json={"ok": True, "path": request.url.path})

    _mock_http_client(monkeypatch, handler)
    args = build_parser().parse_args(argv)
    _finalize_common_option_defaults(args)

    code = await _run_http_command(args)

    assert code == 0
    assert seen[0][0] == method
    assert seen[0][1] == path
    assert _json_out(capsys)


@pytest.mark.asyncio
async def test_download_list_json_wraps_tasks(monkeypatch, capsys):
    def handler(request):
        assert request.url.path == "/api/downloads"
        return httpx.Response(200, json=[{"gid": "123", "status": "queued"}])

    _mock_http_client(monkeypatch, handler)
    args = build_parser().parse_args(["download", "list", "--json", "--daemon-url", "http://daemon"])

    code = await _run_http_command(args)

    assert code == 0
    assert '"tasks"' in _json_out(capsys)


@pytest.mark.asyncio
async def test_status_json_wraps_tasks(monkeypatch, capsys):
    def handler(request):
        assert request.url.path == "/api/downloads"
        return httpx.Response(200, json=[{"gid": "123", "status": "queued"}])

    _mock_http_client(monkeypatch, handler)
    args = build_parser().parse_args(["status", "--json", "--daemon-url", "http://daemon"])

    code = await _run_http_command(args)

    assert code == 0
    assert '"tasks"' in _json_out(capsys)


@pytest.mark.asyncio
async def test_download_watch_ndjson_machine_errors_use_envelope(capsys):
    fake_connect = MagicMock(side_effect=RuntimeError("socket boom"))
    with patch.dict("sys.modules", {"websockets": type("Ws", (), {"connect": fake_connect})}):
        code = await _watch_download_events("http://127.0.0.1:7860", gid="123", ndjson=True)

    assert code == 1
    assert _json_out(capsys) == '{"ok": false, "error": {"code": "websocket_error", "message": "socket boom"}}'


@pytest.mark.asyncio
async def test_download_watch_json_machine_errors_use_error_envelope(capsys):
    fake_connect = MagicMock(side_effect=RuntimeError("socket boom"))
    with patch.dict("sys.modules", {"websockets": type("Ws", (), {"connect": fake_connect})}):
        code = await _watch_download_events("http://127.0.0.1:7860", gid="123", json_output=True)

    out = _json_out(capsys)
    assert code == 1
    assert '"ok": false' in out
    assert '"code": "websocket_error"' in out


def test_machine_error_envelope_shape():
    assert _machine_error("connect_error", "Cannot connect") == {
        "ok": False,
        "error": {"code": "connect_error", "message": "Cannot connect"},
    }


@pytest.mark.asyncio
async def test_gallery_invalid_target_json_uses_error_envelope(capsys):
    args = build_parser().parse_args(["gallery", "1234567", "--json", "--daemon-url", "http://daemon"])

    code = await _run_http_command(args)
    out = _json_out(capsys)

    assert code == 1
    assert '"ok": false' in out
    assert '"code": "invalid_gallery_target"' in out


@pytest.mark.asyncio
async def test_connect_error_json_uses_error_envelope(monkeypatch, capsys):
    transport = httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError("boom", request=request)))
    real_client = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr("pandora_daemon.cli.httpx.AsyncClient", factory)
    args = build_parser().parse_args(["health", "--json", "--daemon-url", "http://daemon"])

    code = await _run_http_command(args)
    out = _json_out(capsys)

    assert code == 1
    assert '"code": "connect_error"' in out
    assert 'Cannot connect to daemon at http://daemon' in out


@pytest.mark.asyncio
async def test_http_status_error_json_uses_error_envelope(monkeypatch, capsys):
    def handler(request):
        return httpx.Response(503, text="daemon unavailable")

    _mock_http_client(monkeypatch, handler)
    args = build_parser().parse_args(["popular", "--json", "--daemon-url", "http://daemon"])

    code = await _run_http_command(args)
    out = _json_out(capsys)

    assert code == 1
    assert '"code": "http_error"' in out
    assert '503 daemon unavailable' in out


@pytest.mark.asyncio
async def test_http_status_error_json_uses_error_envelope_for_download_pages(monkeypatch, capsys):
    def handler(request):
        return httpx.Response(404, text="missing")

    _mock_http_client(monkeypatch, handler)
    args = build_parser().parse_args(["download", "pages", "123", "--json", "--daemon-url", "http://daemon"])

    code = await _run_http_command(args)
    out = _json_out(capsys)

    assert code == 1
    assert out.startswith("{")
    assert '"code": "http_error"' in out


def test_parser_usage_error_json_uses_error_envelope(capsys):
    parser = build_parser()

    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["download", "add", "--json"])

    out = _json_out(capsys)
    assert exc.value.code == 2
    assert '"ok": false' in out
    assert '"code": "usage_error"' in out
