import pytest
from pandora_daemon.tag_database import TagDatabase, TagEntry


SAMPLE_DB_JSON = {
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
