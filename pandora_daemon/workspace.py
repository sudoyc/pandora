"""Deterministic filesystem boundaries for one active gallery provider."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ProviderWorkspace:
    """Persistent paths owned by one selected provider instance."""

    provider_id: str
    database_path: Path
    state_file: Path
    library_path: Path

    @classmethod
    def for_provider(
        cls,
        config_dir: Path | str,
        library_root: Path | str,
        provider_id: str,
        *,
        legacy_provider_id: str | None,
    ) -> "ProviderWorkspace":
        normalized_id = _validate_provider_id(provider_id)
        config_dir = Path(config_dir).expanduser()
        library_root = Path(library_root).expanduser()
        if legacy_provider_id is not None and normalized_id == _validate_provider_id(
            legacy_provider_id
        ):
            return cls(
                provider_id=normalized_id,
                database_path=config_dir / "pandora.db",
                state_file=config_dir / "downloads.json",
                library_path=library_root,
            )

        provider_dir = config_dir / "providers" / normalized_id
        return cls(
            provider_id=normalized_id,
            database_path=provider_dir / "pandora.db",
            state_file=provider_dir / "downloads.json",
            library_path=library_root / normalized_id,
        )


def _validate_provider_id(provider_id: str) -> str:
    normalized_id = provider_id.strip().lower()
    if not normalized_id or normalized_id in {".", ".."}:
        raise ValueError("provider_id must be a non-empty safe path component")
    if any(separator in normalized_id for separator in ("/", "\\")):
        raise ValueError("provider_id must be a non-empty safe path component")
    if any(not (character.isalnum() or character in "._-") for character in normalized_id):
        raise ValueError("provider_id must be a non-empty safe path component")
    return normalized_id
