"""EhTagTranslation database for tag autocomplete."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DB_URL = "https://raw.githubusercontent.com/EhTagTranslation/DatabaseReleases/master/db.text.json"
DEFAULT_CACHE_PATH = Path("~/.cache/pandora/tags/db.text.json")


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

    def load_from_dict(self, data: dict[str, Any]) -> None:
        """Parse db.text.json structure into flat entry list."""
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
        logger.info("TagDatabase loaded %d entries", len(entries))

    def load_from_file(self, path: Path) -> None:
        """Load from a local JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.load_from_dict(data)

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
        async with httpx.AsyncClient() as client:
            resp = await client.get(DB_URL, timeout=60.0)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)

        self.load_from_file(cache_path)

    async def check_update(self, cache_path: Path = DEFAULT_CACHE_PATH) -> bool:
        """Check GitHub for newer version and update if available. Returns True if updated."""
        cache_path = cache_path.expanduser()
        try:
            async with httpx.AsyncClient() as client:
                headers = {}
                if cache_path.exists():
                    import email.utils
                    import os
                    mtime = os.path.getmtime(cache_path)
                    headers["If-Modified-Since"] = email.utils.formatdate(mtime, usegmt=True)

                resp = await client.get(DB_URL, headers=headers, timeout=60.0)
                if resp.status_code == 304:
                    return False
                resp.raise_for_status()
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_bytes(resp.content)
                self.load_from_file(cache_path)
                logger.info("TagDatabase updated from GitHub")
                return True
        except Exception:
            logger.warning("TagDatabase update check failed", exc_info=True)
            return False

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
