from fastapi import Request, Depends
from pandora_daemon.state import AppState
from pandora_daemon.providers import GalleryProvider
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService
from pandora_daemon.tag_database import TagDatabase
from pandora_daemon.db import PandoraDB

def get_state(request: Request) -> AppState:
    return request.app.state.pandora

def get_gallery_provider(
    state: AppState = Depends(get_state),
) -> GalleryProvider:
    return state.provider

def get_downloads(state: AppState = Depends(get_state)) -> DownloadManager:
    return state.downloads

def get_cache(state: AppState = Depends(get_state)) -> CacheManager:
    return state.cache

def get_ws(state: AppState = Depends(get_state)) -> WebSocketManager:
    return state.ws

def get_image_service(state: AppState = Depends(get_state)) -> ImageService:
    return state.image_service

def get_tag_database(state: AppState = Depends(get_state)) -> TagDatabase:
    return state.tag_database

def get_db(state: AppState = Depends(get_state)) -> PandoraDB:
    return state.db
