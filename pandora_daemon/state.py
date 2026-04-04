from dataclasses import dataclass
from pathlib import Path
from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from pandora_daemon.config import PandoraConfig
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService

@dataclass
class AppState:
    config: PandoraConfig
    config_path: Path
    client: ExhentaiClient
    api: ExhentaiAPI
    downloads: DownloadManager
    cache: CacheManager
    image_service: ImageService
    ws: WebSocketManager
