import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from exhentai_api.exceptions import (
    ExhentaiError,
    AuthenticationError,
    ImageLimitError,
    GalleryNotFoundError,
    GalleryOffensiveError,
    ParseError,
    NetworkError,
)
from pandora_daemon.config import load_config
from pandora_daemon.state import AppState
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService
from pandora_daemon.tag_database import TagDatabase
from pandora_daemon.db import PandoraDB

logger = logging.getLogger(__name__)

async def _cache_eviction_loop(cache: CacheManager, interval: int) -> None:
    """Background loop: periodically prune expired galleries and evict images."""
    while True:
        await asyncio.sleep(interval)
        try:
            cache.prune_expired_galleries()
            await cache.evict_images()
        except Exception:
            logger.exception("Cache eviction error")


async def _build_state() -> AppState:
    """Construct all components and return AppState."""
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)
    db_path = config_path.parent / "pandora.db"
    db = PandoraDB(db_path)
    await db.initialize()
    client = ExhentaiClient(
        igneous=config.credentials.igneous,
        ipb_member_id=config.credentials.ipb_member_id,
        proxy=config.network.proxy,
        timeout=config.network.timeout,
    )
    api = ExhentaiAPI(client=client)
    cache = CacheManager(config.cache)
    image_service = ImageService(api=api, cache=cache, config=config.cache)
    ws = WebSocketManager()
    tag_database = TagDatabase()
    try:
        await tag_database.download_and_load()
    except Exception:
        pass  # Non-fatal: suggest will return empty results
    state_file = config_path.parent / "downloads.json"
    downloads = DownloadManager(
        api=api, config=config.download, ws=ws,
        image_service=image_service, state_file=state_file,
    )
    return AppState(
        config=config, config_path=config_path,
        client=client, api=api,
        downloads=downloads, cache=cache,
        image_service=image_service, ws=ws,
        db=db, tag_database=tag_database,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = await _build_state()
    app.state.pandora = state
    await state.start(
        _cache_eviction_loop(state.cache, state.config.cache.eviction_interval_seconds)
    )
    yield
    await state.shutdown()

def create_app() -> FastAPI:
    from pandora_daemon.routes import router
    app = FastAPI(title="pandora-daemon", lifespan=lifespan)

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError):
        return JSONResponse(status_code=401, content={"error": "auth", "detail": str(exc)})

    @app.exception_handler(GalleryNotFoundError)
    async def gallery_not_found_handler(request: Request, exc: GalleryNotFoundError):
        return JSONResponse(status_code=404, content={"error": "gallery_not_found", "detail": str(exc)})

    @app.exception_handler(ImageLimitError)
    async def image_limit_handler(request: Request, exc: ImageLimitError):
        return JSONResponse(status_code=429, content={"error": "image_limit", "detail": str(exc)})

    @app.exception_handler(GalleryOffensiveError)
    async def offensive_handler(request: Request, exc: GalleryOffensiveError):
        return JSONResponse(status_code=451, content={"error": "offensive", "detail": str(exc)})

    @app.exception_handler(ParseError)
    async def parse_error_handler(request: Request, exc: ParseError):
        return JSONResponse(status_code=502, content={"error": "parse", "detail": str(exc)})

    @app.exception_handler(NetworkError)
    async def network_error_handler(request: Request, exc: NetworkError):
        return JSONResponse(status_code=502, content={"error": "network", "detail": str(exc)})

    @app.exception_handler(ExhentaiError)
    async def exhentai_error_handler(request: Request, exc: ExhentaiError):
        return JSONResponse(status_code=500, content={"error": "exhentai", "detail": str(exc)})

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    app.include_router(router)
    return app
