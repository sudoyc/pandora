"""Deterministic in-process workload for the complete gallery-provider seam."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI
from fastapi.testclient import TestClient

from pandora_daemon.config import CacheConfig
from pandora_daemon.dependencies import (
    get_cache,
    get_db,
    get_gallery_provider,
    get_image_service,
)
from pandora_daemon.image_service import ImageService
from pandora_daemon.providers.contracts import (
    AccountOverview,
    ArchiveOption,
    ArchiveOptions,
    CommentVoteResult,
    FavoriteCategory,
    FavoritesPage,
    GalleryComment,
    GalleryDetail,
    GallerySearchQuery,
    GallerySummary,
    GalleryTorrent,
    ProviderContext,
    RatingResult,
    UserProfile,
    UserTag,
)
from pandora_daemon.providers.registry import ProviderRegistry
from pandora_daemon.routes import browse, favorites, gallery, tags, user
from pandora_daemon.workspace import ProviderWorkspace


_FIXTURE_GID = "100001"
_FIXTURE_TOKEN = "provider-swap"
_FIXTURE_TITLE = "Provider swap fixture"
_PROVIDER_MARKERS = ("exhentai", "ehentai")
_IMAGE_BYTES = b"\x89PNG\r\n\x1a\nprovider-swap"


@dataclass(frozen=True, slots=True)
class _Endpoint:
    method: str
    path: str
    provider_method: str
    shape: str
    body: Mapping[str, object] | None = None


_ENDPOINTS = (
    _Endpoint("GET", "/api/homepage", "get_homepage", "gallery_list"),
    _Endpoint("GET", "/api/search", "search", "gallery_list"),
    _Endpoint("GET", "/api/popular", "get_popular", "gallery_list"),
    _Endpoint("GET", "/api/toplist", "get_toplist", "gallery_list"),
    _Endpoint("GET", "/api/watched", "get_watched", "gallery_list"),
    _Endpoint(
        "GET",
        "/api/image/proxy?url=https%3A%2F%2Ffixture.invalid%2Fcover.jpg",
        "fetch_image",
        "image",
    ),
    _Endpoint("GET", "/api/favorites", "get_favorites", "favorites"),
    _Endpoint(
        "POST",
        "/api/favorites",
        "add_favorite",
        "ok",
        {"gid": _FIXTURE_GID, "token": _FIXTURE_TOKEN, "slot": 2},
    ),
    _Endpoint(
        "DELETE",
        "/api/favorites",
        "modify_favorites",
        "ok",
        {"gids": [_FIXTURE_GID], "action": "delete"},
    ),
    _Endpoint("GET", "/api/home", "get_home_detail", "home"),
    _Endpoint("POST", "/api/home/reset_limit", "reset_image_limit", "home"),
    _Endpoint("GET", "/api/profile", "get_profile", "profile"),
    _Endpoint("GET", "/api/tags", "get_user_tags", "tags"),
    _Endpoint(
        "POST",
        "/api/tags",
        "add_tag",
        "ok",
        {"name": "fixture:tag", "watched": True},
    ),
    _Endpoint("DELETE", "/api/tags/7", "delete_tag", "ok"),
    _Endpoint(
        "GET",
        "/api/tags/suggest?q=fixture",
        "tag_catalog.suggest",
        "tag_suggestions",
    ),
    _Endpoint(
        "GET",
        "/api/tags/status",
        "tag_catalog.status",
        "tag_status",
    ),
    _Endpoint(
        "POST",
        "/api/tags/refresh",
        "tag_catalog.refresh",
        "tag_refresh",
    ),
    _Endpoint(
        "GET",
        f"/api/gallery/{_FIXTURE_GID}/{_FIXTURE_TOKEN}",
        "get_gallery_details",
        "detail",
    ),
    _Endpoint(
        "POST",
        f"/api/gallery/{_FIXTURE_GID}/{_FIXTURE_TOKEN}/comment",
        "comment_gallery",
        "ok",
        {"comment": "fixture comment"},
    ),
    _Endpoint(
        "POST",
        f"/api/gallery/{_FIXTURE_GID}/{_FIXTURE_TOKEN}/rate",
        "rate_gallery",
        "ok",
        {"rating": 9},
    ),
    _Endpoint(
        "POST",
        f"/api/gallery/{_FIXTURE_GID}/{_FIXTURE_TOKEN}/vote_comment",
        "vote_comment",
        "ok",
        {"comment_id": 17, "vote": 1},
    ),
    _Endpoint(
        "GET",
        f"/api/gallery/{_FIXTURE_GID}/{_FIXTURE_TOKEN}/torrents",
        "get_torrent_list",
        "torrents",
    ),
    _Endpoint(
        "GET",
        f"/api/gallery/{_FIXTURE_GID}/{_FIXTURE_TOKEN}/archive",
        "get_archive_list",
        "archive",
    ),
    _Endpoint(
        "GET",
        f"/api/gallery/{_FIXTURE_GID}/{_FIXTURE_TOKEN}/page/1",
        "get_page_image",
        "image",
    ),
    _Endpoint(
        "GET",
        f"/api/gallery/{_FIXTURE_GID}/{_FIXTURE_TOKEN}/thumb/1",
        "get_thumbnail",
        "image",
    ),
)


def _gallery_summary() -> GallerySummary:
    return GallerySummary(
        gid=_FIXTURE_GID,
        token=_FIXTURE_TOKEN,
        title=_FIXTURE_TITLE,
        category="fixture",
        uploader="fixture",
        thumb_url="https://fixture.invalid/thumbnail.jpg",
        posted="fixture",
        pages=1,
        url="https://fixture.invalid/gallery",
    )


def _gallery_detail() -> GalleryDetail:
    return GalleryDetail(
        gid=_FIXTURE_GID,
        token=_FIXTURE_TOKEN,
        title=_FIXTURE_TITLE,
        title_jpn=None,
        category="fixture",
        uploader="fixture",
        cover_url="https://fixture.invalid/cover.jpg",
        tags={"fixture": ("tag",)},
        pages=1,
        size="1 MiB",
        posted="fixture",
        favorite_slot=None,
        url="https://fixture.invalid/gallery",
        provider_data=None,
    )


class FakeGalleryProvider:
    """Provider double implementing every daemon-consumed capability."""

    auth_configured = True

    def __init__(self, provider_id: str = "fixture") -> None:
        self.provider_id = provider_id
        self.gallery = _gallery_summary()
        self.detail = _gallery_detail()
        self.tag = UserTag(7, "fixture:tag", True, False, None, 0)
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(self, method: str, args: tuple[object, ...], kwargs: dict[str, object]) -> None:
        self.calls.append((method, args, kwargs))

    async def get_homepage(self, *args: object, **kwargs: object) -> list[GallerySummary]:
        self._record("get_homepage", args, kwargs)
        return [self.gallery]

    async def search(
        self, query: GallerySearchQuery, *args: object, **kwargs: object
    ) -> list[GallerySummary]:
        self._record("search", (query, *args), kwargs)
        return [self.gallery]

    async def get_popular(self, *args: object, **kwargs: object) -> list[GallerySummary]:
        self._record("get_popular", args, kwargs)
        return [self.gallery]

    async def get_toplist(self, *args: object, **kwargs: object) -> list[GallerySummary]:
        self._record("get_toplist", args, kwargs)
        return [self.gallery]

    async def get_watched(self, *args: object, **kwargs: object) -> list[GallerySummary]:
        self._record("get_watched", args, kwargs)
        return [self.gallery]

    async def get_gallery_details(self, *args: object, **kwargs: object) -> GalleryDetail:
        self._record("get_gallery_details", args, kwargs)
        return self.detail

    async def fetch_image(self, *args: object, **kwargs: object) -> bytes:
        self._record("fetch_image", args, kwargs)
        return _IMAGE_BYTES

    async def get_page_image(self, *args: object, **kwargs: object) -> bytes:
        self._record("get_page_image", args, kwargs)
        return _IMAGE_BYTES

    async def get_thumbnail(self, *args: object, **kwargs: object) -> bytes:
        self._record("get_thumbnail", args, kwargs)
        return _IMAGE_BYTES

    async def get_favorites(self, *args: object, **kwargs: object) -> FavoritesPage:
        self._record("get_favorites", args, kwargs)
        return FavoritesPage(
            categories=(FavoriteCategory(2, "Fixture", 1),),
            galleries=(self.gallery,),
        )

    async def add_favorite(self, *args: object, **kwargs: object) -> None:
        self._record("add_favorite", args, kwargs)

    async def modify_favorites(self, *args: object, **kwargs: object) -> None:
        self._record("modify_favorites", args, kwargs)

    async def comment_gallery(self, *args: object, **kwargs: object) -> tuple[GalleryComment, ...]:
        self._record("comment_gallery", args, kwargs)
        return (GalleryComment(17, "fixture", "fixture comment", 0, "fixture"),)

    async def rate_gallery(self, *args: object, **kwargs: object) -> RatingResult:
        self._record("rate_gallery", args, kwargs)
        return RatingResult(4.5, 1)

    async def vote_comment(self, *args: object, **kwargs: object) -> CommentVoteResult:
        self._record("vote_comment", args, kwargs)
        return CommentVoteResult(17, 1, 1)

    async def get_torrent_list(self, *args: object, **kwargs: object) -> tuple[GalleryTorrent, ...]:
        self._record("get_torrent_list", args, kwargs)
        return (GalleryTorrent("fixture.torrent", "https://fixture.invalid/torrent"),)

    async def get_archive_list(self, *args: object, **kwargs: object) -> ArchiveOptions:
        self._record("get_archive_list", args, kwargs)
        return ArchiveOptions(
            funds="100 GP",
            original=ArchiveOption("https://fixture.invalid/archive", "1 MiB", "10 GP"),
        )

    async def get_home_detail(self) -> AccountOverview:
        self._record("get_home_detail", (), {})
        return AccountOverview(1, 100, 10)

    async def reset_image_limit(self) -> AccountOverview:
        self._record("reset_image_limit", (), {})
        return AccountOverview(0, 100, 10)

    async def get_profile(self) -> UserProfile:
        self._record("get_profile", (), {})
        return UserProfile("Fixture User", "https://fixture.invalid/avatar.jpg")

    async def get_user_tags(self) -> tuple[UserTag, ...]:
        self._record("get_user_tags", (), {})
        return (self.tag,)

    async def add_tag(self, *args: object, **kwargs: object) -> tuple[UserTag, ...]:
        self._record("add_tag", args, kwargs)
        return (self.tag,)

    async def delete_tag(self, *args: object, **kwargs: object) -> tuple[UserTag, ...]:
        self._record("delete_tag", args, kwargs)
        return ()

    async def aclose(self) -> None:
        self._record("aclose", (), {})


class _FakeCache:
    def __init__(self) -> None:
        self.detail: GalleryDetail | None = None
        self.images: dict[str, bytes] = {}

    def get_gallery(self, gid: str, token: str) -> GalleryDetail | None:
        del gid, token
        return self.detail

    def put_gallery(self, detail: GalleryDetail) -> None:
        self.detail = detail

    async def get_image(self, key: str) -> bytes | None:
        return self.images.get(key)

    async def put_image(self, key: str, data: bytes) -> None:
        self.images[key] = data


class _FakeDatabase:
    async def put_history(self, detail: GalleryDetail) -> None:
        del detail


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
    content: bytes

    def json(self) -> object: ...


def _has_expected_result(
    response: _Response,
    provider: FakeGalleryProvider,
    shape: str,
) -> bool:
    if response.status_code != 200:
        return False
    if shape == "image":
        return response.content == _IMAGE_BYTES

    try:
        payload = response.json()
    except (AttributeError, ValueError):
        return False

    if shape == "gallery_list":
        return (
            isinstance(payload, list)
            and bool(payload)
            and isinstance(payload[0], dict)
            and payload[0].get("gid") == provider.gallery.gid
            and payload[0].get("title") == provider.gallery.title
        )
    if shape == "favorites":
        return (
            isinstance(payload, dict)
            and isinstance(payload.get("galleries"), list)
            and bool(payload["galleries"])
            and payload["galleries"][0].get("gid") == provider.gallery.gid
        )
    if shape == "home":
        return isinstance(payload, dict) and payload.get("image_total") == 100
    if shape == "profile":
        return isinstance(payload, dict) and payload.get("display_name") == "Fixture User"
    if shape == "tags":
        return (
            isinstance(payload, list)
            and bool(payload)
            and isinstance(payload[0], dict)
            and payload[0].get("name") == provider.tag.name
        )
    if shape == "tag_suggestions":
        return (
            isinstance(payload, dict)
            and isinstance(payload.get("suggestions"), list)
            and bool(payload["suggestions"])
            and payload["suggestions"][0].get("tag") == "fixture"
        )
    if shape == "tag_status":
        return isinstance(payload, dict) and payload.get("loaded") is True
    if shape == "tag_refresh":
        return isinstance(payload, dict) and payload.get("ok") is True
    if shape == "detail":
        return isinstance(payload, dict) and payload.get("gid") == provider.detail.gid
    if shape == "torrents":
        return (
            isinstance(payload, list)
            and bool(payload)
            and isinstance(payload[0], dict)
            and payload[0].get("name") == "fixture.torrent"
        )
    if shape == "archive":
        return isinstance(payload, dict) and payload.get("funds") == "100 GP"
    if shape == "ok":
        return isinstance(payload, dict) and payload.get("ok") is True
    return False


def _method_ran_since(
    provider: FakeGalleryProvider,
    method: str,
    call_count: int,
) -> bool:
    return any(name == method for name, _, _ in provider.calls[call_count:])


def _provider_registry_failures() -> int:
    failures = 0
    context = ProviderContext(credentials={}, proxy="", timeout=30)

    try:
        ProviderRegistry({"../escape": lambda _: FakeGalleryProvider("../escape")})
    except ValueError:
        pass
    else:
        failures += 1

    mismatched = ProviderRegistry(
        {"expected": lambda _: FakeGalleryProvider("unexpected")},
        default_provider_id="expected",
    )
    try:
        mismatched.create("expected", context)
    except ValueError:
        pass
    else:
        failures += 1

    matching = ProviderRegistry(
        {" Fixture ": lambda _: FakeGalleryProvider("fixture")},
        default_provider_id="FIXTURE",
    )
    try:
        provider = matching.create(" fixture ", context)
    except (TypeError, ValueError):
        failures += 1
    else:
        failures += int(provider.provider_id != "fixture")

    return failures


def _workspace_isolation_failures() -> int:
    default = ProviderWorkspace.for_provider(
        "/config",
        "/library",
        "default",
        legacy_provider_id="default",
    )
    alternate = ProviderWorkspace.for_provider(
        "/config",
        "/library",
        "alternate",
        legacy_provider_id="default",
    )
    return int(
        default.database_path != Path("/config/pandora.db")
        or default.state_file != Path("/config/downloads.json")
        or default.library_path != Path("/library")
        or alternate.database_path != Path("/config/providers/alternate/pandora.db")
        or alternate.state_file != Path("/config/providers/alternate/downloads.json")
        or alternate.library_path != Path("/library/alternate")
    )


def run_provider_swap_workload() -> dict[str, int]:
    """Exercise every provider-backed public surface with a replacement provider."""
    provider = FakeGalleryProvider()
    cache = _FakeCache()
    database = _FakeDatabase()
    image_service = ImageService(provider, cache, CacheConfig())
    app = FastAPI()
    for router in (browse.router, favorites.router, gallery.router, tags.router, user.router):
        app.include_router(router)

    app.dependency_overrides[get_gallery_provider] = lambda: provider
    app.dependency_overrides[get_cache] = lambda: cache
    app.dependency_overrides[get_db] = lambda: database
    app.dependency_overrides[get_image_service] = lambda: image_service

    endpoints_passed = 0
    workload_failures = 0
    with TestClient(app, raise_server_exceptions=False) as client:
        for endpoint in _ENDPOINTS:
            call_count = len(provider.calls)
            try:
                response = client.request(
                    endpoint.method,
                    endpoint.path,
                    json=endpoint.body,
                )
                endpoint_passed = _has_expected_result(
                    response,
                    provider,
                    endpoint.shape,
                ) and _method_ran_since(
                    provider,
                    endpoint.provider_method,
                    call_count,
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
        "provider_registry_failures": _provider_registry_failures(),
        "workspace_isolation_failures": _workspace_isolation_failures(),
    }
