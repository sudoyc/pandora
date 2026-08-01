"""Validate successful REST responses against the agent-facing JSON Schemas."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from pandora_daemon.config import DownloadConfig, PandoraConfig, ProviderConfig
from pandora_daemon.providers.contracts import GalleryComment, GalleryDetail, GallerySummary
from pandora_daemon.download import DownloadTask
from pandora_daemon.routes.browse import router as browse_router
from pandora_daemon.routes.config import router as config_router
from pandora_daemon.routes.downloads import router as downloads_router
from pandora_daemon.routes.gallery import router as gallery_router
from pandora_daemon.routes.library import router as library_router
from pandora_daemon.routes.readiness import router as readiness_router
from pandora_daemon.routes.tags import router as tags_router
from pandora_daemon.state import AppState
from pandora_daemon.tag_database import TagDatabase


SCHEMA_DIR = Path(__file__).parents[2] / "docs" / "agent" / "schemas"


def _validate(schema_name: str, payload: object) -> None:
    schema = json.loads((SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)


def _state(**values):
    state = MagicMock(spec=AppState)
    for name, value in values.items():
        setattr(state, name, value)
    return state


def test_health_route_response_matches_schema():
    app = FastAPI()
    app.include_router(config_router)
    provider = MagicMock()
    provider.auth_configured = False
    app.state.pandora = _state(config=PandoraConfig(), provider=provider)

    response = TestClient(app).get("/api/health")

    assert response.status_code == 200
    _validate("health-response.schema.json", response.json())


def test_readiness_route_response_matches_schema_without_credentials():
    app = FastAPI()
    app.include_router(readiness_router)
    provider = MagicMock()
    provider.auth_configured = False
    app.state.pandora = _state(
        config=PandoraConfig(provider=ProviderConfig()),
        provider=provider,
    )

    response = TestClient(app).get("/api/readiness")

    assert response.status_code == 200
    _validate("readiness-response.schema.json", response.json())


def test_search_route_response_matches_gallery_list_schema():
    item = GallerySummary(
        gid="123",
        token="abcdef0123",
        title="Search result",
        category="Manga",
        uploader="fixture-user",
        thumb_url="https://example.test/thumb.jpg",
        posted="2026-01-01",
        rating=4.5,
        pages=12,
        rated=False,
        thumb_width=250,
        thumb_height=350,
        url="https://example.test/g/123/abcdef0123/",
    )
    provider = MagicMock()
    provider.search = AsyncMock(return_value=[item])
    app = FastAPI()
    app.include_router(browse_router)
    app.state.pandora = _state(provider=provider)

    response = TestClient(app).get("/api/search?keyword=fixture")

    assert response.status_code == 200
    _validate("search-response.schema.json", response.json())


def test_gallery_detail_route_response_matches_schema():
    detail = GalleryDetail(
        gid="123",
        token="abcdef0123",
        title="Gallery detail",
        title_jpn=None,
        category="Manga",
        uploader="fixture-user",
        cover_url="https://example.test/cover.jpg",
        tags={"artist": ["fixture"]},
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
    provider = MagicMock()
    provider.get_gallery_details = AsyncMock(return_value=detail)
    cache = MagicMock()
    cache.get_gallery.return_value = None
    db = MagicMock()
    db.put_history = AsyncMock()
    app = FastAPI()
    app.include_router(gallery_router)
    app.state.pandora = _state(provider=provider, cache=cache, db=db)

    response = TestClient(app).get("/api/gallery/123/abcdef0123")

    assert response.status_code == 200
    _validate("gallery-detail-response.schema.json", response.json())


def _download_app(task: DownloadTask) -> FastAPI:
    downloads = MagicMock()
    downloads.submit = AsyncMock(return_value=task)
    downloads.status.return_value = [task]
    downloads.consistency_report.return_value = {
        "consistent": True,
        "summary": {
            "registered_tasks": 1,
            "terminal_tasks": 0,
            "library_entries": 0,
            "affected_galleries": 0,
            "issue_count": 0,
        },
        "issues": [],
    }
    app = FastAPI()
    app.include_router(downloads_router)
    app.state.pandora = _state(downloads=downloads)
    return app


def test_download_task_list_pages_and_report_routes_match_schemas():
    task = DownloadTask(
        gid="123",
        token="abcdef0123",
        title="Download fixture",
        total_pages=5,
        output_dir="/tmp/fixture-download",
        status="downloading",
        downloaded_pages=2,
    )
    task.page_states = {1: "done", 2: "done", 3: "downloading"}
    task.failed_pages = [4]
    app = _download_app(task)
    client = TestClient(app)

    submit = client.post("/api/downloads", json={"gid": "123", "token": "abcdef0123"})
    listing = client.get("/api/downloads")
    pages = client.get("/api/downloads/123/pages")
    report = client.get("/api/downloads/report")

    assert submit.status_code == listing.status_code == pages.status_code == report.status_code == 200
    _validate("download-task-response.schema.json", submit.json())
    _validate("download-list-response.schema.json", listing.json())
    _validate("download-pages-response.schema.json", pages.json())
    _validate("download-consistency-report.schema.json", report.json())


def test_library_list_route_response_matches_schema(tmp_path):
    gallery_dir = tmp_path / "123-Fixture"
    gallery_dir.mkdir()
    (gallery_dir / "metadata.json").write_text(
        json.dumps({"gid": "123", "token": "fixture", "title": "Fixture", "pages": 2}),
        encoding="utf-8",
    )
    app = FastAPI()
    app.include_router(library_router)
    app.state.pandora = _state(
        config=PandoraConfig(download=DownloadConfig(path=str(tmp_path)))
    )

    response = TestClient(app).get("/api/library")

    assert response.status_code == 200
    _validate("library-list-response.schema.json", response.json())


def test_tag_suggest_and_status_routes_match_schemas(tmp_path):
    tag_db = TagDatabase()
    tag_db.load_from_dict(
        {"data": [{"namespace": "artist", "data": {"alice": {"name": "Alice"}}}]},
        cache_path=tmp_path / "db.text.json",
    )
    app = FastAPI()
    app.include_router(tags_router)
    app.state.pandora = _state(tag_database=tag_db)
    client = TestClient(app)

    suggestions = client.get("/api/tags/suggest?q=ali")
    status = client.get("/api/tags/status")

    assert suggestions.status_code == status.status_code == 200
    _validate("tag-suggest-response.schema.json", suggestions.json())
    _validate("tag-status-response.schema.json", status.json())
