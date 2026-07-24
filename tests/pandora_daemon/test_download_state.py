from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from pandora_daemon import download
from pandora_daemon.config import DownloadConfig
from pandora_daemon.download import DownloadManager, DownloadTask


def _manager(tmp_path: Path) -> DownloadManager:
    return DownloadManager(
        AsyncMock(),
        DownloadConfig(path=str(tmp_path / "downloads")),
        AsyncMock(),
        AsyncMock(),
        tmp_path / "downloads.json",
    )


def _task(gid: str = "123") -> DownloadTask:
    return DownloadTask(
        gid=gid,
        token=f"token-{gid}",
        title=f"Gallery {gid}",
        total_pages=2,
        output_dir=f"/downloads/{gid}-Gallery",
        status="completed",
        page_states={1: "done", 2: "failed"},
    )


def test_save_state_uses_versioned_envelope_and_atomic_replace(tmp_path):
    manager = _manager(tmp_path)
    manager._tasks["123"] = _task()

    manager._save_state()

    data = json.loads(manager._state_file.read_text(encoding="utf-8"))
    assert getattr(download, "DOWNLOAD_STATE_SCHEMA_VERSION", None) == 1
    assert set(data) == {"schema_version", "tasks"}
    assert data["schema_version"] == 1
    assert data["tasks"]["123"]["gid"] == "123"
    assert not manager._state_file.with_suffix(".json.tmp").exists()


def test_load_state_migrates_unversioned_legacy_mapping(tmp_path):
    manager = _manager(tmp_path)
    manager._state_file.write_text(
        json.dumps({"123": _task().to_dict()}),
        encoding="utf-8",
    )

    manager._load_state()

    assert manager._tasks["123"].page_states == {1: "done", 2: "failed"}
    migrated = json.loads(manager._state_file.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == 1
    assert migrated["tasks"]["123"]["gid"] == "123"
    assert not manager._state_file.with_suffix(".json.tmp").exists()
    assert list(tmp_path.glob("downloads.json.corrupt*")) == []


@pytest.mark.asyncio
async def test_load_state_rejects_unknown_version_without_modifying_file(tmp_path):
    manager = _manager(tmp_path)
    original = b'{"schema_version":99,"tasks":{}}'
    manager._state_file.write_bytes(original)

    with pytest.raises(download.UnsupportedDownloadStateVersion, match="schema version 99"):
        await manager.start()

    assert manager._state_file.read_bytes() == original
    assert manager._workers == []
    assert not manager._state_file.with_suffix(".json.tmp").exists()
    assert list(tmp_path.glob("downloads.json.corrupt*")) == []


@pytest.mark.parametrize(
    "original",
    [
        b'{"schema_version":1,"tasks":',
        b"\xff",
        b'{"schema_version":1,"tasks":[]}',
    ],
    ids=["truncated", "non-utf8", "invalid-envelope"],
)
def test_load_state_backs_up_and_recovers_corrupt_file(tmp_path, original):
    manager = _manager(tmp_path)
    manager._state_file.write_bytes(original)

    manager._load_state()

    assert manager._tasks == {}
    assert json.loads(manager._state_file.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "tasks": {},
    }
    backups = list(tmp_path.glob("downloads.json.corrupt*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original
    assert not manager._state_file.with_suffix(".json.tmp").exists()


def test_load_state_recovers_valid_tasks_when_one_entry_is_corrupt(tmp_path):
    manager = _manager(tmp_path)
    original = json.dumps({
        "schema_version": 1,
        "tasks": {
            "123": _task().to_dict(),
            "broken": {"gid": "broken"},
        },
    }).encode()
    manager._state_file.write_bytes(original)

    manager._load_state()

    assert set(manager._tasks) == {"123"}
    recovered = json.loads(manager._state_file.read_text(encoding="utf-8"))
    assert set(recovered["tasks"]) == {"123"}
    backups = list(tmp_path.glob("downloads.json.corrupt*"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == original
