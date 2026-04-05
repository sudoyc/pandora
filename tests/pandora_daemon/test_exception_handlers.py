"""Tests for daemon exception handlers in app.py."""
import pytest
from fastapi.testclient import TestClient

from exhentai_api.exceptions import (
    ExhentaiError,
    AuthenticationError,
    ImageLimitError,
    GalleryNotFoundError,
    GalleryOffensiveError,
    ParseError,
    NetworkError,
)


@pytest.fixture
def app():
    """Create a test app with a route that raises configurable exceptions."""
    from pandora_daemon.app import create_app

    real_app = create_app()
    # We need a route that can raise arbitrary exceptions for testing
    _exc_to_raise = None

    @real_app.get("/test-exc")
    async def raise_exc():
        if _exc_to_raise is not None:
            raise _exc_to_raise
        return {"ok": True}

    real_app.state._exc_to_raise = None

    class _Client:
        def __init__(self):
            self.test_client = TestClient(real_app, raise_server_exceptions=False)
            self._app = real_app

        def set_exception(self, exc):
            nonlocal _exc_to_raise
            _exc_to_raise = exc

        def get(self, path="/test-exc"):
            return self.test_client.get(path)

    return _Client()


class TestExceptionHandlers:
    def test_authentication_error_returns_401(self, app):
        app.set_exception(AuthenticationError("Sad Panda"))
        resp = app.get()
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"] == "auth"
        assert "Sad Panda" in data["detail"]

    def test_gallery_not_found_returns_404(self, app):
        app.set_exception(GalleryNotFoundError("Gallery removed"))
        resp = app.get()
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"] == "gallery_not_found"

    def test_image_limit_returns_429(self, app):
        app.set_exception(ImageLimitError("Limit exceeded"))
        resp = app.get()
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"] == "image_limit"

    def test_offensive_returns_451(self, app):
        app.set_exception(GalleryOffensiveError("Offensive content"))
        resp = app.get()
        assert resp.status_code == 451
        data = resp.json()
        assert data["error"] == "offensive"

    def test_parse_error_returns_502(self, app):
        app.set_exception(ParseError("Parse failed"))
        resp = app.get()
        assert resp.status_code == 502
        data = resp.json()
        assert data["error"] == "parse"

    def test_network_error_returns_502(self, app):
        app.set_exception(NetworkError("Timeout"))
        resp = app.get()
        assert resp.status_code == 502
        data = resp.json()
        assert data["error"] == "network"

    def test_base_exhentai_error_returns_500(self, app):
        app.set_exception(ExhentaiError("Unknown exhentai error"))
        resp = app.get()
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "exhentai"

    def test_generic_runtime_error_returns_500_no_error_field(self, app):
        app.set_exception(RuntimeError("Something broke"))
        resp = app.get()
        assert resp.status_code == 500
        data = resp.json()
        assert "error" not in data
        assert "Something broke" in data["detail"]
