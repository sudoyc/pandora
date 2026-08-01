"""Agent Pack workflows against an in-process fixture daemon."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from jsonschema import validate
from PIL import Image

from exhentai_api.api import ExhentaiAPI
from exhentai_api.exceptions import GalleryNotFoundError, SessionError
from exhentai_api.models.gallery import GalleryDetail, GalleryListItem
from pandora_daemon import cli
from pandora_daemon.app import create_app
from pandora_daemon.config import CredentialsConfig, DownloadConfig, PandoraConfig
from pandora_daemon.download import DownloadTask
from pandora_daemon.state import AppState


SCHEMA_DIR = Path(__file__).parents[2] / "docs" / "agent" / "schemas"


def _validate(schema_name: str, payload: object) -> None:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    validate(payload, schema)


class _FixtureWebSocket:
    def __init__(self, hub: _FixtureWebSocketHub):
        self._hub = hub
        self._messages: asyncio.Queue[str] = asyncio.Queue()

    async def __aenter__(self):
        self._hub.listeners.append(self._messages)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._hub.listeners.remove(self._messages)
        return False

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self._messages.get()


class _FixtureWebSocketHub:
    def __init__(self):
        self.events: list[dict] = []
        self.listeners: list[asyncio.Queue[str]] = []

    def connect(self, _url: str) -> _FixtureWebSocket:
        return _FixtureWebSocket(self)

    async def broadcast(self, payload: dict) -> None:
        self.events.append(payload)
        message = json.dumps(payload)
        for listener in self.listeners:
            await listener.put(message)


class _FixtureDownloads:
    def __init__(self, hub: _FixtureWebSocketHub, output_dir: Path):
        self._hub = hub
        self._output_dir = output_dir
        self._tasks: dict[str, DownloadTask] = {}
        self.terminal_event = "download_complete"

    async def submit(
        self,
        gid: str,
        token: str,
        *,
        request_id: str,
        correlation_id: str,
    ) -> DownloadTask:
        task = DownloadTask(
            gid=gid,
            token=token,
            title="Fixture Download",
            total_pages=1,
            output_dir=str(self._output_dir / f"{gid}-Fixture"),
            request_id=request_id,
            correlation_id=correlation_id,
        )
        self._tasks[gid] = task
        diagnostic_fields = {
            "gid": gid,
            "request_id": task.request_id,
            "correlation_id": task.correlation_id,
        }
        await self._hub.broadcast({
            "event": "download_queued",
            "title": task.title,
            **diagnostic_fields,
        })
        terminal = {"event": self.terminal_event, **diagnostic_fields}
        if self.terminal_event == "download_error":
            terminal["error"] = "Fixture download failed"
        await self._hub.broadcast(terminal)
        return task

    def status(self) -> list[DownloadTask]:
        return list(self._tasks.values())


def _gallery_item() -> GalleryListItem:
    return GalleryListItem(
        gid="123",
        token="abcdef0123",
        title="Fixture Search Result",
        category="Manga",
        uploader="fixture-user",
        thumb_url="https://example.test/thumb.jpg",
        posted="2026-01-01",
        rating=4.5,
        pages=12,
        rated=False,
        thumb_width=250,
        thumb_height=350,
    )


def _gallery_detail() -> GalleryDetail:
    return GalleryDetail(
        gid="123",
        token="abcdef0123",
        title="Fixture Gallery",
        title_jpn=None,
        category="Manga",
        uploader="fixture-user",
        cover_url="https://example.test/cover.jpg",
        tags={"artist": ["fixture"]},
        pages=1,
        size="1 MB",
        posted="2026-01-01",
        favorite_slot=None,
        preview_pages=1,
        rating=4.0,
        rating_count=2,
        favorite_count=1,
        torrent_count=0,
        comments=[],
        comments_has_more=False,
    )


@pytest.fixture
def workflow_daemon(monkeypatch, tmp_path):
    download_root = tmp_path / "downloads"
    config = PandoraConfig(
        credentials=CredentialsConfig(
            igneous="fixture-igneous",
            ipb_member_id="123",
        ),
        download=DownloadConfig(path=str(download_root)),
    )
    provider = MagicMock(spec=ExhentaiAPI)
    provider.get_homepage = AsyncMock(return_value=[])
    provider.search = AsyncMock(return_value=[])
    provider.get_popular = AsyncMock(return_value=[])
    provider.get_home_detail = AsyncMock(return_value={})
    provider.get_gallery_details = AsyncMock(return_value=_gallery_detail())

    cache = MagicMock()
    cache.get_gallery.return_value = None
    db = MagicMock()
    db.put_history = AsyncMock()
    hub = _FixtureWebSocketHub()
    downloads = _FixtureDownloads(hub, download_root)

    state = MagicMock(spec=AppState)
    state.config = config
    state.config_path = tmp_path / "config.toml"
    state.provider = provider
    state.cache = cache
    state.db = db
    state.downloads = downloads
    state.ws = hub

    app = create_app()
    app.state.pandora = state
    real_client = httpx.AsyncClient

    def fixture_client(*args, **kwargs):
        kwargs["transport"] = httpx.ASGITransport(app=app)
        return real_client(*args, **kwargs)

    monkeypatch.setattr("pandora_daemon.cli.httpx.AsyncClient", fixture_client)
    return SimpleNamespace(
        provider=provider,
        app=app,
        cache=cache,
        db=db,
        downloads=downloads,
        download_root=download_root,
        hub=hub,
    )


async def _run_json(capsys, *argv: str) -> tuple[int, dict | list]:
    args = cli.build_parser().parse_args([
        *argv,
        "--json",
        "--daemon-url",
        "http://fixture-daemon",
    ])
    exit_code = await cli._run_http_command(args)
    return exit_code, json.loads(capsys.readouterr().out)


async def _run_ndjson(capsys, *argv: str) -> tuple[int, list[dict]]:
    args = cli.build_parser().parse_args([
        *argv,
        "--ndjson",
        "--daemon-url",
        "http://fixture-daemon",
    ])
    exit_code = await cli._run_http_command(args)
    output = capsys.readouterr().out.strip()
    return exit_code, [json.loads(line) for line in output.splitlines()]


@pytest.mark.asyncio
async def test_bootstrap_workflow_reaches_ready_fixture_daemon(
    workflow_daemon,
    capsys,
):
    results = {}
    for command in ("health", "config", "readiness", "status"):
        results[command] = await _run_json(capsys, command)

    assert {command: result[0] for command, result in results.items()} == {
        "health": 0,
        "config": 0,
        "readiness": 0,
        "status": 0,
    }
    assert results["health"][1]["contract_version"] == "1"
    assert "credentials" not in results["config"][1]
    assert results["readiness"][1]["ready"] is True
    assert results["status"][1] == {"tasks": []}
    _validate("health-response.schema.json", results["health"][1])
    _validate("readiness-response.schema.json", results["readiness"][1])


@pytest.mark.asyncio
async def test_search_workflow_covers_success_and_sanitized_failure(
    workflow_daemon,
    capsys,
):
    workflow_daemon.provider.search = AsyncMock(return_value=[_gallery_item()])

    exit_code, payload = await _run_json(capsys, "search", "fixture", "--page", "2")

    assert exit_code == 0
    assert payload[0]["gid"] == "123"
    assert payload[0]["title"] == "Fixture Search Result"
    params = workflow_daemon.provider.search.await_args.args[0]
    assert params.keyword == "fixture"
    assert workflow_daemon.provider.search.await_args.kwargs["page"] == 2
    _validate("search-response.schema.json", payload)

    workflow_daemon.provider.search = AsyncMock(
        side_effect=SessionError("SEARCH_RESPONSE_SECRET")
    )
    exit_code, failure = await _run_json(capsys, "search", "fixture")

    assert exit_code == 1
    assert failure["error"]["code"] == "http_error"
    assert "session" in failure["error"]["message"]
    assert "SEARCH_RESPONSE_SECRET" not in json.dumps(failure)
    _validate("cli-error-envelope.schema.json", failure)


@pytest.mark.asyncio
async def test_gallery_workflow_covers_success_and_sanitized_failure(
    workflow_daemon,
    capsys,
):
    exit_code, payload = await _run_json(
        capsys,
        "gallery",
        "123",
        "abcdef0123",
    )

    assert exit_code == 0
    assert payload["gid"] == "123"
    assert payload["title"] == "Fixture Gallery"
    assert "token" not in payload
    assert "api_uid" not in payload
    workflow_daemon.db.put_history.assert_awaited_once()
    _validate("gallery-detail-response.schema.json", payload)

    workflow_daemon.provider.get_gallery_details = AsyncMock(
        side_effect=GalleryNotFoundError("GALLERY_RESPONSE_SECRET")
    )
    exit_code, failure = await _run_json(
        capsys,
        "gallery",
        "999",
        "abcdef0123",
    )

    assert exit_code == 1
    assert failure["error"]["code"] == "http_error"
    assert "gallery_not_found" in failure["error"]["message"]
    assert "GALLERY_RESPONSE_SECRET" not in json.dumps(failure)
    _validate("cli-error-envelope.schema.json", failure)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("terminal_event", "expected_exit"),
    [("download_complete", 0), ("download_error", 1)],
)
async def test_download_workflow_streams_success_and_failure_events(
    workflow_daemon,
    capsys,
    terminal_event,
    expected_exit,
):
    workflow_daemon.downloads.terminal_event = terminal_event
    fake_websockets = SimpleNamespace(connect=workflow_daemon.hub.connect)

    with patch.dict("sys.modules", {"websockets": fake_websockets}):
        exit_code, events = await _run_ndjson(
            capsys,
            "download",
            "run",
            "123",
            "abcdef0123",
        )

    assert exit_code == expected_exit
    assert [event["event"] for event in events] == [
        "download_submitted",
        "download_queued",
        terminal_event,
    ]
    assert len({event["request_id"] for event in events}) == 1
    assert len({event["correlation_id"] for event in events}) == 1
    assert "abcdef0123" not in json.dumps(events)
    for event in events:
        _validate("download-event.schema.json", event)


def _write_jpeg(path: Path) -> None:
    Image.new("RGB", (12, 16), color=(255, 0, 0)).save(path, format="JPEG")


@pytest.mark.asyncio
async def test_library_and_pdf_workflows_cover_success_and_failure(
    workflow_daemon,
    capsys,
):
    complete_dir = workflow_daemon.download_root / "123-Fixture"
    pages_dir = complete_dir / "pages"
    pages_dir.mkdir(parents=True)
    (complete_dir / "metadata.json").write_text(
        json.dumps({"gid": "123", "title": "Fixture Library", "pages": 1}),
        encoding="utf-8",
    )
    _write_jpeg(pages_dir / "0001.jpg")

    incomplete_dir = workflow_daemon.download_root / "124-Fixture"
    incomplete_dir.mkdir()
    (incomplete_dir / "metadata.json").write_text(
        json.dumps({"gid": "124", "title": "Incomplete Fixture", "pages": 1}),
        encoding="utf-8",
    )

    exit_code, library = await _run_json(capsys, "library", "list")
    assert exit_code == 0
    assert [item["gid"] for item in library] == ["123", "124"]
    _validate("library-list-response.schema.json", library)

    password = "PDF_PASSWORD_SECRET"
    exit_code, exported = await _run_json(
        capsys,
        "library",
        "export-pdf",
        "123",
        "--password",
        password,
    )

    assert exit_code == 0
    assert exported["ok"] is True
    assert exported["password_protected"] is True
    assert Path(exported["path"]).is_file()
    success_events = workflow_daemon.hub.events[-2:]
    assert [event["event"] for event in success_events] == [
        "pdf_export_started",
        "pdf_export_complete",
    ]
    assert all(
        event["correlation_id"] == exported["correlation_id"]
        for event in success_events
    )
    for event in success_events:
        _validate("pdf-export-event.schema.json", event)

    exit_code, failure = await _run_json(
        capsys,
        "library",
        "export-pdf",
        "124",
        "--password",
        password,
    )

    assert exit_code == 1
    assert failure["error"]["code"] == "http_error"
    assert workflow_daemon.hub.events[-1]["event"] == "pdf_export_error"
    _validate("cli-error-envelope.schema.json", failure)
    _validate("pdf-export-event.schema.json", workflow_daemon.hub.events[-1])
    combined = json.dumps([exported, failure, workflow_daemon.hub.events])
    assert password not in combined
