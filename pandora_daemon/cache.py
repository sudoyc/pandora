"""Cache manager for pandora-daemon.

Provides two cache layers:
- Disk-based unified image cache: SHA256(URL) -> file, with LRU eviction.
- In-memory gallery detail cache: (gid, token) -> detail with TTL expiry.
"""
from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path

from pandora_daemon.config import CacheConfig


def _ext_from_url(url: str) -> str:
    """Derive file extension from URL path. Falls back to '.jpg'."""
    path = url.split("?")[0].split("#")[0]
    match = re.search(r"\.([a-zA-Z]{3,4})$", path)
    if match:
        return f".{match.group(1).lower()}"
    return ".jpg"


class CacheManager:
    """Manages unified image cache and gallery detail cache."""

    def __init__(self, config: CacheConfig) -> None:
        self._config = config
        self._image_dir = Path(config.image_dir).expanduser()
        self._image_dir.mkdir(parents=True, exist_ok=True)
        self._max_bytes = config.image_max_size_mb * 1024 * 1024
        self._ttl = config.gallery_ttl_seconds
        self._gallery_cache: dict[str, tuple] = {}

    def _image_path(self, url: str) -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()
        ext = _ext_from_url(url)
        return self._image_dir / f"{h}{ext}"

    async def get_image(self, url: str) -> bytes | None:
        path = self._image_path(url)
        if path.exists():
            return path.read_bytes()
        return None

    async def put_image(self, url: str, data: bytes) -> None:
        path = self._image_path(url)
        path.write_bytes(data)

    async def evict_images(self) -> None:
        if not self._image_dir.exists():
            return
        files = sorted(self._image_dir.iterdir(), key=lambda p: p.stat().st_atime)
        total = sum(f.stat().st_size for f in files)
        while total > self._max_bytes and files:
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink()

    def get_gallery(self, gid: str, token: str):
        key = f"{gid}:{token}"
        entry = self._gallery_cache.get(key)
        if entry is None:
            return None
        detail, expires_at = entry
        if time.time() > expires_at:
            del self._gallery_cache[key]
            return None
        return detail

    def put_gallery(self, detail) -> None:
        key = f"{detail.gid}:{detail.token}"
        self._gallery_cache[key] = (detail, time.time() + self._ttl)
