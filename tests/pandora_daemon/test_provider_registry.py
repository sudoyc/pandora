from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import pandora_daemon.providers.registry as registry_module
from pandora_daemon.providers.contracts import ProviderContext
from pandora_daemon.providers.registry import ProviderRegistry, default_provider_registry


def _context() -> ProviderContext:
    return ProviderContext(
        credentials={"session": "cookie"},
        proxy="http://proxy.test:8080",
        timeout=17,
    )


def test_provider_ids_and_default_are_normalized() -> None:
    registry = ProviderRegistry(
        {" Zulu ": MagicMock(), " alpha ": MagicMock()},
        default_provider_id=" ZULU ",
    )

    assert registry.provider_ids == ("alpha", "zulu")
    assert registry.default_provider_id == "zulu"


def test_register_and_create_normalize_ids_and_forward_context() -> None:
    context = _context()
    provider = MagicMock()
    provider.provider_id = "fixture"
    factory = MagicMock(return_value=provider)
    registry = ProviderRegistry()
    registry.register(" Fixture ", factory)

    assert registry.create(" FIXTURE ", context) is provider
    factory.assert_called_once_with(context)


def test_register_rejects_normalized_duplicate_ids() -> None:
    registry = ProviderRegistry({"fixture": MagicMock()})

    with pytest.raises(ValueError, match="Provider already registered: fixture"):
        registry.register(" Fixture ", MagicMock())


@pytest.mark.parametrize("operation", ("register", "create", "default"))
@pytest.mark.parametrize(
    "provider_id",
    ("", " \t ", ".", "..", "../escape", "nested/provider", r"nested\provider", "bad id"),
)
def test_registry_rejects_unsafe_ids(operation: str, provider_id: str) -> None:
    with pytest.raises(ValueError, match="safe path component"):
        if operation == "register":
            ProviderRegistry().register(provider_id, MagicMock())
        elif operation == "create":
            ProviderRegistry().create(provider_id, _context())
        else:
            ProviderRegistry(default_provider_id=provider_id)


def test_create_rejects_unknown_ids_and_lists_sorted_available_ids() -> None:
    registry = ProviderRegistry(
        {"zulu": MagicMock(), "alpha": MagicMock()},
        default_provider_id="alpha",
    )

    with pytest.raises(
        ValueError,
        match=r"Unknown provider 'missing'; available providers: alpha, zulu",
    ):
        registry.create("missing", _context())


def test_create_rejects_factory_identity_mismatch() -> None:
    provider = MagicMock()
    provider.provider_id = "unexpected"
    registry = ProviderRegistry({"expected": MagicMock(return_value=provider)})

    with pytest.raises(
        ValueError,
        match="identity mismatch: registered 'expected', returned 'unexpected'",
    ):
        registry.create("expected", _context())


def test_create_rejects_factory_without_a_valid_provider_id() -> None:
    provider = MagicMock(spec=[])
    registry = ProviderRegistry({"fixture": MagicMock(return_value=provider)})

    with pytest.raises(ValueError, match="returned an invalid provider_id"):
        registry.create("fixture", _context())


def test_default_provider_must_be_registered() -> None:
    with pytest.raises(ValueError, match="Default provider is not registered: missing"):
        ProviderRegistry({"fixture": MagicMock()}, default_provider_id="missing")


def test_default_registry_discovers_builtin_package_and_loads_factory(monkeypatch) -> None:
    context = _context()
    provider = MagicMock()
    provider.provider_id = "fixture"
    factory = MagicMock(return_value=provider)
    builtin = SimpleNamespace(
        PROVIDER_ID="fixture",
        FACTORY_TARGET="fixture.adapter:create_provider",
    )
    adapter = SimpleNamespace(create_provider=factory)
    import_module = MagicMock(side_effect=(builtin, adapter))
    monkeypatch.setattr(
        registry_module,
        "iter_modules",
        lambda _paths: (SimpleNamespace(ispkg=True, name="fixture"),),
    )
    monkeypatch.setattr(registry_module, "import_module", import_module)

    registry = default_provider_registry()

    assert registry.provider_ids == ("fixture",)
    assert registry.default_provider_id == "fixture"
    assert registry.create("fixture", context) is provider
    assert import_module.call_args_list == [
        (("pandora_daemon.providers.fixture",),),
        (("fixture.adapter",),),
    ]
    factory.assert_called_once_with(context)
