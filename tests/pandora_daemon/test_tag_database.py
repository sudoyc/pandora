import pytest
import httpx
from pandora_daemon.tag_database import TagDatabase, TagEntry


SAMPLE_DB_JSON = {
    "repo": "EhTagTranslation/DatabaseReleases",
    "head": {"sha": "abc123"},
    "data": [
        {
            "namespace": "female",
            "data": {
                "stockings": {"name": "丝袜", "intro": "", "links": ""},
                "stockings only": {"name": "仅穿丝袜", "intro": "", "links": ""},
                "striped stockings": {"name": "条纹丝袜", "intro": "", "links": ""},
                "maid": {"name": "女仆", "intro": "", "links": ""},
            },
        },
        {
            "namespace": "male",
            "data": {
                "stockings": {"name": "丝袜", "intro": "", "links": ""},
            },
        },
        {
            "namespace": "artist",
            "data": {
                "kemuri haku": {"name": "けむり白", "intro": "", "links": ""},
            },
        },
    ],
}


def test_status_before_load_reports_empty_metadata(tmp_path):
    db = TagDatabase()

    status = db.status(cache_path=tmp_path / "db.text.json")

    assert status["loaded"] is False
    assert status["entries"] == 0
    assert status["source_url"]
    assert status["cache_path"] == str(tmp_path / "db.text.json")
    assert status["etag"] is None
    assert status["upstream_repo"] is None
    assert status["upstream_sha"] is None
    assert status["last_error"] is None


def test_load_from_dict_records_metadata(tmp_path):
    db = TagDatabase()

    db.load_from_dict(SAMPLE_DB_JSON, cache_path=tmp_path / "db.text.json", metadata={"etag": '"v1"'})

    status = db.status(cache_path=tmp_path / "db.text.json")

    assert status["loaded"] is True
    assert status["entries"] == 6
    assert status["etag"] == '"v1"'
    assert status["upstream_repo"] == "EhTagTranslation/DatabaseReleases"
    assert status["upstream_sha"] == "abc123"


@pytest.mark.asyncio
async def test_download_and_load_writes_cache_and_metadata_atomically(tmp_path, monkeypatch):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, **kwargs):
            return httpx.Response(200, json=SAMPLE_DB_JSON, headers={"ETag": '"v1"'})

    monkeypatch.setattr("pandora_daemon.tag_database.httpx.AsyncClient", FakeAsyncClient)
    db = TagDatabase()
    cache_path = tmp_path / "db.text.json"

    await db.download_and_load(cache_path=cache_path)

    assert cache_path.exists()
    metadata_path = tmp_path / "metadata.json"
    assert metadata_path.exists()
    status = db.status(cache_path=cache_path)
    assert status["entries"] == 6
    assert status["etag"] == '"v1"'
    assert status["source_url"].startswith("https://")
    assert status["upstream_repo"] == "EhTagTranslation/DatabaseReleases"
    assert status["upstream_sha"] == "abc123"
    assert not (tmp_path / "db.text.json.tmp").exists()
    assert not (tmp_path / "metadata.json.tmp").exists()


@pytest.mark.asyncio
async def test_refresh_uses_etag_and_preserves_loaded_data_on_304(tmp_path, monkeypatch):
    seen_headers = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, **kwargs):
            seen_headers.append(headers or {})
            return httpx.Response(304)

    monkeypatch.setattr("pandora_daemon.tag_database.httpx.AsyncClient", FakeAsyncClient)
    db = TagDatabase()
    cache_path = tmp_path / "db.text.json"
    db.load_from_dict(SAMPLE_DB_JSON, cache_path=cache_path, metadata={"etag": '"v1"'})

    result = await db.refresh(cache_path=cache_path, force=False)

    assert result["ok"] is True
    assert result["updated"] is False
    assert seen_headers == [{"If-None-Match": '"v1"'}]
    assert db.translate("female", "maid") == "女仆"
    assert result["status"]["entries"] == 6


@pytest.mark.asyncio
async def test_failed_refresh_preserves_entries_and_records_last_error(tmp_path, monkeypatch):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, headers=None, **kwargs):
            raise httpx.ConnectError("network down")

    monkeypatch.setattr("pandora_daemon.tag_database.httpx.AsyncClient", FakeAsyncClient)
    db = TagDatabase()
    cache_path = tmp_path / "db.text.json"
    db.load_from_dict(SAMPLE_DB_JSON, cache_path=cache_path)

    result = await db.refresh(cache_path=cache_path)

    assert result["ok"] is False
    assert result["updated"] is False
    assert result["error"]["code"] == "refresh_failed"
    assert "network down" in result["error"]["message"]
    assert db.translate("female", "maid") == "女仆"
    assert result["status"]["entries"] == 6
    assert "network down" in result["status"]["last_error"]


class TestTagDatabase:
    def setup_method(self):
        self.db = TagDatabase()
        self.db.load_from_dict(SAMPLE_DB_JSON)

    def test_load_entry_count(self):
        assert len(self.db.entries) == 6

    def test_suggest_english_substring(self):
        results = self.db.suggest("stocking", limit=10)
        tags = [r.tag for r in results]
        assert "stockings" in tags
        assert "stockings only" in tags
        assert "striped stockings" in tags

    def test_suggest_chinese_substring(self):
        results = self.db.suggest("丝袜", limit=10)
        assert len(results) >= 2  # female:stockings + male:stockings

    def test_suggest_limit(self):
        results = self.db.suggest("stock", limit=2)
        assert len(results) == 2

    def test_suggest_prefix_match_ranked_first(self):
        results = self.db.suggest("stock", limit=10)
        # "stockings" and "stockings only" start with "stock" → ranked before "striped stockings"
        first_tags = [r.tag for r in results[:3]]
        assert first_tags[0] == "stockings" or first_tags[0] == "stockings only"

    def test_suggest_no_match(self):
        results = self.db.suggest("zzzznotexist", limit=10)
        assert results == []

    def test_suggest_empty_query(self):
        results = self.db.suggest("", limit=10)
        assert results == []

    def test_translate_exact(self):
        result = self.db.translate("female", "maid")
        assert result == "女仆"

    def test_translate_not_found(self):
        result = self.db.translate("female", "nonexistent")
        assert result is None
