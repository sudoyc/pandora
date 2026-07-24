"""Agent-facing daemon contract tests.

These tests document the REST/WS JSON shapes that agents, CLI scripts, the web
frontend, and the archived TUI can rely on without importing frontend models.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from exhentai_api.models.comment import GalleryComment
from exhentai_api.models.gallery import GalleryDetail, GalleryListItem
from pandora_daemon.config import DownloadConfig, PandoraConfig
from pandora_daemon import cli
from pandora_daemon.cli import _machine_error
from pandora_daemon.download import DownloadTask
from pandora_daemon.routes.browse import _gallery_item_to_dict
from pandora_daemon.routes.gallery import _detail_to_dict
from pandora_daemon.routes.library import router as library_router
from pandora_daemon.routes.tags import router as tags_router
from pandora_daemon.state import AppState
from pandora_daemon.tag_database import TagDatabase


def _assert_keys(data: dict, keys: set[str]) -> None:
    assert set(data) >= keys


def test_gallery_list_item_contract_shape():
    item = GalleryListItem(
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
        preview_pages=1,
        thumb_urls=["https://example.test/t1.jpg"],
        rating=4.0,
        rating_count=10,
        favorite_count=2,
        torrent_count=1,
        comments=[GalleryComment(id=7, user="reader", comment="hello")],
        comments_has_more=False,
        api_uid="uid",
        api_key="key",
    )

    data = _detail_to_dict(detail)

    _assert_keys(
        data,
        {
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
        },
    )
    assert "token" not in data
    assert "thumb_urls" not in data
    assert "api_uid" not in data
    assert "api_key" not in data
    assert isinstance(data["tags"], dict)
    assert isinstance(data["comments"], list)
    assert data["comments"][0]["id"] == 7


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
    app.state.pandora = state

    data = TestClient(app).get("/api/library").json()[0]

    _assert_keys(data, {"gid", "token", "title", "pages", "thumb_url"})
    assert data["thumb_url"] == "/api/library/123/file?path=cover"


def test_tag_suggestion_contract_shape():
    tag_db = TagDatabase()
    tag_db.load_from_dict({"data": [{"namespace": "artist", "data": {"alice": {"name": "Alice"}}}]})
    app = FastAPI()
    app.include_router(tags_router)
    state = MagicMock(spec=AppState)
    state.tag_database = tag_db
    app.state.pandora = state

    data = TestClient(app).get("/api/tags/suggest?q=ali").json()

    _assert_keys(data, {"suggestions"})
    _assert_keys(data["suggestions"][0], {"namespace", "tag", "translation"})


def test_public_config_contract_shape_and_redaction():
    config = PandoraConfig()
    config.network.proxy = "http://user:pass@proxy.example:8080"

    data = config.to_public_dict()

    _assert_keys(data, {"server", "download", "cache", "network"})
    _assert_keys(data["network"], {"proxy_configured", "timeout"})
    assert data["network"]["proxy_configured"] is True
    assert "proxy" not in data["network"]
    assert "credentials" not in data


def test_health_contract_shape_is_minimal_and_safe():
    data = {
        "ok": True,
        "version": "0.2.0",
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

    _assert_keys(data, {"ok", "version", "service", "auth_configured", "capabilities"})
    assert "config_path" not in data
    assert "database_path" not in data
    assert "download_path" not in data
    assert "cache_path" not in data


def test_websocket_event_contract_examples():
    examples = [
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

    for event in examples:
        assert "event" in event
        assert "type" not in event
        assert isinstance(event["gid"], str)
        if event["event"].startswith("download_"):
            assert "path" not in event


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
