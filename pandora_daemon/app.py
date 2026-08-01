import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
from pandora_daemon.config import load_config
from pandora_daemon.diagnostics import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    get_request_id,
    normalize_diagnostic_id,
)
from pandora_daemon.state import AppState
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService
from pandora_daemon.tag_database import TagDatabase
from pandora_daemon.db import PandoraDB
from pandora_daemon.providers import (
    ProviderContext,
    ProviderRegistry,
    default_provider_registry,
)


logger = logging.getLogger(__name__)


AUTH_ERROR_DETAIL = "Authentication failed"
SESSION_ERROR_DETAIL = "Upstream session is invalid"
UPSTREAM_ERROR_DETAIL = "Upstream service request failed"
GALLERY_NOT_FOUND_DETAIL = "Gallery not found"
IMAGE_LIMIT_DETAIL = "Image limit reached"
OFFENSIVE_DETAIL = "Gallery unavailable"
PARSE_ERROR_DETAIL = "Upstream response parse failed"
NETWORK_ERROR_DETAIL = "Upstream network request failed"
PROVIDER_ERROR_DETAIL = "Upstream request failed"
RUNTIME_ERROR_DETAIL = "Internal server error"


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "<unmatched>")


def _log_request_error(
    request: Request,
    code: str,
    exc: Exception,
    *,
    level: int = logging.WARNING,
) -> None:
    correlation_id = normalize_diagnostic_id(
        getattr(request.state, "correlation_id", None)
    )
    logger.log(
        level,
        "Request failed request_id=%s correlation_id=%s code=%s method=%s "
        "route=%s exception=%s",
        get_request_id(request),
        correlation_id or "none",
        code,
        request.method,
        _route_label(request),
        type(exc).__name__,
    )


async def _cache_eviction_loop(cache: CacheManager, interval: int) -> None:
    """Background loop: periodically prune expired galleries and evict images."""
    while True:
        await asyncio.sleep(interval)
        try:
            cache.prune_expired_galleries()
            await cache.evict_images()
        except Exception:
            logger.exception("Cache eviction error")


async def _build_state(
    provider_registry: ProviderRegistry | None = None,
    provider_id: str | None = None,
) -> AppState:
    """Construct all components and return AppState."""
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)
    db_path = config_path.parent / "pandora.db"
    db = PandoraDB(db_path)
    await db.initialize()
    registry = (
        provider_registry
        if provider_registry is not None
        else default_provider_registry()
    )
    candidates = (provider_id, config.provider.id, registry.default_provider_id)
    selected_provider_id = next(
        (
            candidate
            for candidate in candidates
            if candidate is not None and candidate.strip()
        ),
        None,
    )
    if selected_provider_id is None:
        raise ValueError("No provider id configured")
    provider_context = ProviderContext(
        credentials=dict(config.provider.credentials),
        proxy=config.network.proxy,
        timeout=config.network.timeout,
    )
    provider = registry.create(selected_provider_id, provider_context)
    config.provider.id = provider.provider_id
    cache = CacheManager(config.cache)
    image_service = ImageService(provider=provider, cache=cache, config=config.cache)
    ws = WebSocketManager()
    tag_database = TagDatabase()
    try:
        await tag_database.download_and_load()
    except Exception:
        pass  # Non-fatal: suggest will return empty results
    state_file = config_path.parent / "downloads.json"
    downloads = DownloadManager(
        provider=provider, config=config.download, ws=ws,
        image_service=image_service, state_file=state_file,
    )
    return AppState(
        config=config, config_path=config_path,
        provider=provider,
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
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="pandora-daemon", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER, CORRELATION_ID_HEADER],
    )

    @app.middleware("http")
    async def diagnostic_context(request: Request, call_next):
        request_id = get_request_id(request)
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        correlation_id = normalize_diagnostic_id(
            getattr(request.state, "correlation_id", None)
        )
        if correlation_id is not None:
            response.headers[CORRELATION_ID_HEADER] = correlation_id
        logger.info(
            "Request completed request_id=%s correlation_id=%s method=%s "
            "route=%s status=%s",
            request_id,
            correlation_id or "none",
            request.method,
            _route_label(request),
            response.status_code,
        )
        return response

    @app.exception_handler(ProviderAuthenticationError)
    async def auth_error_handler(request: Request, exc: ProviderAuthenticationError):
        _log_request_error(request, "auth", exc)
        return JSONResponse(status_code=401, content={"error": "auth", "detail": AUTH_ERROR_DETAIL})

    @app.exception_handler(ProviderSessionError)
    async def session_error_handler(request: Request, exc: ProviderSessionError):
        _log_request_error(request, "session", exc)
        return JSONResponse(status_code=401, content={"error": "session", "detail": SESSION_ERROR_DETAIL})

    @app.exception_handler(ProviderUpstreamError)
    async def upstream_error_handler(request: Request, exc: ProviderUpstreamError):
        _log_request_error(request, "upstream", exc, level=logging.ERROR)
        return JSONResponse(status_code=502, content={"error": "upstream", "detail": UPSTREAM_ERROR_DETAIL})

    @app.exception_handler(ProviderGalleryNotFoundError)
    async def gallery_not_found_handler(request: Request, exc: ProviderGalleryNotFoundError):
        _log_request_error(request, "gallery_not_found", exc)
        return JSONResponse(status_code=404, content={"error": "gallery_not_found", "detail": GALLERY_NOT_FOUND_DETAIL})

    @app.exception_handler(ProviderQuotaError)
    async def image_limit_handler(request: Request, exc: ProviderQuotaError):
        _log_request_error(request, "image_limit", exc)
        return JSONResponse(status_code=429, content={"error": "image_limit", "detail": IMAGE_LIMIT_DETAIL})

    @app.exception_handler(ProviderContentBlockedError)
    async def offensive_handler(request: Request, exc: ProviderContentBlockedError):
        _log_request_error(request, "offensive", exc)
        return JSONResponse(status_code=451, content={"error": "offensive", "detail": OFFENSIVE_DETAIL})

    @app.exception_handler(ProviderParseError)
    async def parse_error_handler(request: Request, exc: ProviderParseError):
        _log_request_error(request, "parse", exc, level=logging.ERROR)
        return JSONResponse(status_code=502, content={"error": "parse", "detail": PARSE_ERROR_DETAIL})

    @app.exception_handler(ProviderNetworkError)
    async def network_error_handler(request: Request, exc: ProviderNetworkError):
        _log_request_error(request, "network", exc, level=logging.ERROR)
        return JSONResponse(status_code=502, content={"error": "network", "detail": NETWORK_ERROR_DETAIL})

    @app.exception_handler(ProviderError)
    async def provider_error_handler(request: Request, exc: ProviderError):
        _log_request_error(request, exc.public_code, exc, level=logging.ERROR)
        return JSONResponse(status_code=500, content={"error": exc.public_code, "detail": PROVIDER_ERROR_DETAIL})

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        _log_request_error(request, "runtime", exc, level=logging.ERROR)
        return JSONResponse(
            status_code=500,
            content={"error": "internal", "detail": RUNTIME_ERROR_DETAIL},
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        _log_request_error(request, "unhandled", exc, level=logging.ERROR)
        return JSONResponse(
            status_code=500,
            content={"error": "internal", "detail": RUNTIME_ERROR_DETAIL},
        )

    app.include_router(router)
    return app
