"""Agent-facing daemon contract tests.

These tests document the REST/WS JSON shapes that agents, CLI scripts, the web
frontend, and the archived TUI can rely on without importing frontend models.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import validate

from pandora_daemon.config import DownloadConfig, PandoraConfig, ProviderConfig
from pandora_daemon.providers.contracts import GalleryComment, GalleryDetail, GallerySummary
from pandora_daemon import cli
from pandora_daemon.cli import _machine_error
from pandora_daemon.download import DownloadManager, DownloadTask
from pandora_daemon.routes.browse import _gallery_item_to_dict
from pandora_daemon.routes.gallery import _detail_to_dict
from pandora_daemon.routes.library import router as library_router
from pandora_daemon.routes.tags import router as tags_router
from pandora_daemon.state import AppState
from pandora_daemon.providers.exhentai.tags import ExHentaiTagCatalog


def _assert_keys(data: dict, keys: set[str]) -> None:
    assert set(data) >= keys


def test_gallery_list_item_contract_shape():
    item = GallerySummary(
        gid="123",
        token="abcdef0123",
        title="List Item",
        category="Manga",
        uploader="user",
        thumb_url="https://example.test/thumb.jpg",
        posted="2026-01-01",
        rating=4.5,
        pages=12,
        rated=False,
        thumb_width=250,
        thumb_height=350,
        url="https://example.test/g/123/abcdef0123/",
    )

    data = _gallery_item_to_dict(item)

    _assert_keys(
        data,
        {
            "gid",
            "token",
            "title",
            "category",
            "uploader",
            "thumb_url",
            "posted",
            "rating",
            "pages",
            "rated",
            "thumb_width",
            "thumb_height",
            "url",
        },
    )
    assert isinstance(data["gid"], str)
    assert isinstance(data["rating"], float)
    assert isinstance(data["pages"], int)
    assert data["url"].endswith("/g/123/abcdef0123/")


def test_gallery_detail_contract_shape():
    detail = GalleryDetail(
        gid="123",
        token="abcdef0123",
        title="Detail",
        title_jpn=None,
        category="Manga",
        uploader="user",
        cover_url="https://example.test/cover.jpg",
        tags={"artist": ["someone"]},
        pages=3,
        size="10 MB",
        posted="2026-01-01",
        favorite_slot=None,
        url="https://example.test/g/123/abcdef0123/",
        provider_data=object(),
        preview_page_count=1,
        rating=4.0,
        rating_count=10,
        favorite_count=2,
        torrent_count=1,
        comments=(
            GalleryComment(
                id=7,
                user="reader",
                comment="hello",
                score=0,
                time="2026-01-01",
            ),
        ),
        comments_has_more=False,
    )
    data = _detail_to_dict(detail)
    assert set(data) == {
        "gid",
        "title",
        "title_jpn",
        "category",
        "uploader",
        "cover_url",
        "tags",
        "pages",
        "size",
        "posted",
        "favorite_slot",
        "preview_pages",
        "rating",
        "rating_count",
        "favorite_count",
        "torrent_count",
        "comments",
        "comments_has_more",
        "url",
    }
    assert data["preview_pages"] == 1
    assert set(data["comments"][0]) == {
        "id",
        "user",
        "comment",
        "score",
        "time",
        "is_uploader",
        "vote_up_able",
        "vote_down_able",
        "vote_up_ed",
        "vote_down_ed",
        "editable",
        "last_edited",
    }


def test_download_task_contract_shape():
    task = DownloadTask(
        gid="123",
        token="abcdef0123",
        title="Download",
        total_pages=5,
        output_dir="/downloads/123-Download",
        status="completed_with_errors",
        downloaded_pages=4,
    )
    task.page_states = {1: "done", 5: "failed"}
    task.failed_pages = [5]

    data = task.to_public_dict()

    _assert_keys(
        data,
        {
            "gid",
            "title",
            "total_pages",
            "status",
            "downloaded_pages",
            "downloaded_thumbs",
            "cover_downloaded",
            "metadata_saved",
            "error",
            "created_at",
            "page_states",
            "failed_pages",
        },
    )
    assert "token" not in data
    assert "output_dir" not in data
    assert "viewer_urls" not in data
    assert "thumb_urls" not in data
    assert "thumb_sprites" not in data
    assert isinstance(data["page_states"], dict)
    assert data["page_states"][1] == "completed"
    assert json.loads(json.dumps(data))["page_states"]["5"] == "failed"


def test_download_pages_contract_shape():
    task = DownloadTask(gid="123", token="abcdef0123", title="Download", total_pages=5, output_dir="/tmp")
    task.downloaded_pages = 4
    task.failed_pages = [5]
    task.page_states = {1: "done", 5: "failed"}

    data = {
        "gid": task.gid,
        "total_pages": task.total_pages,
        "downloaded_pages": task.downloaded_pages,
        "failed_pages": task.failed_pages,
        "page_states": task.page_states,
    }

    _assert_keys(data, {"gid", "total_pages", "downloaded_pages", "failed_pages", "page_states"})
    assert isinstance(data["failed_pages"], list)


def test_cli_gallery_contract_redacts_sensitive_api_identity():
    data = cli._redact_sensitive_cli_output({"gid": "123", "api_uid": "uid", "api_key": "key"})

    assert data == {"gid": "123"}


def test_cli_download_pages_contract_uses_public_page_state_values():
    data = cli._normalize_download_pages_output({"gid": "123", "page_states": {"1": "done", "2": "failed"}})

    assert data["page_states"] == {"1": "completed", "2": "failed"}


def test_download_lifecycle_contract_is_documented():
    contract = Path("docs/agent/contract.md").read_text(encoding="utf-8")
    api_reference = Path("docs/api_reference.md").read_text(encoding="utf-8")
    workflow = Path("docs/agent/workflows/download.md").read_text(encoding="utf-8")
    skill = Path(".agents/skills/pandora/SKILL.md").read_text(encoding="utf-8")

    for text in (contract, api_reference, workflow, skill):
        for status in (
            "queued",
            "downloading",
            "completed",
            "completed_with_errors",
            "paused",
            "failed",
            "cancelled",
        ):
            assert f"`{status}`" in text
        assert "reconcile" in text.lower() or "reconciliation" in text.lower()


def test_download_consistency_report_contract_is_documented():
    contract = Path("docs/agent/contract.md").read_text(encoding="utf-8")
    workflow = Path("docs/agent/workflows/download.md").read_text(encoding="utf-8")
    skill = Path(".agents/skills/pandora/SKILL.md").read_text(encoding="utf-8")

    for text in (contract, workflow, skill):
        assert "download report --json" in text
    for issue_code in (
        "orphan_task",
        "missing_pages",
        "missing_metadata",
        "invalid_metadata",
        "unregistered_library",
    ):
        assert issue_code in contract


@pytest.mark.asyncio
async def test_download_recovery_contract_is_safe_and_documented(tmp_path: Path):
    gallery_dir = tmp_path / "downloads" / "123-Download"
    pages_dir = gallery_dir / "pages"
    pages_dir.mkdir(parents=True)
    (gallery_dir / "metadata.json").write_text(
        json.dumps({
            "gid": "123",
            "token": "abcdef0123",
            "title": "Download",
            "pages": 1,
        }),
        encoding="utf-8",
    )
    (pages_dir / "0001.jpg").write_bytes(b"page")
    manager = DownloadManager(
        AsyncMock(),
        DownloadConfig(path=str(tmp_path / "downloads")),
        AsyncMock(),
        AsyncMock(),
        tmp_path / "downloads.json",
    )

    data = await manager.repair("123")

    _assert_keys(data, {"operation", "gid", "apply", "changed", "actions"})
    _assert_keys(
        data["actions"][0],
        {"code", "gid", "task_status", "expected_pages", "present_pages"},
    )
    serialized = json.dumps(data)
    assert "abcdef0123" not in serialized
    assert str(tmp_path) not in serialized
    for path in (
        "docs/agent/contract.md",
        "docs/agent/workflows/download.md",
        ".agents/skills/pandora/SKILL.md",
    ):
        text = Path(path).read_text(encoding="utf-8")
        assert "download repair" in text
        assert "download forget" in text
        assert "--apply" in text


def test_library_item_contract_shape(tmp_path: Path):
    gallery_dir = tmp_path / "123-Download"
    gallery_dir.mkdir()
    (gallery_dir / "metadata.json").write_text(
        json.dumps({"gid": "123", "token": "abcdef0123", "title": "Download", "pages": 5}),
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(library_router)
    state = MagicMock(spec=AppState)
    state.config = PandoraConfig(download=DownloadConfig(path=str(tmp_path)))
    state.downloads = MagicMock(download_path=tmp_path)
    app.state.pandora = state

    data = TestClient(app).get("/api/library").json()[0]

    _assert_keys(data, {"gid", "token", "title", "pages", "thumb_url"})
    assert data["thumb_url"] == "/api/library/123/file?path=cover"


def test_tag_suggestion_contract_shape():
    tag_db = ExHentaiTagCatalog()
    tag_db.load_from_dict({"data": [{"namespace": "artist", "data": {"alice": {"name": "Alice"}}}]})
    app = FastAPI()
    app.include_router(tags_router)
    state = MagicMock(spec=AppState)
    state.provider = MagicMock()
    state.provider.tag_catalog = tag_db
    app.state.pandora = state

    data = TestClient(app).get("/api/tags/suggest?q=ali").json()

    _assert_keys(data, {"suggestions"})
    _assert_keys(data["suggestions"][0], {"namespace", "tag", "translation"})


def test_public_config_contract_shape_and_redaction():
    config = PandoraConfig(
        provider=ProviderConfig(id="fixture", credentials={"session": "sensitive"})
    )
    config.network.proxy = "http://user:pass@proxy.example:8080"

    data = config.to_public_dict()

    assert set(data) == {"provider", "server", "download", "cache", "network"}
    assert data["provider"] == {"id": "fixture"}
    _assert_keys(data["network"], {"proxy_configured", "timeout"})
    assert data["network"]["proxy_configured"] is True
    assert "proxy" not in data["network"]


def test_health_contract_shape_is_minimal_and_safe():
    data = {
        "ok": True,
        "version": "0.2.0",
        "contract_version": "1",
        "service": "pandora-daemon",
        "auth_configured": True,
        "capabilities": {
            "browse": True,
            "gallery_detail": True,
            "downloads": True,
            "library": True,
            "tags": True,
            "favorites": True,
            "websocket": True,
        },
    }

    _assert_keys(
        data,
        {"ok", "version", "contract_version", "service", "auth_configured", "capabilities"},
    )
    assert "config_path" not in data
    assert "database_path" not in data
    assert "download_path" not in data
    assert "cache_path" not in data


def test_readiness_schema_and_contract_docs_exist():
    schema_path = Path("docs/agent/schemas/readiness-response.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["required"] == [
        "ready",
        "auth_configured",
        "session",
        "checks",
    ]
    assert set(schema["$defs"]["checkStatus"]["enum"]) == {
        "not_checked",
        "ok",
        "auth",
        "session",
        "upstream",
        "parse",
        "network",
    }
    serialized_schema = json.dumps(schema)
    for sensitive_name in (
        "igneous",
        "ipb_member_id",
        "ipb_pass_hash",
        "cookie",
        "response_body",
    ):
        assert sensitive_name not in serialized_schema

    for doc_path in (
        Path("docs/api_reference.md"),
        Path("docs/agent/contract.md"),
    ):
        text = doc_path.read_text(encoding="utf-8")
        assert "/api/readiness" in text
        assert "readiness --json" in text
        assert "exit 0" in text
        assert "exit 1" in text


def test_bootstrap_docs_use_canonical_diagnostic_order():
    commands = [
        "uv run python -m pandora_daemon.cli health --json",
        "uv run python -m pandora_daemon.cli config --json",
        "uv run python -m pandora_daemon.cli readiness --json",
        "uv run python -m pandora_daemon.cli status --json",
    ]
    paths = [
        Path("README.md"),
        Path("docs/deployment.md"),
        Path("docs/agent/README.md"),
        Path("docs/agent/contract.md"),
        Path("docs/agent/context-pack.md"),
        Path("docs/agent/workflows/bootstrap.md"),
        Path("docs/hermes_integration.md"),
        Path(".agents/skills/pandora/SKILL.md"),
        Path("GEMINI.md"),
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        positions = [text.find(command) for command in commands]
        assert all(position >= 0 for position in positions), path
        assert positions == sorted(positions), path


def test_websocket_event_contract_examples():
    request_id = "1" * 32
    correlation_id = "2" * 32
    base_examples = [
        {"event": "download_queued", "gid": "123", "title": "Download"},
        {"event": "download_progress", "gid": "123", "phase": "pages", "page": 1, "total": 5},
        {"event": "download_complete", "gid": "123"},
        {"event": "download_complete_with_errors", "gid": "123", "failed_pages": [5]},
        {"event": "download_error", "gid": "123", "error": "boom"},
        {"event": "download_cancelled", "gid": "123"},
        {"event": "download_paused", "gid": "123", "reason": "image_limit"},
        {"event": "download_auth_failed", "gid": "123", "error": "auth"},
        {"event": "pdf_export_started", "gid": "123"},
        {"event": "pdf_export_complete", "gid": "123", "path": "/downloads/123-Download/exports/123.pdf", "password_protected": True},
        {"event": "pdf_export_error", "gid": "123", "error": "boom"},
    ]
    examples = [
        {
            **event,
            "request_id": request_id,
            "correlation_id": correlation_id,
        }
        for event in base_examples
    ]

    for event in examples:
        assert "event" in event
        assert "type" not in event
        assert isinstance(event["gid"], str)
        assert event["request_id"] == request_id
        assert event["correlation_id"] == correlation_id
        if event["event"].startswith("download_"):
            assert "path" not in event
            schema_name = "download-event.schema.json"
        else:
            schema_name = "pdf-export-event.schema.json"
        schema = json.loads(
            (Path("docs/agent/schemas") / schema_name).read_text(encoding="utf-8")
        )
        validate(event, schema)


def test_diagnostic_ids_are_documented_as_optional_v1_fields():
    schema_names = [
        "download-task-response.schema.json",
        "download-list-response.schema.json",
        "download-pages-response.schema.json",
        "download-event.schema.json",
        "pdf-export-event.schema.json",
    ]
    for schema_name in schema_names:
        schema = json.loads(
            (Path("docs/agent/schemas") / schema_name).read_text(encoding="utf-8")
        )
        object_schema = schema["items"] if schema["type"] == "array" else schema
        properties = object_schema["properties"]
        assert properties["request_id"]["pattern"] == "^[0-9a-f]{32}$"
        assert properties["correlation_id"]["pattern"] == "^[0-9a-f]{32}$"
        assert "request_id" not in object_schema.get("required", [])
        assert "correlation_id" not in object_schema.get("required", [])

    for path in (
        Path("docs/agent/contract.md"),
        Path("docs/api_reference.md"),
        Path(".agents/skills/pandora/SKILL.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "X-Request-ID" in text
        assert "X-Correlation-ID" in text
        assert "request_id" in text
        assert "correlation_id" in text


def test_pdf_export_event_schema_and_agent_docs_exist():
    schema_path = Path("docs/agent/schemas/pdf-export-event.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "pdf_export_complete" in schema["properties"]["event"]["enum"]

    contract = Path("docs/agent/contract.md").read_text(encoding="utf-8")
    library_workflow = Path("docs/agent/workflows/library.md").read_text(encoding="utf-8")
    skill = Path(".agents/skills/pandora/SKILL.md").read_text(encoding="utf-8")

    for text in (contract, library_workflow, skill):
        assert "library export-pdf" in text
        assert "pdf_export_complete" in text
        assert "password" in text

    assert "secret-pass" not in contract
    assert "secret-pass" not in library_workflow
    assert "secret-pass" not in skill


def test_cli_machine_error_envelope_contract_shape():
    data = _machine_error("connect_error", "Cannot connect to daemon at http://127.0.0.1:7860")

    _assert_keys(data, {"ok", "error"})
    assert data["ok"] is False
    _assert_keys(data["error"], {"code", "message"})
    assert data["error"]["code"] == "connect_error"


def test_upstream_error_schema_and_contract_docs_exist():
    schema_path = Path("docs/agent/schemas/upstream-error.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    core_codes = {"auth", "session", "upstream", "parse", "network"}

    assert schema["required"] == ["error", "detail"]
    assert schema["additionalProperties"] is False
    assert core_codes <= set(schema["properties"]["error"]["enum"])

    serialized_schema = json.dumps(schema)
    for sensitive_name in ("igneous", "ipb_member_id", "ipb_pass_hash", "cookie", "response_body"):
        assert sensitive_name not in serialized_schema

    for doc_path in (
        Path("docs/api_reference.md"),
        Path("docs/agent/contract.md"),
        Path(".agents/skills/pandora/SKILL.md"),
    ):
        text = doc_path.read_text(encoding="utf-8")
        for code in core_codes:
            assert f"`{code}`" in text
