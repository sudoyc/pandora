"""Deterministic in-process workload for the gallery-provider seam."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Protocol
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.routes import browse


_FIXTURE_GID = "100001"
_FIXTURE_TOKEN = "provider-swap"
_FIXTURE_TITLE = "Provider swap fixture"
_PROVIDER_MARKERS = ("exhentai", "ehentai")
_ENDPOINTS = (
    ("/api/homepage", "get_homepage"),
    ("/api/search", "search"),
    ("/api/popular", "get_popular"),
    ("/api/watched", "get_watched"),
)


def _gallery_item() -> SimpleNamespace:
    """Return a neutral gallery record understood by the browse serializer."""
    return SimpleNamespace(
        gid=_FIXTURE_GID,
        token=_FIXTURE_TOKEN,
        title=_FIXTURE_TITLE,
        category="fixture",
        uploader="fixture",
        thumb_url="/fixture/thumbnail",
        posted="fixture",
        rating=0.0,
        pages=1,
        rated=False,
        thumb_width=1,
        thumb_height=1,
        url="/fixture/gallery",
    )


class FakeGalleryProvider:
    """Small provider double that records the route-to-provider contract."""

    def __init__(self) -> None:
        self.gallery = _gallery_item()
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(
        self, method: str, args: tuple[object, ...], kwargs: dict[str, object]
    ) -> None:
        self.calls.append((method, args, kwargs))

    async def get_homepage(
        self, *args: object, **kwargs: object
    ) -> list[SimpleNamespace]:
        self._record("get_homepage", args, kwargs)
        return [self.gallery]

    async def search(self, *args: object, **kwargs: object) -> list[SimpleNamespace]:
        self._record("search", args, kwargs)
        return [self.gallery]

    async def get_popular(
        self, *args: object, **kwargs: object
    ) -> list[SimpleNamespace]:
        self._record("get_popular", args, kwargs)
        return [self.gallery]

    async def get_watched(
        self, *args: object, **kwargs: object
    ) -> list[SimpleNamespace]:
        self._record("get_watched", args, kwargs)
        return [self.gallery]


def _provider_dependency() -> Callable[..., object]:
    """Find the dependency callable captured by the browse router."""
    provider_dependency = getattr(browse, "get_gallery_provider", None)
    if callable(provider_dependency):
        return provider_dependency

    legacy_dependency = getattr(browse, "get_api", None)
    if callable(legacy_dependency):
        return legacy_dependency

    raise RuntimeError("Browse router does not expose a gallery-provider dependency")


def _is_provider_specific_type(value_type: type[object]) -> bool:
    module = getattr(value_type, "__module__", "").lower()
    name = getattr(value_type, "__qualname__", value_type.__name__).lower()
    return any(marker in module or marker in name for marker in _PROVIDER_MARKERS)


def _collect_provider_specific_types(
    value: object,
    leaks: set[tuple[str, str]],
    seen: set[int],
) -> None:
    value_type = type(value)
    if _is_provider_specific_type(value_type):
        leaks.add(
            (
                getattr(value_type, "__module__", ""),
                getattr(value_type, "__qualname__", value_type.__name__),
            )
        )

    value_id = id(value)
    if value_id in seen:
        return
    seen.add(value_id)

    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            _collect_provider_specific_types(key, leaks, seen)
            _collect_provider_specific_types(nested_value, leaks, seen)
        return

    if isinstance(value, (list, tuple, set, frozenset)):
        for nested_value in value:
            _collect_provider_specific_types(nested_value, leaks, seen)
        return

    try:
        attributes = vars(value)
    except TypeError:
        return

    for nested_value in attributes.values():
        _collect_provider_specific_types(nested_value, leaks, seen)


def _count_provider_type_leaks(
    calls: list[tuple[str, tuple[object, ...], dict[str, object]]],
) -> int:
    leaks: set[tuple[str, str]] = set()
    seen: set[int] = set()
    for _, args, kwargs in calls:
        _collect_provider_specific_types(args, leaks, seen)
        _collect_provider_specific_types(kwargs, leaks, seen)
    return len(leaks)


class _Response(Protocol):
    status_code: int

    def json(self) -> object: ...


def _has_expected_result(response: _Response, provider: FakeGalleryProvider) -> bool:
    if getattr(response, "status_code", None) != 200:
        return False

    try:
        payload = response.json()
    except (AttributeError, ValueError):
        return False

    if not isinstance(payload, list) or not payload:
        return False

    item = payload[0]
    return (
        isinstance(item, dict)
        and item.get("gid") == provider.gallery.gid
        and item.get("token") == provider.gallery.token
        and item.get("title") == provider.gallery.title
    )


def _method_ran_since(
    provider: FakeGalleryProvider, method: str, call_count: int
) -> bool:
    return any(name == method for name, _, _ in provider.calls[call_count:])


def run_provider_swap_workload() -> dict[str, int]:
    """Exercise browse routes against a deterministic provider replacement."""
    provider = FakeGalleryProvider()
    app = FastAPI()
    app.include_router(browse.router)

    def get_fake_provider() -> FakeGalleryProvider:
        return provider

    app.dependency_overrides[_provider_dependency()] = get_fake_provider

    endpoints_passed = 0
    workload_failures = 0
    with TestClient(app, raise_server_exceptions=False) as client:
        for path, expected_method in _ENDPOINTS:
            call_count = len(provider.calls)
            try:
                response = client.get(path)
                endpoint_passed = _has_expected_result(response, provider) and _method_ran_since(
                    provider, expected_method, call_count
                )
            except Exception:
                endpoint_passed = False

            if endpoint_passed:
                endpoints_passed += 1
            else:
                workload_failures += 1

    return {
        "swap_endpoints_passed": endpoints_passed,
        "swap_workload_failures": workload_failures,
        "swap_contract_leaks": _count_provider_type_leaks(provider.calls),
    }
