from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

from scripts.release import (
    check_release_metadata,
    expected_tag,
    project_version,
    verify_artifacts,
)


ROOT = Path(__file__).resolve().parents[2]


def _write_release_metadata(
    root: Path,
    *,
    version: str = "1.2.3",
    lock_version: str | None = None,
    changelog_version: str | None = None,
) -> None:
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "pandora"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(
        "version = 1\n"
        "[[package]]\n"
        'name = "pandora"\n'
        f'version = "{lock_version or version}"\n'
        'source = { editable = "." }\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n"
        f"## [{changelog_version or version}] - 2026-07-25\n",
        encoding="utf-8",
    )


def _add_tar_bytes(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    archive.addfile(info, io.BytesIO(content))


def _write_artifacts(
    dist_dir: Path,
    version: str,
    *,
    metadata_version: str | None = None,
    extra_sdist_members: tuple[str, ...] = (),
) -> None:
    wheel = dist_dir / f"pandora-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("exhentai_api/__init__.py", "")
        archive.writestr("pandora_daemon/__init__.py", "")
        archive.writestr(
            f"pandora-{version}.dist-info/METADATA",
            "Metadata-Version: 2.4\n"
            "Name: pandora\n"
            f"Version: {metadata_version or version}\n",
        )
        archive.writestr(
            f"pandora-{version}.dist-info/entry_points.txt",
            "[console_scripts]\n"
            "pandora = pandora_daemon.cli:main\n"
            "pandora-daemon = pandora_daemon.__main__:main\n",
        )

    root = f"pandora-{version}"
    with tarfile.open(dist_dir / f"pandora-{version}.tar.gz", "w:gz") as archive:
        _add_tar_bytes(archive, f"{root}/README.md", b"# Pandora\n")
        _add_tar_bytes(archive, f"{root}/CHANGELOG.md", b"# Changelog\n")
        _add_tar_bytes(archive, f"{root}/pyproject.toml", b"[project]\n")
        _add_tar_bytes(archive, f"{root}/exhentai_api/__init__.py", b"")
        _add_tar_bytes(archive, f"{root}/pandora_daemon/__init__.py", b"")
        _add_tar_bytes(
            archive,
            f"{root}/PKG-INFO",
            (
                "Metadata-Version: 2.4\n"
                "Name: pandora\n"
                f"Version: {metadata_version or version}\n"
            ).encode(),
        )
        for extra_sdist_member in extra_sdist_members:
            _add_tar_bytes(archive, f"{root}/{extra_sdist_member}", b"unexpected")


def test_current_repository_release_metadata_is_consistent():
    version = project_version(ROOT)

    assert expected_tag(version) == f"v{version}"
    assert check_release_metadata(ROOT, proposed_tag=expected_tag(version)) == []


def test_release_metadata_reports_lock_changelog_and_tag_mismatches(tmp_path):
    _write_release_metadata(
        tmp_path,
        version="1.2.3",
        lock_version="1.2.2",
        changelog_version="1.2.1",
    )

    errors = check_release_metadata(tmp_path, proposed_tag="v1.2.0")

    assert any("uv.lock" in error and "1.2.2" in error for error in errors)
    assert any("CHANGELOG.md" in error and "1.2.3" in error for error in errors)
    assert any("v1.2.3" in error and "v1.2.0" in error for error in errors)


def test_artifact_verifier_accepts_minimal_release_artifacts(tmp_path):
    _write_artifacts(tmp_path, "1.2.3")
    (tmp_path / ".gitignore").write_text("*\n", encoding="utf-8")

    assert verify_artifacts(tmp_path, "1.2.3") == []


def test_artifact_verifier_rejects_wrong_metadata_and_unexpected_sdist_content(tmp_path):
    _write_artifacts(
        tmp_path,
        "1.2.3",
        metadata_version="1.2.2",
        extra_sdist_members=(
            "pandora-web/node_modules/package/index.js",
            "pandora_daemon/credentials.txt",
        ),
    )
    (tmp_path / "unexpected-directory").mkdir()

    errors = verify_artifacts(tmp_path, "1.2.3")

    assert sum("metadata version" in error for error in errors) == 2
    assert any("pandora-web/node_modules" in error for error in errors)
    assert any("pandora_daemon/credentials.txt" in error for error in errors)
    assert any("unexpected-directory" in error for error in errors)
