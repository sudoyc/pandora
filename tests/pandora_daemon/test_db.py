"""Tests for pandora_daemon.db module — PandoraDB database layer."""
from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from pandora_daemon.db import PandoraDB, FILTER_TITLE, FILTER_UPLOADER, FILTER_TAG, FILTER_TAG_NAMESPACE


# ── helpers ──────────────────────────────────────────────────────────────────

def make_list_item(gid="123", token="abc", title="Test Gallery", category="Doujinshi",
                   uploader="author", thumb_url="https://example.com/thumb.jpg",
                   posted="2024-01-01", rating=4.5, pages=20):
    """Simulate a GalleryListItem (duck typing)."""
    return SimpleNamespace(
        gid=gid, token=token, title=title, category=category,
        uploader=uploader, thumb_url=thumb_url, posted=posted,
        rating=rating, pages=pages,
    )


def make_detail(gid="456", token="def", title="Detail Gallery", title_jpn="詳細ギャラリー",
                category="Manga", uploader="mangaka", cover_url="https://example.com/cover.jpg",
                posted="2024-02-01", rating=3.5, pages=50):
    """Simulate a GalleryDetail (duck typing — has cover_url and title_jpn)."""
    return SimpleNamespace(
        gid=gid, token=token, title=title, title_jpn=title_jpn,
        category=category, uploader=uploader, cover_url=cover_url,
        posted=posted, rating=rating, pages=pages,
    )


async def make_db() -> PandoraDB:
    db = PandoraDB(Path(":memory:"))
    await db.initialize()
    return db


# ── initialize + migrate ──────────────────────────────────────────────────────

class TestInitialize:
    @pytest.mark.asyncio
    async def test_tables_created(self):
        db = await make_db()
        # Query sqlite_master to verify all 6 tables exist
        async with db._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ) as cur:
            rows = await cur.fetchall()
        table_names = {r[0] for r in rows}
        assert "history" in table_names
        assert "local_favorites" in table_names
        assert "bookmarks" in table_names
        assert "quick_search" in table_names
        assert "filter" in table_names
        assert "gallery_tags_cache" in table_names
        await db.close()

    @pytest.mark.asyncio
    async def test_schema_version_set(self):
        db = await make_db()
        async with db._db.execute("PRAGMA user_version") as cur:
            row = await cur.fetchone()
        assert row[0] == 1
        await db.close()


# ── history ───────────────────────────────────────────────────────────────────

class TestHistory:
    @pytest.mark.asyncio
    async def test_put_and_get_list_item(self):
        db = await make_db()
        item = make_list_item()
        await db.put_history(item)
        rows = await db.get_history()
        assert len(rows) == 1
        assert rows[0]["gid"] == "123"
        assert rows[0]["title"] == "Test Gallery"
        assert rows[0]["thumb_url"] == "https://example.com/thumb.jpg"
        assert rows[0]["title_jpn"] is None
        await db.close()

    @pytest.mark.asyncio
    async def test_put_and_get_detail(self):
        db = await make_db()
        detail = make_detail()
        await db.put_history(detail)
        rows = await db.get_history()
        assert len(rows) == 1
        assert rows[0]["gid"] == "456"
        assert rows[0]["thumb_url"] == "https://example.com/cover.jpg"
        assert rows[0]["title_jpn"] == "詳細ギャラリー"
        await db.close()

    @pytest.mark.asyncio
    async def test_delete_history(self):
        db = await make_db()
        await db.put_history(make_list_item(gid="1"))
        await db.put_history(make_list_item(gid="2"))
        await db.delete_history("1")
        rows = await db.get_history()
        assert len(rows) == 1
        assert rows[0]["gid"] == "2"
        await db.close()

    @pytest.mark.asyncio
    async def test_clear_history(self):
        db = await make_db()
        for i in range(5):
            await db.put_history(make_list_item(gid=str(i)))
        await db.clear_history()
        rows = await db.get_history()
        assert rows == []
        await db.close()

    @pytest.mark.asyncio
    async def test_history_limit_200(self):
        db = await make_db()
        # Insert 210 entries
        for i in range(210):
            item = make_list_item(gid=str(i))
            await db.put_history(item)
        rows = await db.get_history(limit=300)
        assert len(rows) == 200
        await db.close()


# ── local_favorites ───────────────────────────────────────────────────────────

class TestLocalFavorites:
    @pytest.mark.asyncio
    async def test_add_and_get(self):
        db = await make_db()
        await db.add_local_favorite(make_list_item(gid="10", title="Fav Gallery"))
        rows = await db.get_local_favorites()
        assert len(rows) == 1
        assert rows[0]["gid"] == "10"
        assert rows[0]["title"] == "Fav Gallery"
        await db.close()

    @pytest.mark.asyncio
    async def test_remove_local_favorite(self):
        db = await make_db()
        await db.add_local_favorite(make_list_item(gid="10"))
        await db.add_local_favorite(make_list_item(gid="11"))
        await db.remove_local_favorite("10")
        rows = await db.get_local_favorites()
        assert len(rows) == 1
        assert rows[0]["gid"] == "11"
        await db.close()

    @pytest.mark.asyncio
    async def test_is_local_favorite_true(self):
        db = await make_db()
        await db.add_local_favorite(make_list_item(gid="20"))
        assert await db.is_local_favorite("20") is True
        await db.close()

    @pytest.mark.asyncio
    async def test_is_local_favorite_false(self):
        db = await make_db()
        assert await db.is_local_favorite("999") is False
        await db.close()


# ── bookmarks ─────────────────────────────────────────────────────────────────

class TestBookmarks:
    @pytest.mark.asyncio
    async def test_update_and_get_bookmark(self):
        db = await make_db()
        await db.update_bookmark("100", "tok1", "Bookmarked Gallery", "https://example.com/t.jpg", 5, 30)
        bm = await db.get_bookmark("100")
        assert bm is not None
        assert bm["gid"] == "100"
        assert bm["page"] == 5
        assert bm["total"] == 30
        await db.close()

    @pytest.mark.asyncio
    async def test_get_bookmark_not_found(self):
        db = await make_db()
        bm = await db.get_bookmark("nonexistent")
        assert bm is None
        await db.close()

    @pytest.mark.asyncio
    async def test_get_bookmarks_list(self):
        db = await make_db()
        await db.update_bookmark("1", "t1", "Gallery 1", "url1", 1, 10)
        await db.update_bookmark("2", "t2", "Gallery 2", "url2", 2, 20)
        rows = await db.get_bookmarks()
        assert len(rows) == 2
        await db.close()

    @pytest.mark.asyncio
    async def test_delete_bookmark(self):
        db = await make_db()
        await db.update_bookmark("1", "t1", "Gallery 1", "url1", 1, 10)
        await db.delete_bookmark("1")
        bm = await db.get_bookmark("1")
        assert bm is None
        await db.close()


# ── quick_search ──────────────────────────────────────────────────────────────

class TestQuickSearch:
    @pytest.mark.asyncio
    async def test_add_and_get(self):
        db = await make_db()
        id_ = await db.add_quick_search("My Search", keyword="artist:foo", category=2, min_rating=3)
        rows = await db.get_quick_searches()
        assert len(rows) == 1
        assert rows[0]["id"] == id_
        assert rows[0]["name"] == "My Search"
        assert rows[0]["keyword"] == "artist:foo"
        assert rows[0]["category"] == 2
        assert rows[0]["min_rating"] == 3
        await db.close()

    @pytest.mark.asyncio
    async def test_add_returns_id(self):
        db = await make_db()
        id1 = await db.add_quick_search("Search 1")
        id2 = await db.add_quick_search("Search 2")
        assert id1 != id2
        assert isinstance(id1, int)
        await db.close()

    @pytest.mark.asyncio
    async def test_delete_quick_search(self):
        db = await make_db()
        id_ = await db.add_quick_search("To Delete")
        await db.delete_quick_search(id_)
        rows = await db.get_quick_searches()
        assert rows == []
        await db.close()


# ── filter ────────────────────────────────────────────────────────────────────

class TestFilter:
    @pytest.mark.asyncio
    async def test_add_and_get(self):
        db = await make_db()
        id_ = await db.add_filter(FILTER_TITLE, "bad word")
        rows = await db.get_filters()
        assert len(rows) == 1
        assert rows[0]["id"] == id_
        assert rows[0]["mode"] == FILTER_TITLE
        assert rows[0]["text"] == "bad word"
        assert rows[0]["enabled"] == 1
        await db.close()

    @pytest.mark.asyncio
    async def test_toggle_filter(self):
        db = await make_db()
        id_ = await db.add_filter(FILTER_UPLOADER, "spammer")
        await db.toggle_filter(id_)
        rows = await db.get_filters()
        assert rows[0]["enabled"] == 0
        await db.toggle_filter(id_)
        rows = await db.get_filters()
        assert rows[0]["enabled"] == 1
        await db.close()

    @pytest.mark.asyncio
    async def test_delete_filter(self):
        db = await make_db()
        id_ = await db.add_filter(FILTER_TITLE, "junk")
        await db.delete_filter(id_)
        rows = await db.get_filters()
        assert rows == []
        await db.close()

    @pytest.mark.asyncio
    async def test_apply_filters_title(self):
        db = await make_db()
        await db.add_filter(FILTER_TITLE, "forbidden")
        galleries = [
            {"gid": "1", "title": "A Forbidden Gallery", "uploader": "user1"},
            {"gid": "2", "title": "A Clean Gallery", "uploader": "user2"},
        ]
        result = await db.apply_filters(galleries)
        assert len(result) == 1
        assert result[0]["gid"] == "2"
        await db.close()

    @pytest.mark.asyncio
    async def test_apply_filters_uploader(self):
        db = await make_db()
        await db.add_filter(FILTER_UPLOADER, "spammer")
        galleries = [
            {"gid": "1", "title": "Gallery A", "uploader": "Spammer"},
            {"gid": "2", "title": "Gallery B", "uploader": "gooduser"},
        ]
        result = await db.apply_filters(galleries)
        assert len(result) == 1
        assert result[0]["gid"] == "2"
        await db.close()

    @pytest.mark.asyncio
    async def test_apply_filters_tag(self):
        db = await make_db()
        await db.add_filter(FILTER_TAG, "loli")
        # Put tags in cache for gid "1"
        await db.put_cached_tags("1", {"female": ["loli", "schoolgirl"]})
        galleries = [
            {"gid": "1", "title": "Gallery A", "uploader": "user"},
            {"gid": "2", "title": "Gallery B", "uploader": "user"},
        ]
        result = await db.apply_filters(galleries)
        assert len(result) == 1
        assert result[0]["gid"] == "2"
        await db.close()


# ── gallery_tags_cache ────────────────────────────────────────────────────────

class TestGalleryTagsCache:
    @pytest.mark.asyncio
    async def test_put_and_get(self):
        db = await make_db()
        tags = {"artist": ["foo"], "female": ["bar", "baz"]}
        await db.put_cached_tags("999", tags)
        result = await db.get_cached_tags("999")
        assert result == tags
        await db.close()

    @pytest.mark.asyncio
    async def test_get_not_found_returns_none(self):
        db = await make_db()
        result = await db.get_cached_tags("nonexistent")
        assert result is None
        await db.close()

    @pytest.mark.asyncio
    async def test_put_upsert(self):
        db = await make_db()
        await db.put_cached_tags("111", {"artist": ["old"]})
        await db.put_cached_tags("111", {"artist": ["new"]})
        result = await db.get_cached_tags("111")
        assert result == {"artist": ["new"]}
        await db.close()
