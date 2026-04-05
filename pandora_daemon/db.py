"""PandoraDB — SQLite database layer for pandora-daemon.

Manages 6 tables: history, local_favorites, bookmarks, quick_search, filter,
gallery_tags_cache. Uses aiosqlite for async I/O.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite

# ── filter mode constants ─────────────────────────────────────────────────────

FILTER_TITLE = 0
FILTER_UPLOADER = 1
FILTER_TAG = 2
FILTER_TAG_NAMESPACE = 3

# ── schema ────────────────────────────────────────────────────────────────────

SCHEMA_VERSION = 1

_MIGRATIONS: dict[int, list[str]] = {
    0: [
        """CREATE TABLE history (
            gid        TEXT PRIMARY KEY,
            token      TEXT NOT NULL,
            title      TEXT NOT NULL,
            title_jpn  TEXT,
            category   TEXT NOT NULL DEFAULT '',
            uploader   TEXT NOT NULL DEFAULT '',
            thumb_url  TEXT NOT NULL DEFAULT '',
            posted     TEXT NOT NULL DEFAULT '',
            rating     REAL NOT NULL DEFAULT 0.0,
            pages      INTEGER NOT NULL DEFAULT 0,
            read_page  INTEGER NOT NULL DEFAULT 0,
            time       INTEGER NOT NULL
        )""",
        "CREATE INDEX idx_history_time ON history(time DESC)",
        """CREATE TABLE local_favorites (
            gid        TEXT PRIMARY KEY,
            token      TEXT NOT NULL,
            title      TEXT NOT NULL,
            title_jpn  TEXT,
            category   TEXT NOT NULL DEFAULT '',
            uploader   TEXT NOT NULL DEFAULT '',
            thumb_url  TEXT NOT NULL DEFAULT '',
            posted     TEXT NOT NULL DEFAULT '',
            rating     REAL NOT NULL DEFAULT 0.0,
            pages      INTEGER NOT NULL DEFAULT 0,
            time       INTEGER NOT NULL
        )""",
        "CREATE INDEX idx_local_fav_time ON local_favorites(time DESC)",
        """CREATE TABLE bookmarks (
            gid        TEXT PRIMARY KEY,
            token      TEXT NOT NULL,
            title      TEXT NOT NULL,
            thumb_url  TEXT NOT NULL DEFAULT '',
            page       INTEGER NOT NULL,
            total      INTEGER NOT NULL DEFAULT 0,
            time       INTEGER NOT NULL
        )""",
        "CREATE INDEX idx_bookmarks_time ON bookmarks(time DESC)",
        """CREATE TABLE quick_search (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            keyword    TEXT NOT NULL DEFAULT '',
            category   INTEGER,
            min_rating INTEGER,
            page_from  INTEGER,
            page_to    INTEGER,
            time       INTEGER NOT NULL
        )""",
        """CREATE TABLE filter (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            mode       INTEGER NOT NULL,
            text       TEXT NOT NULL,
            enabled    INTEGER NOT NULL DEFAULT 1
        )""",
        """CREATE TABLE gallery_tags_cache (
            gid         TEXT PRIMARY KEY,
            tags_json   TEXT NOT NULL,
            created_at  INTEGER NOT NULL,
            updated_at  INTEGER NOT NULL
        )""",
    ],
}

_HISTORY_MAX = 200


def _row_to_dict(row: aiosqlite.Row) -> dict[str, Any]:
    return dict(row)


class PandoraDB:
    """Facade for all pandora SQLite database operations."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Open connection and run migrations."""
        self._db = await aiosqlite.connect(str(self._db_path))
        self._db.row_factory = aiosqlite.Row
        async with self._db.execute("PRAGMA user_version") as cur:
            row = await cur.fetchone()
        current_version = row[0]
        if current_version < SCHEMA_VERSION:
            await self._migrate(current_version)

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    # ── migration ─────────────────────────────────────────────────────────────

    async def _migrate(self, current_version: int) -> None:
        for version in range(current_version, SCHEMA_VERSION):
            for sql in _MIGRATIONS[version]:
                await self._db.execute(sql)
        await self._db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        await self._db.commit()

    # ── history ───────────────────────────────────────────────────────────────

    async def put_history(self, gallery: Any) -> None:
        """Upsert a gallery into history. Accepts GalleryListItem or GalleryDetail."""
        thumb_url = getattr(gallery, "cover_url", None) or getattr(gallery, "thumb_url", "")
        title_jpn = getattr(gallery, "title_jpn", None)
        now = int(time.time())
        await self._db.execute(
            """INSERT OR REPLACE INTO history
               (gid, token, title, title_jpn, category, uploader, thumb_url,
                posted, rating, pages, read_page, time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(
                   (SELECT read_page FROM history WHERE gid = ?), 0
               ), ?)""",
            (
                gallery.gid, gallery.token, gallery.title, title_jpn,
                gallery.category, gallery.uploader, thumb_url,
                gallery.posted, gallery.rating, gallery.pages,
                gallery.gid, now,
            ),
        )
        # Keep max 200 entries — delete oldest beyond limit
        await self._db.execute(
            """DELETE FROM history WHERE gid IN (
               SELECT gid FROM history ORDER BY time DESC LIMIT -1 OFFSET ?
            )""",
            (_HISTORY_MAX,),
        )
        await self._db.commit()

    async def get_history(self, limit: int = 50, offset: int = 0) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM history ORDER BY time DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def delete_history(self, gid: str) -> None:
        await self._db.execute("DELETE FROM history WHERE gid = ?", (gid,))
        await self._db.commit()

    async def clear_history(self) -> None:
        await self._db.execute("DELETE FROM history")
        await self._db.commit()

    # ── local_favorites ───────────────────────────────────────────────────────

    async def add_local_favorite(self, gallery: Any) -> None:
        thumb_url = getattr(gallery, "cover_url", None) or getattr(gallery, "thumb_url", "")
        title_jpn = getattr(gallery, "title_jpn", None)
        now = int(time.time())
        await self._db.execute(
            """INSERT OR REPLACE INTO local_favorites
               (gid, token, title, title_jpn, category, uploader, thumb_url,
                posted, rating, pages, time)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                gallery.gid, gallery.token, gallery.title, title_jpn,
                gallery.category, gallery.uploader, thumb_url,
                gallery.posted, gallery.rating, gallery.pages, now,
            ),
        )
        await self._db.commit()

    async def remove_local_favorite(self, gid: str) -> None:
        await self._db.execute("DELETE FROM local_favorites WHERE gid = ?", (gid,))
        await self._db.commit()

    async def get_local_favorites(self, limit: int = 50, offset: int = 0) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM local_favorites ORDER BY time DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def is_local_favorite(self, gid: str) -> bool:
        async with self._db.execute(
            "SELECT 1 FROM local_favorites WHERE gid = ?", (gid,)
        ) as cur:
            row = await cur.fetchone()
        return row is not None

    # ── bookmarks ─────────────────────────────────────────────────────────────

    async def update_bookmark(
        self, gid: str, token: str, title: str, thumb_url: str, page: int, total: int
    ) -> None:
        now = int(time.time())
        await self._db.execute(
            """INSERT OR REPLACE INTO bookmarks
               (gid, token, title, thumb_url, page, total, time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (gid, token, title, thumb_url, page, total, now),
        )
        await self._db.commit()

    async def get_bookmark(self, gid: str) -> dict | None:
        async with self._db.execute(
            "SELECT * FROM bookmarks WHERE gid = ?", (gid,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_dict(row) if row else None

    async def get_bookmarks(self, limit: int = 50, offset: int = 0) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM bookmarks ORDER BY time DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def delete_bookmark(self, gid: str) -> None:
        await self._db.execute("DELETE FROM bookmarks WHERE gid = ?", (gid,))
        await self._db.commit()

    # ── quick_search ──────────────────────────────────────────────────────────

    async def add_quick_search(
        self,
        name: str,
        keyword: str = "",
        category: int | None = None,
        min_rating: int | None = None,
        page_from: int | None = None,
        page_to: int | None = None,
    ) -> int:
        now = int(time.time())
        async with self._db.execute(
            """INSERT INTO quick_search
               (name, keyword, category, min_rating, page_from, page_to, time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (name, keyword, category, min_rating, page_from, page_to, now),
        ) as cur:
            row_id = cur.lastrowid
        await self._db.commit()
        return row_id

    async def get_quick_searches(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM quick_search ORDER BY time DESC") as cur:
            rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def delete_quick_search(self, id: int) -> None:
        await self._db.execute("DELETE FROM quick_search WHERE id = ?", (id,))
        await self._db.commit()

    # ── filter ────────────────────────────────────────────────────────────────

    async def add_filter(self, mode: int, text: str) -> int:
        async with self._db.execute(
            "INSERT INTO filter (mode, text, enabled) VALUES (?, ?, 1)",
            (mode, text),
        ) as cur:
            row_id = cur.lastrowid
        await self._db.commit()
        return row_id

    async def get_filters(self) -> list[dict]:
        async with self._db.execute("SELECT * FROM filter") as cur:
            rows = await cur.fetchall()
        return [_row_to_dict(r) for r in rows]

    async def toggle_filter(self, id: int) -> None:
        await self._db.execute(
            "UPDATE filter SET enabled = 1 - enabled WHERE id = ?", (id,)
        )
        await self._db.commit()

    async def delete_filter(self, id: int) -> None:
        await self._db.execute("DELETE FROM filter WHERE id = ?", (id,))
        await self._db.commit()

    async def apply_filters(self, galleries: list[dict]) -> list[dict]:
        """Return galleries that do NOT match any enabled filter."""
        filters = await self.get_filters()
        enabled = [f for f in filters if f["enabled"]]
        if not enabled:
            return galleries

        result = []
        for gallery in galleries:
            excluded = False
            for f in enabled:
                mode = f["mode"]
                text = f["text"]
                if mode == FILTER_TITLE:
                    if text.lower() in gallery.get("title", "").lower():
                        excluded = True
                        break
                elif mode == FILTER_UPLOADER:
                    if text.lower() == gallery.get("uploader", "").lower():
                        excluded = True
                        break
                elif mode == FILTER_TAG:
                    tags = await self.get_cached_tags(gallery.get("gid", ""))
                    if tags:
                        for tag_list in tags.values():
                            if text in tag_list:
                                excluded = True
                                break
                    if excluded:
                        break
                elif mode == FILTER_TAG_NAMESPACE:
                    tags = await self.get_cached_tags(gallery.get("gid", ""))
                    if tags and text in tags:
                        excluded = True
                        break
            if not excluded:
                result.append(gallery)
        return result

    # ── gallery_tags_cache ────────────────────────────────────────────────────

    async def get_cached_tags(self, gid: str) -> dict | None:
        async with self._db.execute(
            "SELECT tags_json FROM gallery_tags_cache WHERE gid = ?", (gid,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    async def put_cached_tags(self, gid: str, tags: dict) -> None:
        now = int(time.time())
        await self._db.execute(
            """INSERT INTO gallery_tags_cache (gid, tags_json, created_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(gid) DO UPDATE SET tags_json = excluded.tags_json,
                                              updated_at = excluded.updated_at""",
            (gid, json.dumps(tags), now, now),
        )
        await self._db.commit()
