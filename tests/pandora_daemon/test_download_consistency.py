from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

from pandora_daemon.config import DownloadConfig
from pandora_daemon.download import DownloadManager, DownloadTask


def _task(download_path: Path, gid: str, *, status: str, pages: int) -> DownloadTask:
    return DownloadTask(
        gid=gid,
        token=f"token-{gid}",
        title=f"Gallery {gid}",
        total_pages=pages,
        output_dir=str(download_path / f"{gid}-Gallery"),
        status=status,
    )


def _write_metadata(gallery_dir: Path, gid: str, pages: int) -> None:
    gallery_dir.mkdir(parents=True, exist_ok=True)
    (gallery_dir / "metadata.json").write_text(
        json.dumps({"gid": gid, "title": f"Gallery {gid}", "pages": pages}),
        encoding="utf-8",
    )


def _write_pages(gallery_dir: Path, *pages: int) -> None:
    pages_dir = gallery_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for page in pages:
        (pages_dir / f"{page:04d}.jpg").write_bytes(f"page-{page}".encode())


def _snapshot(root: Path) -> list[tuple[str, str, bytes | None]]:
    snapshot = []
    for path in sorted(root.rglob("*")):
        snapshot.append(
            (
                str(path.relative_to(root)),
                "dir" if path.is_dir() else "file",
                None if path.is_dir() else path.read_bytes(),
            )
        )
    return snapshot


def test_consistency_report_covers_state_and_library_fixture_matrix(tmp_path):
    download_path = tmp_path / "downloads"
    state_file = tmp_path / "downloads.json"
    tasks = {
        task.gid: task
        for task in (
            _task(download_path, "101", status="completed", pages=2),
            _task(download_path, "102", status="completed", pages=3),
            _task(download_path, "103", status="completed", pages=2),
            _task(download_path, "104", status="completed", pages=1),
            _task(download_path, "106", status="queued", pages=2),
            _task(download_path, "107", status="completed", pages=1),
        )
    }
    state_file.write_text(
        json.dumps({gid: task.to_dict() for gid, task in tasks.items()}),
        encoding="utf-8",
    )

    missing_page_dir = download_path / "102-Gallery"
    _write_metadata(missing_page_dir, "102", 3)
    _write_pages(missing_page_dir, 1, 3)

    missing_metadata_dir = download_path / "103-Gallery"
    missing_metadata_dir.mkdir(parents=True)
    _write_pages(missing_metadata_dir, 1, 2)

    invalid_metadata_dir = download_path / "104-Gallery"
    invalid_metadata_dir.mkdir(parents=True)
    (invalid_metadata_dir / "metadata.json").write_bytes(b"\xff")
    _write_pages(invalid_metadata_dir, 1)

    unregistered_dir = download_path / "105-Gallery"
    _write_metadata(unregistered_dir, "105", 2)
    _write_pages(unregistered_dir, 1, 2)

    consistent_dir = download_path / "107-Gallery"
    _write_metadata(consistent_dir, "107", 1)
    _write_pages(consistent_dir, 1)

    manager = DownloadManager(
        AsyncMock(),
        DownloadConfig(path=str(download_path)),
        AsyncMock(),
        AsyncMock(),
        state_file,
    )
    manager._load_state()
    before = _snapshot(tmp_path)

    report = manager.consistency_report()

    assert report == {
        "consistent": False,
        "summary": {
            "registered_tasks": 6,
            "terminal_tasks": 5,
            "library_entries": 3,
            "affected_galleries": 5,
            "issue_count": 5,
        },
        "issues": [
            {
                "code": "orphan_task",
                "gid": "101",
                "task_status": "completed",
                "expected_pages": 2,
                "present_pages": 0,
                "missing_pages": [],
            },
            {
                "code": "missing_pages",
                "gid": "102",
                "task_status": "completed",
                "expected_pages": 3,
                "present_pages": 2,
                "missing_pages": [2],
            },
            {
                "code": "missing_metadata",
                "gid": "103",
                "task_status": "completed",
                "expected_pages": 2,
                "present_pages": 2,
                "missing_pages": [],
            },
            {
                "code": "invalid_metadata",
                "gid": "104",
                "task_status": "completed",
                "expected_pages": 1,
                "present_pages": 1,
                "missing_pages": [],
            },
            {
                "code": "unregistered_library",
                "gid": "105",
                "task_status": None,
                "expected_pages": 2,
                "present_pages": 2,
                "missing_pages": [],
            },
        ],
    }
    serialized = json.dumps(report)
    assert "token-" not in serialized
    assert str(tmp_path) not in serialized
    assert _snapshot(tmp_path) == before


def test_consistency_report_is_consistent_without_tasks_or_library(tmp_path):
    manager = DownloadManager(
        AsyncMock(),
        DownloadConfig(path=str(tmp_path / "downloads")),
        AsyncMock(),
        AsyncMock(),
        tmp_path / "downloads.json",
    )

    assert manager.consistency_report() == {
        "consistent": True,
        "summary": {
            "registered_tasks": 0,
            "terminal_tasks": 0,
            "library_entries": 0,
            "affected_galleries": 0,
            "issue_count": 0,
        },
        "issues": [],
    }


def test_consistency_report_marks_task_outside_current_library_as_orphan(tmp_path):
    download_path = tmp_path / "current-downloads"
    old_gallery_dir = tmp_path / "old-downloads" / "201-Gallery"
    _write_metadata(old_gallery_dir, "201", 1)
    _write_pages(old_gallery_dir, 1)
    manager = DownloadManager(
        AsyncMock(),
        DownloadConfig(path=str(download_path)),
        AsyncMock(),
        AsyncMock(),
        tmp_path / "downloads.json",
    )
    manager._tasks["201"] = DownloadTask(
        gid="201",
        token="token-201",
        title="Gallery 201",
        total_pages=1,
        output_dir=str(old_gallery_dir),
        status="completed",
    )

    report = manager.consistency_report()

    assert report["issues"] == [
        {
            "code": "orphan_task",
            "gid": "201",
            "task_status": "completed",
            "expected_pages": 1,
            "present_pages": 0,
            "missing_pages": [],
        }
    ]
