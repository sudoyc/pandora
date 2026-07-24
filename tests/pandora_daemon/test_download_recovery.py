from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

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


def _write_library_gallery(root: Path, gid: str, *, pages: int) -> Path:
    gallery_dir = root / f"{gid}-Gallery"
    gallery_dir.mkdir(parents=True)
    (gallery_dir / "metadata.json").write_text(
        json.dumps({
            "gid": gid,
            "token": f"token-{gid}",
            "title": f"Gallery {gid}",
            "pages": pages,
            "downloaded_at": "2026-07-24T00:00:00+00:00",
        }),
        encoding="utf-8",
    )
    pages_dir = gallery_dir / "pages"
    pages_dir.mkdir()
    for page in range(1, pages + 1):
        (pages_dir / f"{page:04d}.jpg").write_bytes(f"page-{page}".encode())
    return gallery_dir


def _snapshot(root: Path) -> list[tuple[str, str, bytes | None]]:
    if not root.exists():
        return []
    return [
        (
            str(path.relative_to(root)),
            "dir" if path.is_dir() else "file",
            None if path.is_dir() else path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
    ]


@pytest.mark.asyncio
async def test_repair_preview_plans_registration_without_writing_state_or_library(tmp_path):
    manager = _manager(tmp_path)
    library_root = tmp_path / "downloads"
    _write_library_gallery(library_root, "105", pages=2)
    before = _snapshot(library_root)

    result = await manager.repair("105", apply=False)

    assert result == {
        "operation": "repair",
        "gid": "105",
        "apply": False,
        "changed": False,
        "actions": [{
            "code": "register_library_task",
            "gid": "105",
            "task_status": "completed",
            "expected_pages": 2,
            "present_pages": 2,
        }],
    }
    assert manager.status() == []
    assert not manager._state_file.exists()
    assert _snapshot(library_root) == before


@pytest.mark.asyncio
async def test_repair_apply_is_persisted_idempotent_and_does_not_change_library(tmp_path):
    manager = _manager(tmp_path)
    library_root = tmp_path / "downloads"
    _write_library_gallery(library_root, "105", pages=2)
    before = _snapshot(library_root)

    result = await manager.repair("105", apply=True)

    assert result["apply"] is True
    assert result["changed"] is True
    assert result["actions"][0]["code"] == "register_library_task"
    task = manager.status()[0]
    assert task.gid == "105"
    assert task.status == "completed"
    assert task.downloaded_pages == 2
    assert task.page_states == {1: "done", 2: "done"}
    assert task.metadata_saved is True
    assert manager.consistency_report()["consistent"] is True
    persisted = json.loads(manager._state_file.read_text(encoding="utf-8"))
    assert set(persisted["tasks"]) == {"105"}
    assert _snapshot(library_root) == before
    assert "token-105" not in json.dumps(result)
    assert str(tmp_path) not in json.dumps(result)
    reloaded = _manager(tmp_path)
    reloaded._load_state()
    assert reloaded.status()[0].page_states == {1: "done", 2: "done"}

    state_after_first_apply = manager._state_file.read_bytes()
    second = await manager.repair("105", apply=True)

    assert second == {
        "operation": "repair",
        "gid": "105",
        "apply": True,
        "changed": False,
        "actions": [],
    }
    assert manager._state_file.read_bytes() == state_after_first_apply
    assert _snapshot(library_root) == before


@pytest.mark.asyncio
async def test_repair_rejects_incomplete_library_without_changing_files(tmp_path):
    manager = _manager(tmp_path)
    library_root = tmp_path / "downloads"
    gallery_dir = _write_library_gallery(library_root, "105", pages=2)
    (gallery_dir / "pages" / "0002.jpg").unlink()
    before = _snapshot(library_root)

    with pytest.raises(ValueError, match="missing pages"):
        await manager.repair("105", apply=True)

    assert manager.status() == []
    assert not manager._state_file.exists()
    assert _snapshot(library_root) == before


@pytest.mark.asyncio
async def test_repair_rejects_ambiguous_library_entries(tmp_path):
    manager = _manager(tmp_path)
    library_root = tmp_path / "downloads"
    _write_library_gallery(library_root, "105", pages=1)
    duplicate = _write_library_gallery(library_root, "106", pages=1)
    metadata_path = duplicate / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["gid"] = "105"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    before = _snapshot(library_root)

    with pytest.raises(ValueError, match="Multiple library entries"):
        await manager.repair("105", apply=True)

    assert manager.status() == []
    assert not manager._state_file.exists()
    assert _snapshot(library_root) == before


@pytest.mark.asyncio
async def test_forget_preview_and_apply_are_idempotent_and_preserve_library(tmp_path):
    manager = _manager(tmp_path)
    library_root = tmp_path / "downloads"
    gallery_dir = _write_library_gallery(library_root, "105", pages=2)
    manager._tasks["105"] = DownloadTask(
        gid="105",
        token="token-105",
        title="Gallery 105",
        total_pages=2,
        output_dir=str(gallery_dir),
        status="completed",
    )
    manager._save_state()
    before = _snapshot(library_root)
    state_before = manager._state_file.read_bytes()

    preview = await manager.forget("105", apply=False)

    assert preview == {
        "operation": "forget",
        "gid": "105",
        "apply": False,
        "changed": False,
        "actions": [{
            "code": "forget_task",
            "gid": "105",
            "task_status": "completed",
        }],
    }
    assert manager._state_file.read_bytes() == state_before
    assert set(task.gid for task in manager.status()) == {"105"}
    assert _snapshot(library_root) == before

    applied = await manager.forget("105", apply=True)

    assert applied["changed"] is True
    assert manager.status() == []
    persisted = json.loads(manager._state_file.read_text(encoding="utf-8"))
    assert persisted["tasks"] == {}
    assert _snapshot(library_root) == before
    state_after_first_apply = manager._state_file.read_bytes()

    second = await manager.forget("105", apply=True)

    assert second == {
        "operation": "forget",
        "gid": "105",
        "apply": True,
        "changed": False,
        "actions": [],
    }
    assert manager._state_file.read_bytes() == state_after_first_apply
    assert _snapshot(library_root) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["queued", "downloading"])
async def test_forget_rejects_active_task(tmp_path, status):
    manager = _manager(tmp_path)
    manager._tasks["105"] = DownloadTask(
        gid="105",
        token="token-105",
        title="Gallery 105",
        total_pages=2,
        output_dir=str(tmp_path / "downloads" / "105-Gallery"),
        status=status,
    )

    with pytest.raises(ValueError, match="active task"):
        await manager.forget("105", apply=True)

    assert set(task.gid for task in manager.status()) == {"105"}
    assert not manager._state_file.exists()
