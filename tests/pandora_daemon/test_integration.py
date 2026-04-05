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


def _make_gallery_item(
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
    url="https://exhentai.org/g/12345/abcdef/",
):
    item = MagicMock()
    item.gid = gid
    item.token = token
    item.title = title
    item.category = category
    item.uploader = uploader
    item.thumb_url = thumb_url
    item.posted = posted
    item.rating = rating
    item.pages = pages
    item.rated = rated
    item.thumb_width = thumb_width
    item.thumb_height = thumb_height
    item.url = url
    return item


@pytest.fixture
def mock_state(tmp_path):
    config = PandoraConfig()
    config_path = tmp_path / "config.toml"
    mock_api = AsyncMock()
    mock_client = AsyncMock()
    mock_api.client = mock_client

    cache_config = config.cache
    cache_config.image_dir = str(tmp_path / "images")
    cache = CacheManager(cache_config)
    ws = WebSocketManager()
    state_file = tmp_path / "downloads.json"
    image_service = ImageService(api=mock_api, cache=cache, config=cache_config)
    downloads = DownloadManager(api=mock_api, config=config.download, ws=ws, image_service=image_service, state_file=state_file)

    state = AppState(
        config=config, config_path=config_path,
        client=mock_client, api=mock_api,
        downloads=downloads, cache=cache, image_service=image_service, ws=ws,
        db=MagicMock(),
    )
    return state, mock_api


def _make_test_app(mock_state):
    state, mock_api = mock_state

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
        """Mock api.get_homepage to return a gallery item, verify 200 and title."""
        state, mock_api = mock_state
        gallery = _make_gallery_item(title="Integration Test Gallery")
        mock_api.get_homepage = AsyncMock(return_value=[gallery])

        app = _make_test_app(mock_state)
        client = TestClient(app)

        response = client.get("/api/homepage")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Integration Test Gallery"
        assert data[0]["gid"] == "12345"
        mock_api.get_homepage.assert_called_once()

    def test_sad_panda_returns_401(self, mock_state):
        """Mock api.get_homepage to raise RuntimeError('Sad Panda: ...'), verify 401."""
        state, mock_api = mock_state
        mock_api.get_homepage = AsyncMock(
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
        """Verify search with keyword/page/min_rating passes correct SearchParams."""
        state, mock_api = mock_state
        gallery = _make_gallery_item()
        mock_api.search = AsyncMock(return_value=[gallery])

        app = _make_test_app(mock_state)
        client = TestClient(app)

        response = client.get("/api/search?keyword=test+gallery&page=2&min_rating=4")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        call_args = mock_api.search.call_args
        search_params = call_args[0][0]
        assert search_params.f_search == "test gallery"
        assert call_args[1]["page"] == 2
        assert search_params.advsearch is True
        assert search_params.f_sr is True
        assert search_params.f_srdd == 4


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
