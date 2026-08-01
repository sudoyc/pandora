from pathlib import Path

import pytest

from pandora_daemon.workspace import ProviderWorkspace


def test_default_provider_keeps_legacy_paths(tmp_path: Path) -> None:
    workspace = ProviderWorkspace.for_provider(
        tmp_path / "config",
        tmp_path / "library",
        " Default ",
        legacy_provider_id="default",
    )

    assert workspace.provider_id == "default"
    assert workspace.database_path == tmp_path / "config" / "pandora.db"
    assert workspace.state_file == tmp_path / "config" / "downloads.json"
    assert workspace.library_path == tmp_path / "library"


def test_alternate_provider_uses_isolated_paths(tmp_path: Path) -> None:
    workspace = ProviderWorkspace.for_provider(
        tmp_path / "config",
        tmp_path / "library",
        " Fixture ",
        legacy_provider_id="default",
    )

    provider_dir = tmp_path / "config" / "providers" / "fixture"
    assert workspace.provider_id == "fixture"
    assert workspace.database_path == provider_dir / "pandora.db"
    assert workspace.state_file == provider_dir / "downloads.json"
    assert workspace.library_path == tmp_path / "library" / "fixture"


def test_provider_is_isolated_when_there_is_no_legacy_default(tmp_path: Path) -> None:
    workspace = ProviderWorkspace.for_provider(
        tmp_path / "config",
        tmp_path / "library",
        "fixture",
        legacy_provider_id=None,
    )

    assert workspace.database_path.parent == tmp_path / "config" / "providers" / "fixture"
    assert workspace.library_path == tmp_path / "library" / "fixture"


@pytest.mark.parametrize(
    "provider_id",
    ("", "  ", ".", "..", "../escape", "nested/provider", r"nested\provider", "bad id"),
)
def test_provider_id_must_be_a_safe_path_component(
    tmp_path: Path,
    provider_id: str,
) -> None:
    with pytest.raises(ValueError, match="safe path component"):
        ProviderWorkspace.for_provider(
            tmp_path / "config",
            tmp_path / "library",
            provider_id,
            legacy_provider_id="default",
        )
