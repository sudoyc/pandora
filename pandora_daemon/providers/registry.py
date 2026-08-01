from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module

from pandora_daemon.providers.contracts import GalleryProvider, ProviderContext


ProviderFactory = Callable[[ProviderContext], GalleryProvider]
_PROVIDERS: dict[str, str] = {
    "exhentai": "pandora_daemon.providers.exhentai.adapter:create_provider",
}


class ProviderRegistry:
    """Explicit provider-to-factory mapping; no plugin discovery or state."""

    def __init__(self, factories: Mapping[str, ProviderFactory] | None = None) -> None:
        self._factories = dict(factories or {})

    def register(self, provider_id: str, factory: ProviderFactory) -> None:
        normalized_id = provider_id.strip().lower()
        if not normalized_id:
            raise ValueError("provider_id must not be empty")
        if normalized_id in self._factories:
            raise ValueError(f"Provider already registered: {normalized_id}")
        self._factories[normalized_id] = factory

    def create(self, provider_id: str, context: ProviderContext) -> GalleryProvider:
        normalized_id = provider_id.strip().lower()
        try:
            factory = self._factories[normalized_id]
        except KeyError as exc:
            available = ", ".join(sorted(self._factories)) or "none"
            raise ValueError(
                f"Unknown provider {normalized_id!r}; available providers: {available}"
            ) from exc
        return factory(context)

    @property
    def provider_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))


def _load_factory(target: str) -> ProviderFactory:
    module_name, separator, attribute_name = target.partition(":")
    if not separator:
        raise ValueError(f"Invalid provider factory target: {target}")

    def load(context: ProviderContext) -> GalleryProvider:
        module = import_module(module_name)
        factory = getattr(module, attribute_name)
        return factory(context)

    return load


def default_provider_registry() -> ProviderRegistry:
    return ProviderRegistry(
        {
            provider_id: _load_factory(target)
            for provider_id, target in _PROVIDERS.items()
        }
    )
