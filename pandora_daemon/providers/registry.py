from __future__ import annotations

from collections.abc import Callable, Mapping
from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules

from pandora_daemon.providers.contracts import GalleryProvider, ProviderContext


ProviderFactory = Callable[[ProviderContext], GalleryProvider]

_BUILTIN_PROVIDER_PACKAGE = "pandora_daemon.providers"


def _normalize_provider_id(provider_id: str) -> str:
    normalized_id = provider_id.strip().lower()
    if not normalized_id:
        raise ValueError("provider_id must not be empty")
    return normalized_id


class ProviderRegistry:
    """Explicit provider-to-factory mapping; no plugin discovery or state."""

    def __init__(
        self,
        factories: Mapping[str, ProviderFactory] | None = None,
        default_provider_id: str | None = None,
    ) -> None:
        registry: dict[str, ProviderFactory] = {}
        self._factories = registry
        for provider_id, factory in (factories or {}).items():
            self.register(provider_id, factory)
        self._default_provider_id = (
            _normalize_provider_id(default_provider_id)
            if default_provider_id is not None
            else None
        )

    def register(self, provider_id: str, factory: ProviderFactory) -> None:
        normalized_id = _normalize_provider_id(provider_id)
        if normalized_id in self._factories:
            raise ValueError(f"Provider already registered: {normalized_id}")
        self._factories[normalized_id] = factory

    def create(self, provider_id: str, context: ProviderContext) -> GalleryProvider:
        normalized_id = _normalize_provider_id(provider_id)
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

    @property
    def default_provider_id(self) -> str | None:
        return self._default_provider_id


def _load_factory(target: str) -> ProviderFactory:
    module_name, separator, attribute_name = target.partition(":")
    if not separator:
        raise ValueError(f"Invalid provider factory target: {target}")

    def load(context: ProviderContext) -> GalleryProvider:
        module = import_module(module_name)
        factory = getattr(module, attribute_name)
        return factory(context)

    return load


def _builtin_provider_targets() -> dict[str, str]:
    providers_path = Path(__file__).parent
    targets: dict[str, str] = {}
    for module_info in iter_modules([str(providers_path)]):
        if not module_info.ispkg:
            continue
        package = import_module(f"{_BUILTIN_PROVIDER_PACKAGE}.{module_info.name}")
        provider_id = getattr(package, "PROVIDER_ID", None)
        factory_target = getattr(package, "FACTORY_TARGET", None)
        if provider_id is None or factory_target is None:
            continue
        normalized_id = _normalize_provider_id(provider_id)
        if normalized_id in targets:
            raise ValueError(f"Provider already registered: {normalized_id}")
        targets[normalized_id] = factory_target
    return targets


def default_provider_registry() -> ProviderRegistry:
    targets = _builtin_provider_targets()
    provider_ids = sorted(targets)
    if not provider_ids:
        raise ValueError("No built-in providers registered")
    return ProviderRegistry(
        {provider_id: _load_factory(targets[provider_id]) for provider_id in provider_ids},
        default_provider_id=provider_ids[0],
    )
