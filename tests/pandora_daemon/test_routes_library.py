"""Tests for pandora_daemon.routes.library module."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfReader

from pandora_daemon.config import DownloadConfig, PandoraConfig
from pandora_daemon.routes.library import router
from pandora_daemon.state import AppState


def _make_app(download_path: str):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.config = PandoraConfig(download=DownloadConfig(path=download_path))
    state.ws = MagicMock()
    state.ws.broadcast = AsyncMock()
    app.state.pandora = state
    return app


def _write_page(path: Path, color: tuple[int, int, int] = (255, 0, 0)) -> None:
    image = Image.new("RGB", (20, 30), color=color)
    image.save(path, format="JPEG")


class TestLibraryRoutes:
    def test_library_list_returns_downloaded_galleries(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test Gallery"
        gallery_dir.mkdir()
        metadata = {
            "gid": "12345",
            "token": "abc",
            "title": "Test Gallery",
            "category": "Manga",
            "pages": 10,
        }
        (gallery_dir / "metadata.json").write_text(json.dumps(metadata))

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["gid"] == "12345"
        assert data[0]["title"] == "Test Gallery"

    def test_library_list_empty_when_no_downloads(self, tmp_path):
        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_library_file_serves_cover(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345"}')
        (gallery_dir / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library/12345/file?path=cover")
        assert resp.status_code == 200
        assert b"fake-jpeg" in resp.content

    def test_library_file_serves_page(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345"}')
        pages_dir = gallery_dir / "pages"
        pages_dir.mkdir()
        (pages_dir / "0003.jpg").write_bytes(b"\xff\xd8\xff\xe0page-data")

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library/12345/file?path=page/3")
        assert resp.status_code == 200
        assert b"page-data" in resp.content

    def test_library_file_serves_thumb(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345"}')
        thumbs_dir = gallery_dir / "thumbs"
        thumbs_dir.mkdir()
        (thumbs_dir / "0005.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPthumb")

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library/12345/file?path=thumb/5")
        assert resp.status_code == 200
        assert b"thumb" in resp.content

    def test_library_file_404_for_missing_gallery(self, tmp_path):
        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.get("/api/library/99999/file?path=cover")
        assert resp.status_code == 404

    def test_library_export_pdf_creates_password_protected_pdf_without_echoing_password(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345", "pages": 2}')
        pages_dir = gallery_dir / "pages"
        pages_dir.mkdir()
        _write_page(pages_dir / "0001.jpg", (255, 0, 0))
        _write_page(pages_dir / "0002.jpg", (0, 255, 0))

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.post(
            "/api/library/12345/export/pdf",
            json={"password": "secret-pass", "output_name": "comic.pdf"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["gid"] == "12345"
        assert data["format"] == "pdf"
        assert data["password_protected"] is True
        assert "secret-pass" not in resp.text
        assert Path(data["path"]).exists()
        assert Path(data["path"]).name == "comic.pdf"

    def test_library_export_pdf_includes_cover_when_requested(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345", "pages": 2}')
        _write_page(gallery_dir / "cover.jpg", (0, 0, 255))
        pages_dir = gallery_dir / "pages"
        pages_dir.mkdir()
        _write_page(pages_dir / "0001.jpg", (255, 0, 0))
        _write_page(pages_dir / "0002.jpg", (0, 255, 0))

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.post("/api/library/12345/export/pdf", json={"include_cover": True, "output_name": "with-cover.pdf"})

        assert resp.status_code == 200
        reader = PdfReader(resp.json()["path"])
        assert len(reader.pages) == 3
        assert reader.is_encrypted is False

    def test_library_export_pdf_rejects_missing_gallery(self, tmp_path):
        app = _make_app(str(tmp_path))
        client = TestClient(app)

        resp = client.post("/api/library/99999/export/pdf", json={})

        assert resp.status_code == 404

    def test_library_export_pdf_rejects_gallery_without_pages(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345"}')

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.post("/api/library/12345/export/pdf", json={})

        assert resp.status_code == 400

    def test_library_export_pdf_rejects_path_traversal_output_name(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345", "pages": 1}')
        pages_dir = gallery_dir / "pages"
        pages_dir.mkdir()
        _write_page(pages_dir / "0001.jpg")

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.post(
            "/api/library/12345/export/pdf",
            json={"output_name": "../escape.pdf"},
        )

        assert resp.status_code == 400

    def test_library_export_pdf_broadcasts_hook_events(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345", "pages": 1}')
        pages_dir = gallery_dir / "pages"
        pages_dir.mkdir()
        _write_page(pages_dir / "0001.jpg")

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.post("/api/library/12345/export/pdf", json={"password": "secret-pass"})

        assert resp.status_code == 200
        broadcasted = [call.args[0] for call in app.state.pandora.ws.broadcast.await_args_list]
        assert broadcasted[0] == {"event": "pdf_export_started", "gid": "12345"}
        assert broadcasted[1]["event"] == "pdf_export_complete"
        assert broadcasted[1]["gid"] == "12345"
        assert broadcasted[1]["password_protected"] is True
        assert "secret-pass" not in json.dumps(broadcasted, ensure_ascii=False)

    def test_library_export_pdf_started_emits_after_plan_validation(self, tmp_path):
        gallery_dir = tmp_path / "12345-Test"
        gallery_dir.mkdir()
        (gallery_dir / "metadata.json").write_text('{"gid": "12345"}')

        app = _make_app(str(tmp_path))
        client = TestClient(app)
        resp = client.post("/api/library/12345/export/pdf", json={"output_name": "comic.pdf"})

        assert resp.status_code == 400
        broadcasted = [call.args[0] for call in app.state.pandora.ws.broadcast.await_args_list]
        assert broadcasted == [{"event": "pdf_export_error", "gid": "12345", "error": "PDF export failed"}]
        assert all("started" not in item.get("event", "") for item in broadcasted)
