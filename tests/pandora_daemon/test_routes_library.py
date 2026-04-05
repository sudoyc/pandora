"""Tests for pandora_daemon.routes.library module."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.config import DownloadConfig, PandoraConfig
from pandora_daemon.routes.library import router
from pandora_daemon.state import AppState


def _make_app(download_path: str):
    app = FastAPI()
    app.include_router(router)
    state = MagicMock(spec=AppState)
    state.config = PandoraConfig(download=DownloadConfig(path=download_path))
    app.state.pandora = state
    return app


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
