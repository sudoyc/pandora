"""EhTagTranslation database for tag autocomplete."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DB_URL = "https://raw.githubusercontent.com/EhTagTranslation/DatabaseReleases/master/db.text.json"
DEFAULT_CACHE_PATH = Path("~/.cache/pandora/tags/db.text.json")
DEFAULT_METADATA_PATH = Path("~/.cache/pandora/tags/metadata.json")


@dataclass
class TagEntry:
    namespace: str
    tag: str
    translation: str


class TagDatabase:
    """In-memory EhTagTranslation database with substring search."""

    def __init__(self) -> None:
        self.entries: list[TagEntry] = []
        self._lookup: dict[tuple[str, str], str] = {}  # (namespace, tag) → translation
        self._loaded = False
        self._metadata: dict[str, Any] = {}
        self._last_error: str | None = None

    def _metadata_path(self, cache_path: Path) -> Path:
        if cache_path == DEFAULT_CACHE_PATH.expanduser():
            return DEFAULT_METADATA_PATH.expanduser()
        return cache_path.with_name("metadata.json")

    def _load_metadata_file(self, cache_path: Path) -> dict[str, Any]:
        metadata_path = self._metadata_path(cache_path)
        if not metadata_path.exists():
            return {}
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            logger.warning("Tag database metadata is unreadable", exc_info=True)
            return {}

    def _build_metadata(
        self,
        data: dict[str, Any],
        *,
        cache_path: Path,
        etag: str | None = None,
        metadata: dict[str, Any] | None = None,
        entries: int,
    ) -> dict[str, Any]:
        base = dict(metadata or {})
        if etag is not None:
            base["etag"] = etag
        base.setdefault("source_url", DB_URL)
        base["cache_path"] = str(cache_path)
        base["entries"] = entries
        base["upstream_repo"] = data.get("repo")
        head = data.get("head") if isinstance(data.get("head"), dict) else {}
        base["upstream_sha"] = head.get("sha")
        base["updated_at"] = datetime.now(timezone.utc).isoformat()
        return base

    def load_from_dict(
        self,
        data: dict[str, Any],
        *,
        cache_path: Path = DEFAULT_CACHE_PATH,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Parse db.text.json structure into flat entry list."""
        cache_path = cache_path.expanduser()
        entries: list[TagEntry] = []
        lookup: dict[tuple[str, str], str] = {}
        for ns_block in data.get("data", []):
            namespace = ns_block.get("namespace", "")
            for tag, info in ns_block.get("data", {}).items():
                translation = info.get("name", "")
                entry = TagEntry(namespace=namespace, tag=tag, translation=translation)
                entries.append(entry)
                lookup[(namespace, tag)] = translation
        self.entries = entries
        self._lookup = lookup
        self._loaded = True
        self._metadata = self._build_metadata(
            data,
            cache_path=cache_path,
            metadata=metadata,
            entries=len(entries),
        )
        self._last_error = None
        logger.info("TagDatabase loaded %d entries", len(entries))

    def load_from_file(self, path: Path) -> None:
        """Load from a local JSON file."""
        path = path.expanduser()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_from_dict(data, cache_path=path, metadata=self._load_metadata_file(path))

    def status(self, cache_path: Path = DEFAULT_CACHE_PATH) -> dict[str, Any]:
        """Return machine-readable tag database cache/load status."""
        cache_path = cache_path.expanduser()
        metadata = {**self._load_metadata_file(cache_path), **self._metadata}
        return {
            "loaded": self._loaded,
            "entries": len(self.entries),
            "source_url": metadata.get("source_url", DB_URL),
            "cache_path": str(cache_path),
            "metadata_path": str(self._metadata_path(cache_path)),
            "etag": metadata.get("etag"),
            "upstream_repo": metadata.get("upstream_repo"),
            "upstream_sha": metadata.get("upstream_sha"),
            "last_error": self._last_error,
        }

    def _write_atomic(self, path: Path, content: bytes) -> None:
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_bytes(content)
        tmp_path.replace(path)

    async def download_and_load(self, cache_path: Path = DEFAULT_CACHE_PATH) -> None:
        """Download db.text.json from GitHub, cache locally, and load."""
        cache_path = cache_path.expanduser()
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        # Try loading from cache first
        if cache_path.exists():
            try:
                self.load_from_file(cache_path)
                return
            except Exception:
                logger.warning("Cached tag database corrupted, re-downloading")

        # Download fresh copy
        result = await self.refresh(cache_path=cache_path, force=True)
        if not result["ok"]:
            raise RuntimeError(result["error"]["message"])

    async def check_update(self, cache_path: Path = DEFAULT_CACHE_PATH) -> bool:
        """Check GitHub for newer version and update if available. Returns True if updated."""
        result = await self.refresh(cache_path=cache_path, force=False)
        return bool(result.get("ok") and result.get("updated"))

    async def refresh(self, cache_path: Path = DEFAULT_CACHE_PATH, *, force: bool = False) -> dict[str, Any]:
        """Refresh tag database cache using ETag metadata when available."""
        cache_path = cache_path.expanduser()
        metadata_path = self._metadata_path(cache_path)
        try:
            metadata = {**self._load_metadata_file(cache_path), **self._metadata}
            headers = {}
            if not force and metadata.get("etag"):
                headers["If-None-Match"] = metadata["etag"]

            async with httpx.AsyncClient() as client:
                resp = await client.get(DB_URL, headers=headers, timeout=60.0)
                if resp.status_code == 304:
                    self._last_error = None
                    return {"ok": True, "updated": False, "status": self.status(cache_path=cache_path)}
                if resp.status_code >= 400:
                    resp.raise_for_status()
                data = resp.json()

                entries: list[TagEntry] = []
                lookup: dict[tuple[str, str], str] = {}
                for ns_block in data.get("data", []):
                    namespace = ns_block.get("namespace", "")
                    for tag, info in ns_block.get("data", {}).items():
                        translation = info.get("name", "")
                        entry = TagEntry(namespace=namespace, tag=tag, translation=translation)
                        entries.append(entry)
                        lookup[(namespace, tag)] = translation

                new_metadata = self._build_metadata(
                    data,
                    cache_path=cache_path,
                    etag=resp.headers.get("ETag"),
                    entries=len(entries),
                )
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                metadata_path.parent.mkdir(parents=True, exist_ok=True)
                self._write_atomic(cache_path, resp.content)
                self._write_atomic(metadata_path, json.dumps(new_metadata, ensure_ascii=False, indent=2).encode("utf-8"))

                self.entries = entries
                self._lookup = lookup
                self._loaded = True
                self._metadata = new_metadata
                self._last_error = None
                logger.info("TagDatabase updated from GitHub")
                return {"ok": True, "updated": True, "status": self.status(cache_path=cache_path)}
        except Exception as e:
            self._last_error = str(e)
            logger.warning("TagDatabase update check failed", exc_info=True)
            return {
                "ok": False,
                "updated": False,
                "error": {"code": "refresh_failed", "message": str(e)},
                "status": self.status(cache_path=cache_path),
            }

    def suggest(self, query: str, limit: int = 10) -> list[TagEntry]:
        """Substring match on tag name or translation. Prefix matches ranked first."""
        if not query:
            return []
        q = query.lower()
        prefix_matches: list[TagEntry] = []
        substring_matches: list[TagEntry] = []
        for entry in self.entries:
            tag_lower = entry.tag.lower()
            if tag_lower.startswith(q) or entry.translation.startswith(query):
                prefix_matches.append(entry)
            elif q in tag_lower or query in entry.translation:
                substring_matches.append(entry)
            if len(prefix_matches) + len(substring_matches) >= limit * 2:
                break  # Early exit, we have enough candidates
        results = prefix_matches + substring_matches
        return results[:limit]

    def translate(self, namespace: str, tag: str) -> str | None:
        """Exact lookup for a single tag translation."""
        return self._lookup.get((namespace, tag))
