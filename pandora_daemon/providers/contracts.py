from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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

@dataclass(frozen=True, slots=True)
class GalleryComment:
    """Normalized comment included in a gallery detail response."""

    id: int
    user: str
    comment: str
    score: int
    time: str
    is_uploader: bool = False
    vote_up_able: bool = False
    vote_down_able: bool = False
    vote_up_ed: bool = False
    vote_down_ed: bool = False
    editable: bool = False
    last_edited: str = ""


@dataclass(frozen=True, slots=True)
class GalleryDetail:
    """Normalized gallery metadata with adapter-owned opaque state."""

    gid: str
    token: str
    title: str
    title_jpn: str | None
    category: str
    uploader: str
    cover_url: str
    tags: Mapping[str, Sequence[str]]
    pages: int
    size: str
    posted: str
    favorite_slot: int | None
    url: str
    provider_data: object = field(repr=False, compare=False)
    preview_page_count: int = 1
    rating: float = 0.0
    rating_count: int = 0
    favorite_count: int = 0
    torrent_count: int = 0
    comments: Sequence[GalleryComment] = ()
    comments_has_more: bool = False


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
    auth_configured: bool


    async def get_gallery_details(self, gid: str, token: str) -> GalleryDetail: ...

    async def fetch_image(self, source: str) -> bytes: ...

    async def get_page_image(self, detail: GalleryDetail, page: int) -> bytes: ...

    async def get_thumbnail(self, detail: GalleryDetail, page: int) -> bytes: ...

    async def rate_gallery(self, detail: GalleryDetail, rating: int) -> object: ...

    async def vote_comment(
        self,
        detail: GalleryDetail,
        comment_id: int,
        vote: int,
    ) -> object: ...

    async def get_home_detail(self) -> object: ...

    async def aclose(self) -> None: ...
