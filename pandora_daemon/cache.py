"""Cache manager for pandora-daemon.

Provides two cache layers:
- Disk-based thumbnail cache: SHA256(URL) -> .jpg file, with LRU eviction.
- In-memory gallery detail cache: (gid, token) -> detail with TTL expiry.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from pandora_daemon.config import CacheConfig


class CacheManager:
    """Manages thumbnail and gallery detail caches for the daemon."""

    def __init__(self, config: CacheConfig) -> None:
        self._config = config
        self._thumb_dir = Path(config.thumb_dir)
        self._thumb_dir.mkdir(parents=True, exist_ok=True)
        self._max_bytes = config.thumb_max_size_mb * 1024 * 1024
        self._ttl = config.gallery_ttl_seconds
        self._gallery_cache: dict[str, tuple] = {}

    def _thumb_path(self, url: str) -> Path:
        """Return the file path for a cached thumbnail identified by URL."""
        h = hashlib.sha256(url.encode()).hexdigest()
        return self._thumb_dir / f"{h}.jpg"

    async def get_thumb(self, url: str) -> bytes | None:
        """Return cached thumbnail bytes for *url*, or None if not cached."""
        path = self._thumb_path(url)
        if path.exists():
            return path.read_bytes()
        return None

    async def put_thumb(self, url: str, data: bytes) -> None:
        """Write thumbnail *data* for *url* to the disk cache."""
        path = self._thumb_path(url)
        path.write_bytes(data)

    async def evict_thumbs(self) -> None:
        """Evict oldest thumbnails until total disk usage is within the limit.

        Files are sorted by access time (LRU) and removed oldest-first until
        the total size satisfies ``_max_bytes``.
        """
        if not self._thumb_dir.exists():
            return
        files = sorted(self._thumb_dir.iterdir(), key=lambda p: p.stat().st_atime)
        total = sum(f.stat().st_size for f in files)
        while total > self._max_bytes and files:
            oldest = files.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink()

    def get_gallery(self, gid: str, token: str):
        """Return a cached gallery detail object, or None if missing/expired."""
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
        """Store *detail* in the gallery cache with a TTL-based expiry."""
        key = f"{detail.gid}:{detail.token}"
        self._gallery_cache[key] = (detail, time.time() + self._ttl)
