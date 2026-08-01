from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import pandora_daemon.providers.registry as registry_module
from pandora_daemon.providers.contracts import ProviderContext
from pandora_daemon.providers.registry import ProviderRegistry, default_provider_registry


def _context() -> ProviderContext:
    return ProviderContext(
        credentials={"igneous": "cookie", "ipb_member_id": "member"},
        proxy="http://proxy.test:8080",
        timeout=17,
    )


def test_provider_ids_are_normalized_and_sorted() -> None:
    registry = ProviderRegistry()

    registry.register("Zulu", MagicMock())
    registry.register(" alpha ", MagicMock())

    assert registry.provider_ids == ("alpha", "zulu")


def test_create_calls_the_registered_factory_with_its_context() -> None:
    context = _context()
    provider = MagicMock()
    factory = MagicMock(return_value=provider)
    registry = ProviderRegistry()
    registry.register("fixture", factory)

    assert registry.create(" FIXTURE ", context) is provider
    factory.assert_called_once_with(context)


def test_register_rejects_normalized_duplicate_ids() -> None:
    registry = ProviderRegistry()
    registry.register("fixture", MagicMock())

    with pytest.raises(ValueError, match="Provider already registered: fixture"):
        registry.register(" Fixture ", MagicMock())


@pytest.mark.parametrize("provider_id", ("", " \t "))
def test_register_rejects_empty_ids(provider_id: str) -> None:
    with pytest.raises(ValueError, match="provider_id must not be empty"):
        ProviderRegistry().register(provider_id, MagicMock())


def test_create_rejects_unknown_ids_and_lists_sorted_available_ids() -> None:
    registry = ProviderRegistry()
    registry.register("zulu", MagicMock())
    registry.register("alpha", MagicMock())

    with pytest.raises(
        ValueError,
        match=r"Unknown provider 'missing'; available providers: alpha, zulu",
    ):
        registry.create("missing", _context())


def test_default_registry_uses_the_declared_factory_mapping(monkeypatch) -> None:
    context = _context()
    provider = MagicMock()
    factory = MagicMock(return_value=provider)
    import_module = MagicMock(return_value=SimpleNamespace(create_provider=factory))
    monkeypatch.setattr(registry_module, "import_module", import_module)

    registry = default_provider_registry()

    assert registry.provider_ids == ("exhentai",)
    assert registry.create("exhentai", context) is provider
    import_module.assert_called_once_with("pandora_daemon.providers.exhentai.adapter")
    factory.assert_called_once_with(context)
