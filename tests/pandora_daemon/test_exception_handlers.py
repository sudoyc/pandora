"""Tests for daemon exception handlers in app.py."""
import pytest
from fastapi.testclient import TestClient

from pandora_daemon.providers.errors import (
    ProviderAuthenticationError,
    ProviderContentBlockedError,
    ProviderError,
    ProviderGalleryNotFoundError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderQuotaError,
    ProviderSessionError,
    ProviderUpstreamError,
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
        app.set_exception(ProviderAuthenticationError("Sad Panda"))
        resp = app.get()
        assert resp.status_code == 401
        data = resp.json()
        assert data["error"] == "auth"
        assert data["detail"] == "Authentication failed"
        assert "Sad Panda" not in data["detail"]

    def test_session_error_returns_stable_401(self, app):
        app.set_exception(ProviderSessionError("expired cookie"))
        resp = app.get()

        assert resp.status_code == 401
        assert resp.json() == {
            "error": "session",
            "detail": "Upstream session is invalid",
        }

    def test_upstream_error_returns_stable_502(self, app):
        app.set_exception(ProviderUpstreamError(status_code=404))
        resp = app.get()

        assert resp.status_code == 502
        assert resp.json() == {
            "error": "upstream",
            "detail": "Upstream service request failed",
        }

    def test_gallery_not_found_returns_404(self, app):
        app.set_exception(ProviderGalleryNotFoundError("Gallery removed"))
        resp = app.get()
        assert resp.status_code == 404
        data = resp.json()
        assert data["error"] == "gallery_not_found"
        assert data["detail"] == "Gallery not found"
        assert "Gallery removed" not in data["detail"]

    def test_image_limit_returns_429(self, app):
        app.set_exception(ProviderQuotaError("Limit exceeded"))
        resp = app.get()
        assert resp.status_code == 429
        data = resp.json()
        assert data["error"] == "image_limit"
        assert data["detail"] == "Image limit reached"
        assert "Limit exceeded" not in data["detail"]

    def test_offensive_returns_451(self, app):
        app.set_exception(ProviderContentBlockedError("Offensive content"))
        resp = app.get()
        assert resp.status_code == 451
        data = resp.json()
        assert data["error"] == "offensive"
        assert data["detail"] == "Gallery unavailable"
        assert "Offensive content" not in data["detail"]

    def test_parse_error_returns_502(self, app):
        app.set_exception(ProviderParseError("Parse failed"))
        resp = app.get()
        assert resp.status_code == 502
        data = resp.json()
        assert data["error"] == "parse"
        assert data["detail"] == "Upstream response parse failed"
        assert "Parse failed" not in data["detail"]

    def test_network_error_returns_502(self, app):
        app.set_exception(ProviderNetworkError("Timeout"))
        resp = app.get()
        assert resp.status_code == 502
        data = resp.json()
        assert data["error"] == "network"
        assert data["detail"] == "Upstream network request failed"
        assert "Timeout" not in data["detail"]

    def test_base_provider_error_returns_500(self, app):
        app.set_exception(ProviderError("Unknown provider error", public_code="exhentai"))
        resp = app.get()
        assert resp.status_code == 500
        data = resp.json()
        assert data["error"] == "exhentai"
        assert data["detail"] == "Upstream request failed"
        assert "Unknown provider error" not in data["detail"]

    def test_generic_runtime_error_returns_stable_internal_500(self, app):
        app.set_exception(RuntimeError("Something broke"))
        resp = app.get()
        assert resp.status_code == 500
        data = resp.json()
        assert data == {
            "error": "internal",
            "detail": "Internal server error",
        }
        assert "Something broke" not in data["detail"]

    def test_generic_exception_returns_stable_internal_500(self, app):
        app.set_exception(Exception("Connection details leaked"))
        resp = app.get()
        assert resp.status_code == 500
        data = resp.json()
        assert data == {
            "error": "internal",
            "detail": "Internal server error",
        }
        assert "Connection details leaked" not in data["detail"]

    @pytest.mark.parametrize(
        "exc",
        [
            ProviderAuthenticationError("igneous=COOKIE_SECRET"),
            ProviderSessionError("ipb_member_id=COOKIE_SECRET"),
            ProviderUpstreamError("<html>FULL_UPSTREAM_PAGE</html>"),
            ProviderParseError("<html>FULL_UPSTREAM_PAGE</html>"),
            ProviderNetworkError("https://user:PROXY_SECRET@proxy.example"),
            ProviderError("igneous=COOKIE_SECRET", public_code="exhentai"),
            RuntimeError("<html>FULL_UPSTREAM_PAGE</html>"),
            Exception("ipb_pass_hash=COOKIE_SECRET"),
        ],
    )
    def test_exception_output_and_logs_do_not_leak_details(self, app, caplog, exc):
        app.set_exception(exc)
        with caplog.at_level("WARNING", logger="pandora_daemon.app"):
            resp = app.get()

        combined = resp.text + caplog.text
        assert "COOKIE_SECRET" not in combined
        assert "FULL_UPSTREAM_PAGE" not in combined
        assert "PROXY_SECRET" not in combined
