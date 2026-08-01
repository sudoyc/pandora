from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from typing import ParamSpec, TypeVar, cast

from pandora_daemon.providers.exhentai.upstream.api import ExhentaiAPI
from pandora_daemon.providers.exhentai.upstream.client import ExhentaiClient
from pandora_daemon.providers.exhentai.upstream.exceptions import (
    AuthenticationError,
    ExhentaiError,
    GalleryNotFoundError,
    GalleryOffensiveError,
    ImageLimitError,
    NetworkError,
    ParseError,
    SessionError,
    UpstreamError,
)
from pandora_daemon.providers.exhentai.upstream.models.archive import (
    ArchiveOption as ExHentaiArchiveOption,
    ArchiverData,
)
from pandora_daemon.providers.exhentai.upstream.models.comment import GalleryComment as ExHentaiGalleryComment
from pandora_daemon.providers.exhentai.upstream.models.gallery import (
    GalleryDetail as ExHentaiGalleryDetail,
    GalleryListItem,
)
from pandora_daemon.providers.exhentai.upstream.models.favorites import (
    FavoriteCategory as ExHentaiFavoriteCategory,
    FavoritesResponse,
)
from pandora_daemon.providers.exhentai.upstream.models.home import HomeDetail
from pandora_daemon.providers.exhentai.upstream.models.profile import ProfileResult
from pandora_daemon.providers.exhentai.upstream.models.search import SearchParams
from pandora_daemon.providers.exhentai.upstream.models.tags import WatchedTag
from pandora_daemon.providers.exhentai.upstream.models.torrent import TorrentItem
from pandora_daemon.providers.exhentai.upstream.models.vote import (
    RateResult,
    VoteCommentResult,
)
from pandora_daemon.providers.exhentai.media import ExHentaiMedia
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
    ProviderContext,
    GalleryTorrent,
    RatingResult,
    UserProfile,
    UserTag,
)
from pandora_daemon.providers.errors import (
    ProviderAuthenticationError,
    ProviderContentBlockedError,
    ProviderError,
    ProviderGalleryNotFoundError,
    ProviderNetworkError,
    ProviderParseError,
    ProviderQuotaError,
    ProviderSessionError,
    ProviderUpstreamError,
)


_P = ParamSpec("_P")
_T = TypeVar("_T")

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

def _comment(comment: ExHentaiGalleryComment) -> GalleryComment:
    return GalleryComment(
        id=comment.id,
        user=comment.user,
        comment=comment.comment,
        score=comment.score,
        time=comment.time,
        is_uploader=comment.is_uploader,
        vote_up_able=comment.vote_up_able,
        vote_down_able=comment.vote_down_able,
        vote_up_ed=comment.vote_up_ed,
        vote_down_ed=comment.vote_down_ed,
        editable=comment.editable,
        last_edited=comment.last_edited,
    )

def _favorite_category(category: ExHentaiFavoriteCategory) -> FavoriteCategory:
    return FavoriteCategory(slot=category.slot, name=category.name, count=category.count)


def _favorites(response: FavoritesResponse) -> FavoritesPage:
    return FavoritesPage(
        categories=tuple(_favorite_category(category) for category in response.categories),
        galleries=tuple(_summary(gallery) for gallery in response.galleries),
    )


def _torrent(torrent: TorrentItem) -> GalleryTorrent:
    return GalleryTorrent(name=torrent.name, url=torrent.url)


def _archive_option(option: ExHentaiArchiveOption | None) -> ArchiveOption | None:
    if option is None:
        return None
    return ArchiveOption(url=option.url, size=option.size, cost=option.cost)


def _archive(archive: ArchiverData) -> ArchiveOptions:
    return ArchiveOptions(
        funds=archive.funds,
        original=_archive_option(archive.original),
        resample=_archive_option(archive.resample),
    )


def _account_overview(detail: HomeDetail) -> AccountOverview:
    return AccountOverview(
        image_used=detail.image_used,
        image_total=detail.image_total,
        reset_cost=detail.reset_cost,
    )


def _profile(profile: ProfileResult) -> UserProfile:
    return UserProfile(display_name=profile.display_name, avatar_url=profile.avatar_url)


def _user_tag(tag: WatchedTag) -> UserTag:
    return UserTag(
        id=tag.id,
        name=tag.name,
        watched=tag.watched,
        hidden=tag.hidden,
        color=tag.color,
        weight=tag.weight,
    )


def _rating(result: RateResult) -> RatingResult:
    return RatingResult(rating=result.rating, rating_count=result.rating_count)


def _comment_vote(result: VoteCommentResult) -> CommentVoteResult:
    return CommentVoteResult(
        comment_id=result.comment_id,
        comment_score=result.comment_score,
        comment_vote=result.comment_vote,
    )


def _detail(detail: ExHentaiGalleryDetail) -> GalleryDetail:
    return GalleryDetail(
        gid=str(detail.gid),
        token=str(detail.token),
        title=detail.title,
        title_jpn=detail.title_jpn,
        category=detail.category,
        uploader=detail.uploader,
        cover_url=detail.cover_url,
        tags={name: list(values) for name, values in detail.tags.items()},
        pages=detail.pages,
        size=detail.size,
        posted=detail.posted,
        favorite_slot=detail.favorite_slot,
        url=detail.url,
        provider_data=detail,
        preview_page_count=detail.preview_pages,
        rating=detail.rating,
        rating_count=detail.rating_count,
        favorite_count=detail.favorite_count,
        torrent_count=detail.torrent_count,
        comments=tuple(_comment(comment) for comment in detail.comments),
        comments_has_more=detail.comments_has_more,
    )


def _raw_detail(detail: GalleryDetail) -> ExHentaiGalleryDetail:
    return cast(ExHentaiGalleryDetail, detail.provider_data)

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

    def __init__(
        self,
        api: ExhentaiAPI,
        *,
        owns_client: bool = False,
        media: ExHentaiMedia | None = None,
        auth_configured: bool = False,
    ) -> None:
        self._api = api
        self._media = media
        self._owns_client = owns_client
        self.auth_configured = auth_configured
        self._closed = False

    async def _call_api(
        self,
        method: Callable[_P, Awaitable[_T]],
        /,
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _T:
        try:
            return await method(*args, **kwargs)
        except SessionError as exc:
            raise ProviderSessionError(str(exc), public_code="exhentai") from exc
        except AuthenticationError as exc:
            raise ProviderAuthenticationError(str(exc), public_code="exhentai") from exc
        except UpstreamError as exc:
            raise ProviderUpstreamError(
                str(exc),
                status_code=exc.status_code,
                public_code="exhentai",
            ) from exc
        except ImageLimitError as exc:
            raise ProviderQuotaError(str(exc), public_code="exhentai") from exc
        except GalleryNotFoundError as exc:
            raise ProviderGalleryNotFoundError(str(exc), public_code="exhentai") from exc
        except GalleryOffensiveError as exc:
            raise ProviderContentBlockedError(str(exc), public_code="exhentai") from exc
        except ParseError as exc:
            raise ProviderParseError(str(exc), public_code="exhentai") from exc
        except NetworkError as exc:
            raise ProviderNetworkError(str(exc), public_code="exhentai") from exc
        except ExhentaiError as exc:
            raise ProviderError(str(exc), public_code="exhentai") from exc

    def _get_media(self) -> ExHentaiMedia:
        if self._media is None:
            self._media = ExHentaiMedia(self._api.client)
        return self._media


    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._media is not None:
                await self._call_api(self._media.aclose)
        finally:
            if self._owns_client:
                await self._call_api(self._api.client.aclose)
            else:
                await self._call_api(self._api.aclose)

    async def get_homepage(self, next_gid: str | None = None) -> list[GallerySummary]:
        items = await self._call_api(self._api.get_homepage, next_gid=next_gid)
        return [_summary(item) for item in items]

    async def search(
        self,
        query: GallerySearchQuery,
        page: int = 0,
        next_gid: str | None = None,
    ) -> list[GallerySummary]:
        items = await self._call_api(
            self._api.search,
            _search_params(query),
            page=page,
            next_gid=next_gid,
        )
        return [_summary(item) for item in items]

    async def get_popular(self) -> list[GallerySummary]:
        items = await self._call_api(self._api.get_popular)
        return [_summary(item) for item in items]

    async def get_toplist(self, window: str = "15") -> list[GallerySummary]:
        summaries: list[GallerySummary] = []
        for item in await self._call_api(self._api.get_toplist, window):
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
        items = await self._call_api(self._api.get_watched, page=page, next_gid=next_gid)
        return [_summary(item) for item in items]

    async def get_gallery_details(self, gid: str, token: str) -> GalleryDetail:
        detail = await self._call_api(self._api.get_gallery_details, gid, token)
        return _detail(detail)



    async def fetch_image(self, source: str) -> bytes:
        return await self._call_api(self._get_media().fetch_image, source)

    async def get_page_image(self, detail: GalleryDetail, page: int) -> bytes:
        return await self._call_api(
            self._get_media().get_page_image,
            _raw_detail(detail),
            page,
        )

    async def get_thumbnail(self, detail: GalleryDetail, page: int) -> bytes:
        return await self._call_api(
            self._get_media().get_thumbnail,
            _raw_detail(detail),
            page,
        )

    async def get_favorites(
        self,
        slot: int = -1,
        page: int = 0,
        keyword: str = "",
        search_name: bool = False,
        search_tags: bool = False,
        search_notes: bool = False,
    ) -> FavoritesPage:
        response = await self._call_api(
            self._api.get_favorites,
            favcat=slot,
            page=page,
            keyword=keyword,
            sn=search_name,
            st=search_tags,
            sf=search_notes,
        )
        return _favorites(response)

    async def add_favorite(
        self,
        gid: str,
        token: str,
        slot: int = 0,
        note: str = "",
    ) -> None:
        await self._call_api(self._api.add_favorite, gid, token, favcat=slot, favnote=note)

    async def modify_favorites(self, gids: Sequence[str], action: str) -> None:
        await self._call_api(self._api.modify_favorites, list(gids), action)

    async def comment_gallery(
        self, gid: str, token: str, comment: str, *, edit_id: int | None = None
    ) -> list[GalleryComment]:
        comments = await self._call_api(
            self._api.comment_gallery,
            gid,
            token,
            comment,
            edit_id=edit_id,
        )
        return [_comment(item) for item in comments]

    async def vote_comment(
        self,
        detail: GalleryDetail,
        comment_id: int,
        vote: int,
    ) -> CommentVoteResult:
        raw_detail = _raw_detail(detail)
        result = await self._call_api(
            self._api.vote_comment,
            raw_detail.api_uid,
            raw_detail.api_key,
            int(detail.gid),
            detail.token,
            comment_id,
            vote,
        )
        return _comment_vote(result)

    async def rate_gallery(self, detail: GalleryDetail, rating: int) -> RatingResult:
        raw_detail = _raw_detail(detail)
        result = await self._call_api(
            self._api.rate_gallery,
            raw_detail.api_uid,
            raw_detail.api_key,
            int(detail.gid),
            detail.token,
            rating,
        )
        return _rating(result)

    async def get_torrent_list(self, gid: str, token: str) -> list[GalleryTorrent]:
        torrents = await self._call_api(self._api.get_torrent_list, gid, token)
        return [_torrent(torrent) for torrent in torrents]

    async def get_archive_list(self, gid: str, token: str) -> ArchiveOptions:
        archive = await self._call_api(self._api.get_archive_list, gid, token)
        return _archive(archive)


    async def get_user_tags(self) -> list[UserTag]:
        tags = await self._call_api(self._api.get_mytags)
        return [_user_tag(tag) for tag in tags]

    async def add_tag(
        self,
        tag_name: str,
        *,
        watched: bool = False,
        hidden: bool = False,
        color: str = "",
        weight: int = 0,
    ) -> list[UserTag]:
        tags = await self._call_api(
            self._api.add_tag,
            tag_name,
            watched=watched,
            hidden=hidden,
            color=color,
            weight=weight,
        )
        return [_user_tag(tag) for tag in tags]

    async def delete_tag(self, tag_id: int) -> list[UserTag]:
        tags = await self._call_api(self._api.delete_tag, tag_id)
        return [_user_tag(tag) for tag in tags]

    async def get_home_detail(self) -> AccountOverview:
        detail = await self._call_api(self._api.get_home_detail)
        return _account_overview(detail)

    async def reset_image_limit(self) -> AccountOverview:
        detail = await self._call_api(self._api.reset_image_limit)
        return _account_overview(detail)

    async def get_profile(self) -> UserProfile:
        profile = await self._call_api(self._api.get_profile)
        return _profile(profile)



def create_provider(context: ProviderContext) -> ExHentaiProvider:
    credentials = context.credentials
    igneous = credentials.get("igneous", "")
    ipb_member_id = credentials.get("ipb_member_id", "")
    ipb_pass_hash = credentials.get("ipb_pass_hash", "")
    client = ExhentaiClient(
        igneous=igneous,
        ipb_member_id=ipb_member_id,
        ipb_pass_hash=ipb_pass_hash,
        proxy=context.proxy,
        timeout=context.timeout,
    )
    return ExHentaiProvider(
        ExhentaiAPI(client=client),
        owns_client=True,
        auth_configured=bool(igneous and ipb_member_id and ipb_pass_hash),
    )
