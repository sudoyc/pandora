from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from PIL import Image
from starlette.requests import Request

from pandora_daemon.app import create_app
from pandora_daemon.config import DownloadConfig, PandoraConfig
from pandora_daemon.diagnostics import get_correlation_id, get_request_id
from pandora_daemon.download import DownloadManager
from pandora_daemon.state import AppState


REQUEST_ID = "1" * 32
CORRELATION_ID = "2" * 32


def _state(**values):
    state = MagicMock(spec=AppState)
    for name, value in values.items():
        setattr(state, name, value)
    return state


def test_request_id_header_and_logs_use_safe_route_template(caplog):
    app = create_app()

    @app.get("/diagnostics/{value}")
    async def fail_with_sensitive_detail(value: str):
        raise RuntimeError(f"sensitive exception {value}")

    with caplog.at_level(logging.INFO, logger="pandora_daemon.app"):
        response = TestClient(app, raise_server_exceptions=False).get(
            "/diagnostics/PATH_SECRET",
            headers={
                "X-Request-ID": REQUEST_ID,
                "Authorization": "Bearer HEADER_SECRET",
            },
        )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert f"request_id={REQUEST_ID}" in caplog.text
    assert "route=/diagnostics/{value}" in caplog.text
    for sensitive in ("PATH_SECRET", "HEADER_SECRET", "sensitive exception"):
        assert sensitive not in caplog.text


def test_invalid_diagnostic_headers_are_replaced_without_leaking(caplog):
    app = create_app()

    @app.get("/diagnostics")
    async def diagnostic_ids(request: Request):
        return {
            "request_id": get_request_id(request),
            "correlation_id": get_correlation_id(request),
        }

    with caplog.at_level(logging.INFO, logger="pandora_daemon.app"):
        response = TestClient(app).get(
            "/diagnostics",
            headers={
                "X-Request-ID": "REQUEST_HEADER_SECRET",
                "X-Correlation-ID": "CORRELATION_HEADER_SECRET",
            },
        )

    payload = response.json()
    assert response.headers["X-Request-ID"] == payload["request_id"]
    assert response.headers["X-Correlation-ID"] == payload["correlation_id"]
    assert len(payload["request_id"]) == 32
    assert len(payload["correlation_id"]) == 32
    assert "HEADER_SECRET" not in response.text + caplog.text


def _download_manager(tmp_path: Path):
    detail = SimpleNamespace(
        title="PRIVATE_TITLE",
        pages=2,
    )
    provider = MagicMock()
    provider.get_gallery_details = AsyncMock(return_value=detail)
    ws = MagicMock()
    ws.broadcast = AsyncMock()
    config = DownloadConfig(path=str(tmp_path / "downloads"))
    manager = DownloadManager(provider, config, ws, AsyncMock(), tmp_path / "downloads.json")
    return manager, ws


def test_download_rest_task_state_ws_and_logs_share_diagnostic_ids(tmp_path, caplog):
    manager, ws = _download_manager(tmp_path)
    app = create_app()
    app.state.pandora = _state(downloads=manager)

    with caplog.at_level(logging.INFO, logger="pandora_daemon.download"):
        response = TestClient(app).post(
            "/api/downloads",
            json={"gid": "123", "token": "TOKEN_SECRET"},
            headers={
                "X-Request-ID": REQUEST_ID,
                "X-Correlation-ID": CORRELATION_ID,
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert response.headers["X-Correlation-ID"] == CORRELATION_ID
    assert response.json()["request_id"] == REQUEST_ID
    assert response.json()["correlation_id"] == CORRELATION_ID
    assert "TOKEN_SECRET" not in response.text

    event = ws.broadcast.await_args.args[0]
    assert event["event"] == "download_queued"
    assert event["request_id"] == REQUEST_ID
    assert event["correlation_id"] == CORRELATION_ID

    persisted = json.loads(manager._state_file.read_text(encoding="utf-8"))
    task_data = persisted["tasks"]["123"]
    assert task_data["request_id"] == REQUEST_ID
    assert task_data["correlation_id"] == CORRELATION_ID

    reloaded, _ = _download_manager(tmp_path)
    reloaded._load_state()
    task = reloaded.status()[0]
    assert task.request_id == REQUEST_ID
    assert task.correlation_id == CORRELATION_ID

    assert f"request_id={REQUEST_ID}" in caplog.text
    assert f"correlation_id={CORRELATION_ID}" in caplog.text
    assert "TOKEN_SECRET" not in caplog.text
    assert "PRIVATE_TITLE" not in caplog.text


def test_failed_download_submission_logs_ids_without_sensitive_detail(tmp_path, caplog):
    manager, _ = _download_manager(tmp_path)
    manager._provider.get_gallery_details = AsyncMock(
        side_effect=RuntimeError("UPSTREAM_RESPONSE_SECRET")
    )
    app = create_app()
    app.state.pandora = _state(downloads=manager)

    with caplog.at_level(logging.INFO, logger="pandora_daemon.app"):
        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/downloads",
            json={"gid": "123", "token": "TOKEN_SECRET"},
            headers={
                "X-Request-ID": REQUEST_ID,
                "X-Correlation-ID": CORRELATION_ID,
            },
        )

    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert response.headers["X-Correlation-ID"] == CORRELATION_ID
    assert f"request_id={REQUEST_ID}" in caplog.text
    assert f"correlation_id={CORRELATION_ID}" in caplog.text
    combined = response.text + caplog.text
    assert "TOKEN_SECRET" not in combined
    assert "UPSTREAM_RESPONSE_SECRET" not in combined


def _write_jpeg(path: Path) -> None:
    Image.new("RGB", (12, 16), color=(255, 0, 0)).save(path, format="JPEG")


def test_pdf_rest_ws_and_logs_share_ids_without_password(tmp_path, caplog):
    gallery_dir = tmp_path / "123-Fixture"
    pages_dir = gallery_dir / "pages"
    pages_dir.mkdir(parents=True)
    (gallery_dir / "metadata.json").write_text(
        json.dumps({"gid": "123", "pages": 1}),
        encoding="utf-8",
    )
    _write_jpeg(pages_dir / "0001.jpg")

    ws = MagicMock()
    ws.broadcast = AsyncMock()
    app = create_app()
    app.state.pandora = _state(
        config=PandoraConfig(download=DownloadConfig(path=str(tmp_path))),
        ws=ws,
    )

    with caplog.at_level(logging.INFO, logger="pandora_daemon.routes.library"):
        response = TestClient(app).post(
            "/api/library/123/export/pdf",
            json={"password": "PASSWORD_SECRET"},
            headers={
                "X-Request-ID": REQUEST_ID,
                "X-Correlation-ID": CORRELATION_ID,
            },
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == REQUEST_ID
    assert response.headers["X-Correlation-ID"] == CORRELATION_ID
    assert response.json()["request_id"] == REQUEST_ID
    assert response.json()["correlation_id"] == CORRELATION_ID

    events = [call.args[0] for call in ws.broadcast.await_args_list]
    assert [event["event"] for event in events] == [
        "pdf_export_started",
        "pdf_export_complete",
    ]
    assert all(event["request_id"] == REQUEST_ID for event in events)
    assert all(event["correlation_id"] == CORRELATION_ID for event in events)

    combined = response.text + json.dumps(events) + caplog.text
    assert "PASSWORD_SECRET" not in combined
    assert f"request_id={REQUEST_ID}" in caplog.text
    assert f"correlation_id={CORRELATION_ID}" in caplog.text
