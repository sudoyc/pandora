from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from pandora_daemon.config import load_config
from pandora_daemon.state import AppState
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    config_path = Path("~/.config/pandora/config.toml").expanduser()
    config = load_config(config_path)
    client = ExhentaiClient(
        igneous=config.credentials.igneous,
        ipb_member_id=config.credentials.ipb_member_id,
    )
    api = ExhentaiAPI(client=client)
    cache = CacheManager(config.cache)
    ws = WebSocketManager()
    state_file = config_path.parent / "downloads.json"
    downloads = DownloadManager(api=api, config=config.download, ws=ws, state_file=state_file)
    state = AppState(
        config=config, config_path=config_path,
        client=client, api=api,
        downloads=downloads, cache=cache, ws=ws,
    )
    app.state.pandora = state
    await downloads.start()
    yield
    await downloads.shutdown()
    await api.aclose()

def create_app() -> FastAPI:
    from pandora_daemon.routes import router
    app = FastAPI(title="pandora-daemon", lifespan=lifespan)

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        if "Sad Panda" in str(exc):
            return JSONResponse(status_code=401, content={"detail": str(exc)})
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    app.include_router(router)
    return app
