from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ProviderContext:
    """Immutable daemon-owned inputs used to construct one provider."""

    credentials: Mapping[str, str]
    proxy: str
    timeout: int


@dataclass(frozen=True, slots=True)
class GallerySearchQuery:
    """Provider-neutral gallery discovery criteria."""

    keyword: str = ""
    category: int | None = None
    minimum_rating: int | None = None
    search_name: bool = False
    search_tags: bool = False
    search_description: bool = False
    search_torrents: bool = False
    search_low_power_tags: bool = False
    disable_language_filter: bool = False
    show_expunged: bool = False
    minimum_pages: int | None = None
    maximum_pages: int | None = None


@dataclass(frozen=True, slots=True)
class GallerySummary:
    """Normalized gallery row consumed by daemon browse routes."""

    gid: str
    token: str
    title: str
    category: str
    uploader: str
    thumb_url: str
    posted: str
    rating: float = 0.0
    pages: int = 0
    rated: bool = False
    thumb_width: int = 0
    thumb_height: int = 0
    url: str = ""


class BrowseProvider(Protocol):
    async def get_homepage(self, next_gid: str | None = None) -> Sequence[GallerySummary]: ...

    async def search(
        self,
        query: GallerySearchQuery,
        page: int = 0,
        next_gid: str | None = None,
    ) -> Sequence[GallerySummary]: ...

    async def get_popular(self) -> Sequence[GallerySummary]: ...

    async def get_toplist(self, window: str = "15") -> Sequence[GallerySummary]: ...

    async def get_watched(
        self,
        page: int = 0,
        next_gid: str | None = None,
    ) -> Sequence[GallerySummary]: ...


class GalleryProvider(BrowseProvider, Protocol):
    """Lifecycle and core browse contract implemented by every provider."""

    provider_id: str

    async def get_home_detail(self) -> object: ...

    async def aclose(self) -> None: ...
