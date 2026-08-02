from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pandora_daemon.config import PandoraConfig
from pandora_daemon.providers import GalleryProvider
from pandora_daemon.download import DownloadManager
from pandora_daemon.cache import CacheManager
from pandora_daemon.ws import WebSocketManager
from pandora_daemon.image_service import ImageService
from pandora_daemon.db import PandoraDB


@dataclass
class AppState:
    config: PandoraConfig
    config_path: Path
    provider: GalleryProvider
    downloads: DownloadManager
    cache: CacheManager
    image_service: ImageService
    ws: WebSocketManager
    db: PandoraDB
    _eviction_task: asyncio.Task[None] | None = field(
        default=None, init=False, repr=False
    )

    async def start(self, eviction_loop_coro: Any) -> None:
        """Start background tasks (downloads + cache eviction)."""
        await self.downloads.start()
        self._eviction_task = asyncio.create_task(eviction_loop_coro)

    async def shutdown(self) -> None:
        """Shut down all components in dependency order."""
        if self._eviction_task is not None:
            self._eviction_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._eviction_task
        await self.downloads.shutdown()
        await self.image_service.shutdown()
        await self.db.close()
        await self.provider.aclose()
