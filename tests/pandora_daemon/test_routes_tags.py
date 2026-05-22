import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from pandora_daemon.tag_database import TagDatabase, TagEntry

SAMPLE_DB = {
    "data": [
        {
            "namespace": "female",
            "data": {
                "stockings": {"name": "丝袜", "intro": "", "links": ""},
                "maid": {"name": "女仆", "intro": "", "links": ""},
            },
        },
    ],
}


@pytest.fixture
def app_with_tags():
    from pandora_daemon.app import create_app

    app = create_app()
    tag_db = TagDatabase()
    tag_db.load_from_dict(SAMPLE_DB)

    mock_state = MagicMock()
    mock_state.tag_database = tag_db
    app.state.pandora = mock_state
    return app


def test_suggest_returns_matches(app_with_tags):
    client = TestClient(app_with_tags)
    resp = client.get("/api/tags/suggest?q=stock")
    assert resp.status_code == 200
    data = resp.json()
    assert "suggestions" in data
    assert len(data["suggestions"]) >= 1
    assert data["suggestions"][0]["tag"] == "stockings"
    assert data["suggestions"][0]["namespace"] == "female"
    assert data["suggestions"][0]["translation"] == "丝袜"


def test_suggest_empty_query(app_with_tags):
    client = TestClient(app_with_tags)
    resp = client.get("/api/tags/suggest?q=")
    assert resp.status_code == 200
    assert resp.json()["suggestions"] == []


def test_suggest_respects_limit(app_with_tags):
    client = TestClient(app_with_tags)
    resp = client.get("/api/tags/suggest?q=m&limit=1")
    assert resp.status_code == 200
    assert len(resp.json()["suggestions"]) <= 1


def test_suggest_chinese_query(app_with_tags):
    client = TestClient(app_with_tags)
    resp = client.get("/api/tags/suggest?q=女仆")
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert any(s["tag"] == "maid" for s in suggestions)


def test_tags_status_returns_database_status(app_with_tags):
    client = TestClient(app_with_tags)

    resp = client.get("/api/tags/status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["loaded"] is True
    assert data["entries"] == 2


def test_tags_refresh_passes_force_false_by_default(app_with_tags, monkeypatch):
    calls = []

    async def fake_refresh(self, *, force=False):
        calls.append(force)
        return {"ok": True, "updated": False, "status": {"entries": 2}}

    monkeypatch.setattr(TagDatabase, "refresh", fake_refresh)
    client = TestClient(app_with_tags)

    resp = client.post("/api/tags/refresh")

    assert resp.status_code == 200
    assert resp.json()["updated"] is False
    assert calls == [False]


def test_tags_refresh_passes_force_true(app_with_tags, monkeypatch):
    calls = []

    async def fake_refresh(self, *, force=False):
        calls.append(force)
        return {"ok": True, "updated": True, "status": {"entries": 2}}

    monkeypatch.setattr(TagDatabase, "refresh", fake_refresh)
    client = TestClient(app_with_tags)

    resp = client.post("/api/tags/refresh?force=true")

    assert resp.status_code == 200
    assert resp.json()["updated"] is True
    assert calls == [True]
