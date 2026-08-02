from __future__ import annotations

import textwrap
from pathlib import Path

from scripts.architecture_benchmark import WEIGHTS, score
from scripts.architecture_metrics import collect_static_metrics
from scripts.provider_swap_workload import run_provider_swap_workload


STATIC_METRIC_KEYS = frozenset(
    {
        "provider_import_edges",
        "provider_symbol_leaks",
        "concrete_provider_state_fields",
        "provider_factory_calls",
        "uncontracted_provider_calls",
        "adapter_surface_leaks",
        "untyped_provider_dependencies",
        "missing_provider_contract",
        "missing_provider_registry",
        "top_level_provider_packages",
        "packaging_provider_leaks",
        "route_module_naming_violations",
        "product_naming_violations",
        "architecture_doc_contradictions",
    }
)
WORKLOAD_METRIC_KEYS = frozenset(
    {
        "swap_endpoints_passed",
        "swap_workload_failures",
        "swap_contract_leaks",
        "provider_registry_failures",
        "workspace_isolation_failures",
    }
)
PENALTY_METRIC_KEYS = STATIC_METRIC_KEYS | {
    "swap_workload_failures",
    "swap_contract_leaks",
    "provider_registry_failures",
    "workspace_isolation_failures",
}


def _write_fixture(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _write_coupled_repository(root: Path) -> None:
    fixture = {
        "pyproject.toml": """
            [project]
            name = "pandora-fixture"
            version = "0.0.0"

            [tool.hatch.build.targets.wheel]
            packages = ["pandora_daemon", "exhentai_api"]
        """,
        "exhentai_api/__init__.py": "",
        "exhentai_api/api.py": """
            class ExhentaiAPI:
                pass
        """,
        "pandora_daemon/__init__.py": "",
        "pandora_daemon/providers/__init__.py": "",
        "pandora_daemon/providers/contracts.py": """
            from typing import Protocol


            class GalleryProvider(Protocol):
                async def get_homepage(self) -> list[object]: ...
        """,
        "pandora_daemon/providers/exhentai/__init__.py": "",
        "pandora_daemon/providers/exhentai/adapter.py": """
            class ExHentaiProvider:
                async def get_homepage(self):
                    return []

                @property
                def client(self):
                    return object()

                async def image_search(self):
                    return []
        """,
        "pandora_daemon/routes/gallery.py": """
            def Depends(dependency):
                return dependency


            def get_gallery_provider():
                return object()


            async def gallery(provider=Depends(get_gallery_provider)):
                return await provider.get_gallery_details("1", "token")
        """,
        "pandora_daemon/providers/registry.py": """
            from .contracts import GalleryProvider


            REGISTRY: dict[str, type[GalleryProvider]] = {}


            def get_gallery_provider(name: str) -> GalleryProvider:
                return REGISTRY[name]()
        """,
        "pandora_daemon/state.py": """
            from dataclasses import dataclass

            from exhentai_api.api import ExhentaiAPI


            @dataclass
            class AppState:
                api: ExhentaiAPI


            def build_state() -> AppState:
                return AppState(api=ExhentaiAPI())
        """,
        "pandora_daemon/routes/__init__.py": "",
        "pandora_daemon/routes/exhentai_routes.py": """
            from exhentai_api.api import ExhentaiAPI


            def homepage(api: ExhentaiAPI) -> None:
                del api
        """,
        "pandora_daemon/exhentai_service.py": """
            class ExhentaiService:
                pass
        """,
    }
    for relative_path, content in fixture.items():
        _write_fixture(root, relative_path, content)


def test_static_metrics_detect_coupling_without_missing_neutral_seams(tmp_path: Path):
    _write_coupled_repository(tmp_path)

    metrics = collect_static_metrics(tmp_path)

    assert set(metrics) == STATIC_METRIC_KEYS
    assert all(type(value) is int and value >= 0 for value in metrics.values())
    assert metrics == collect_static_metrics(tmp_path)

    for name in (
        "provider_import_edges",
        "provider_symbol_leaks",
        "concrete_provider_state_fields",
        "provider_factory_calls",
        "uncontracted_provider_calls",
        "top_level_provider_packages",
        "adapter_surface_leaks",
        "untyped_provider_dependencies",
        "packaging_provider_leaks",
        "route_module_naming_violations",
        "product_naming_violations",
    ):
        assert metrics[name] > 0, name

    assert metrics["missing_provider_contract"] == 0
    assert metrics["missing_provider_registry"] == 0


def test_uncontracted_provider_calls_compare_routes_with_protocol(tmp_path: Path):
    _write_fixture(
        tmp_path,
        "pandora_daemon/providers/contracts.py",
        """
        from typing import Protocol


        class GalleryProvider(Protocol):
            async def get_homepage(self) -> list[object]: ...
        """,
    )
    _write_fixture(
        tmp_path,
        "pandora_daemon/routes/browse.py",
        """
        async def homepage(provider):
            return await provider.get_homepage()


        async def archive(alternate_provider):
            return await alternate_provider.get_archive_list("1", "token")
        """,
    )

    metrics = collect_static_metrics(tmp_path)

    assert metrics["uncontracted_provider_calls"] == 1


def test_adapter_surface_and_provider_dependency_metrics_are_precise(tmp_path: Path):
    _write_fixture(
        tmp_path,
        "pandora_daemon/providers/contracts.py",
        """
        from typing import Protocol


        class GalleryProvider(Protocol):
            async def get_homepage(self) -> list[object]: ...
        """,
    )
    _write_fixture(
        tmp_path,
        "pandora_daemon/providers/fixture/adapter.py",
        """
        class FixtureProvider:
            async def get_homepage(self):
                return []

            async def extra_public_method(self):
                return None

            async def _private_helper(self):
                return None
        """,
    )
    _write_fixture(
        tmp_path,
        "pandora_daemon/routes/browse.py",
        """
        def Depends(dependency):
            return dependency


        def get_gallery_provider():
            return object()


        async def typed(provider: GalleryProvider = Depends(get_gallery_provider)):
            return await provider.get_homepage()


        async def untyped(provider=Depends(get_gallery_provider)):
            return await provider.get_homepage()
        """,
    )

    metrics = collect_static_metrics(tmp_path)

    assert metrics["adapter_surface_leaks"] == 1
    assert metrics["untyped_provider_dependencies"] == 1


def test_provider_specific_tag_catalog_is_a_generic_symbol_leak(tmp_path: Path):
    _write_fixture(
        tmp_path,
        "pandora_daemon/tag_database.py",
        '''
        SOURCE_URL = "https://example.invalid/EhTagTranslation/catalog.json"
        ''',
    )

    metrics = collect_static_metrics(tmp_path)

    assert metrics["provider_symbol_leaks"] == 1


def test_dependency_accessor_without_mapping_is_not_a_registry(tmp_path: Path):
    _write_fixture(
        tmp_path,
        "pandora_daemon/providers/contracts.py",
        """
        from typing import Protocol


        class GalleryProvider(Protocol):
            async def get_homepage(self) -> list[object]: ...
        """,
    )
    _write_fixture(
        tmp_path,
        "pandora_daemon/dependencies.py",
        """
        def get_gallery_provider():
            return object()
        """,
    )

    metrics = collect_static_metrics(tmp_path)

    assert metrics["missing_provider_contract"] == 0
    assert metrics["missing_provider_registry"] == 1


def test_provider_swap_workload_passes_every_required_endpoint():
    metrics = run_provider_swap_workload()

    assert set(metrics) == WORKLOAD_METRIC_KEYS
    assert all(type(value) is int and value >= 0 for value in metrics.values())
    assert metrics["swap_endpoints_passed"] == 26
    assert metrics["swap_workload_failures"] == 0
    assert metrics["workspace_isolation_failures"] == 0
    assert metrics["provider_registry_failures"] == 1

def test_score_weights_every_penalty_and_ignores_endpoint_successes():
    assert set(WEIGHTS) == PENALTY_METRIC_KEYS
    assert all(type(weight) is int and weight > 0 for weight in WEIGHTS.values())
    assert "swap_endpoints_passed" not in WEIGHTS

    metrics = {
        name: index
        for index, name in enumerate(sorted(PENALTY_METRIC_KEYS), start=1)
    }
    metrics["swap_endpoints_passed"] = 23
    expected = sum(WEIGHTS[name] * metrics[name] for name in WEIGHTS)

    assert score(metrics) == expected

    metrics["swap_endpoints_passed"] = 400
    assert score(metrics) == expected
