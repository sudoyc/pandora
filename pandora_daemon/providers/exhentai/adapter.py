from __future__ import annotations

import re
from typing import Any

from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from exhentai_api.models.gallery import GalleryListItem
from exhentai_api.models.search import SearchParams
from pandora_daemon.providers.contracts import (
    GallerySearchQuery,
    GallerySummary,
    ProviderContext,
)


_GALLERY_LINK = re.compile(r"/g/(\d+)/([0-9a-f]+)")


def _summary(item: GalleryListItem) -> GallerySummary:
    return GallerySummary(
        gid=str(item.gid),
        token=str(item.token),
        title=item.title,
        category=item.category,
        uploader=item.uploader,
        thumb_url=item.thumb_url,
        posted=item.posted,
        rating=item.rating,
        pages=item.pages,
        rated=item.rated,
        thumb_width=item.thumb_width,
        thumb_height=item.thumb_height,
        url=item.url,
    )


def _search_params(query: GallerySearchQuery) -> SearchParams:
    params = SearchParams(
        f_search=query.keyword,
        f_cats=query.category,
        advsearch=any(
            (
                query.minimum_rating is not None,
                query.search_name,
                query.search_tags,
                query.search_description,
                query.search_torrents,
                query.search_low_power_tags,
                query.disable_language_filter,
                query.minimum_pages is not None,
                query.maximum_pages is not None,
            )
        ),
        f_sname=query.search_name,
        f_stags=query.search_tags,
        f_sdesc=query.search_description,
        f_storr=query.search_torrents,
        f_sto=query.search_low_power_tags,
        f_sdt1=query.disable_language_filter,
        f_sh=query.show_expunged,
        f_sr=query.minimum_rating is not None,
        f_sp=query.minimum_pages is not None or query.maximum_pages is not None,
        f_srdd=query.minimum_rating,
        f_spf=query.minimum_pages,
        f_spt=query.maximum_pages,
    )
    return params


class ExHentaiProvider:
    """Translate Pandora provider contracts to the ExHentai implementation."""

    provider_id = "exhentai"

    def __init__(self, api: ExhentaiAPI, *, owns_client: bool = False) -> None:
        self._api = api
        self._owns_client = owns_client

    @property
    def client(self) -> ExhentaiClient:
        return self._api.client

    async def aclose(self) -> None:
        if self._owns_client:
            await self._api.client.aclose()
        else:
            await self._api.aclose()

    async def get_homepage(self, next_gid: str | None = None) -> list[GallerySummary]:
        return [_summary(item) for item in await self._api.get_homepage(next_gid=next_gid)]

    async def search(
        self,
        query: GallerySearchQuery,
        page: int = 0,
        next_gid: str | None = None,
    ) -> list[GallerySummary]:
        items = await self._api.search(_search_params(query), page=page, next_gid=next_gid)
        return [_summary(item) for item in items]

    async def get_popular(self) -> list[GallerySummary]:
        return [_summary(item) for item in await self._api.get_popular()]

    async def get_toplist(self, window: str = "15") -> list[GallerySummary]:
        summaries: list[GallerySummary] = []
        for item in await self._api.get_toplist(window):
            match = _GALLERY_LINK.search(item.link)
            if match is None:
                continue
            gid, token = match.groups()
            summaries.append(
                GallerySummary(
                    gid=gid,
                    token=token,
                    title=item.name,
                    category=item.type,
                    uploader="",
                    thumb_url="",
                    posted="",
                    url=item.link,
                )
            )
        return summaries

    async def get_watched(
        self,
        page: int = 0,
        next_gid: str | None = None,
    ) -> list[GallerySummary]:
        items = await self._api.get_watched(page=page, next_gid=next_gid)
        return [_summary(item) for item in items]

    async def get_gallery_details(self, gid: str, token: str) -> Any:
        return await self._api.get_gallery_details(gid, token)

    async def get_image_url(
        self, gid: str, imgkey: str, page: int, nl: str | None = None
    ) -> Any:
        return await self._api.get_image_url(gid, imgkey, page, nl=nl)

    async def get_gallery_token(self, gid: int, imgkey: str, page: int) -> str:
        return await self._api.get_gallery_token(gid, imgkey, page)

    async def get_favorites(self, **kwargs: Any) -> Any:
        return await self._api.get_favorites(**kwargs)

    async def add_favorite(self, gid: str, token: str, **kwargs: Any) -> str:
        return await self._api.add_favorite(gid, token, **kwargs)

    async def modify_favorites(self, gids: list[str], action: str) -> str:
        return await self._api.modify_favorites(gids, action)

    async def comment_gallery(
        self, gid: str, token: str, comment: str, *, edit_id: int | None = None
    ) -> Any:
        return await self._api.comment_gallery(gid, token, comment, edit_id=edit_id)

    async def vote_comment(self, *args: Any, **kwargs: Any) -> Any:
        return await self._api.vote_comment(*args, **kwargs)

    async def rate_gallery(self, *args: Any, **kwargs: Any) -> Any:
        return await self._api.rate_gallery(*args, **kwargs)

    async def get_torrent_list(self, gid: str, token: str) -> Any:
        return await self._api.get_torrent_list(gid, token)

    async def get_archive_list(self, gid: str, token: str) -> Any:
        return await self._api.get_archive_list(gid, token)

    async def download_archive(self, archive_url: str, resolution: str = "org") -> str:
        return await self._api.download_archive(archive_url, resolution)

    async def get_mytags(self) -> Any:
        return await self._api.get_mytags()

    async def add_tag(self, tag_name: str, **kwargs: Any) -> Any:
        return await self._api.add_tag(tag_name, **kwargs)

    async def delete_tag(self, tag_id: int) -> Any:
        return await self._api.delete_tag(tag_id)

    async def get_home_detail(self) -> Any:
        return await self._api.get_home_detail()

    async def reset_image_limit(self) -> Any:
        return await self._api.reset_image_limit()

    async def get_profile(self) -> Any:
        return await self._api.get_profile()

    async def image_search(self, *args: Any, **kwargs: Any) -> list[GallerySummary]:
        return [_summary(item) for item in await self._api.image_search(*args, **kwargs)]


def create_provider(context: ProviderContext) -> ExHentaiProvider:
    client = ExhentaiClient(
        igneous=context.credentials.get("igneous", ""),
        ipb_member_id=context.credentials.get("ipb_member_id", ""),
        ipb_pass_hash=context.credentials.get("ipb_pass_hash", ""),
        proxy=context.proxy,
        timeout=context.timeout,
    )
    return ExHentaiProvider(ExhentaiAPI(client=client), owns_client=True)
