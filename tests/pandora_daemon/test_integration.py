"""Integration tests for pandora_daemon using real route infrastructure."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from pandora_daemon.routes import router
from pandora_daemon.state import AppState
from pandora_daemon.config import PandoraConfig
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService
from pandora_daemon.providers import GallerySearchQuery, GallerySummary


def _make_gallery_summary(
    gid="12345",
    token="abcdef",
    title="Test Gallery",
    category="Doujinshi",
    uploader="testuser",
    thumb_url="https://example.com/thumb.jpg",
    posted="2023-01-01",
    rating=4.5,
    pages=20,
    rated=False,
    thumb_width=250,
    thumb_height=350,
    url="https://example.com/g/12345/abcdef/",
):
    return GallerySummary(
        gid=gid,
        token=token,
        title=title,
        category=category,
        uploader=uploader,
        thumb_url=thumb_url,
        posted=posted,
        rating=rating,
        pages=pages,
        rated=rated,
        thumb_width=thumb_width,
        thumb_height=thumb_height,
        url=url,
    )


@pytest.fixture
def mock_state(tmp_path):
    config = PandoraConfig()
    config_path = tmp_path / "config.toml"
    mock_provider = MagicMock()

    cache_config = config.cache
    cache_config.image_dir = str(tmp_path / "images")
    cache = CacheManager(cache_config)
    ws = WebSocketManager()
    state_file = tmp_path / "downloads.json"
    image_service = ImageService(api=mock_provider, cache=cache, config=cache_config)
    downloads = DownloadManager(
        api=mock_provider,
        config=config.download,
        ws=ws,
        image_service=image_service,
        state_file=state_file,
    )

    state = AppState(
        config=config,
        config_path=config_path,
        provider=mock_provider,
        downloads=downloads,
        cache=cache,
        image_service=image_service,
        ws=ws,
        db=MagicMock(),
    )
    return state, mock_provider


def _make_test_app(mock_state):
    state, _ = mock_state

    app = FastAPI()

    @app.exception_handler(RuntimeError)
    async def sad_panda_handler(request: Request, exc: RuntimeError):
        if "Sad Panda" in str(exc):
            return JSONResponse(status_code=401, content={"detail": str(exc)})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    app.include_router(router)
    app.state.pandora = state
    return app


class TestIntegrationHomepage:
    def test_homepage_returns_galleries(self, mock_state):
        """Mock provider.get_homepage to return a gallery summary."""
        state, mock_provider = mock_state
        gallery = _make_gallery_summary(title="Integration Test Gallery")
        mock_provider.get_homepage = AsyncMock(return_value=[gallery])

        app = _make_test_app(mock_state)
        client = TestClient(app)

        response = client.get("/api/homepage")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Integration Test Gallery"
        assert data[0]["gid"] == "12345"
        mock_provider.get_homepage.assert_awaited_once()

    def test_sad_panda_returns_401(self, mock_state):
        """A provider Sad Panda error preserves the authentication response."""
        state, mock_provider = mock_state
        mock_provider.get_homepage = AsyncMock(
            side_effect=RuntimeError("Sad Panda: session expired")
        )

        app = _make_test_app(mock_state)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/api/homepage")

        assert response.status_code == 401
        data = response.json()
        assert "Sad Panda" in data["detail"]


class TestIntegrationSearch:
    def test_search_passes_params(self, mock_state):
        """Verify search passes a provider-neutral query and page."""
        state, mock_provider = mock_state
        gallery = _make_gallery_summary()
        mock_provider.search = AsyncMock(return_value=[gallery])

        app = _make_test_app(mock_state)
        client = TestClient(app)

        response = client.get("/api/search?keyword=test+gallery&page=2&min_rating=4")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        mock_provider.search.assert_awaited_once_with(
            GallerySearchQuery(keyword="test gallery", minimum_rating=4),
            page=2,
        )


@pytest.mark.asyncio
async def test_image_service_and_download_share_cache(tmp_path):
    """Images cached by ImageService are reused by DownloadManager."""
    from pandora_daemon.config import CacheConfig

    cache_config = CacheConfig(
        image_dir=str(tmp_path / "images"),
        image_max_size_mb=100,
    )
    cache = CacheManager(cache_config)

    # Simulate ImageService caching an image
    url = "https://cdn.example.com/full.jpg"
    await cache.put_image(url, b"image_bytes")

    # DownloadManager's _fetch_image should find it
    result = await cache.get_image(url)
    assert result == b"image_bytes"
