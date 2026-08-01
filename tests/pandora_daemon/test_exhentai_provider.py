from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pandora_daemon.providers.exhentai.upstream.api import ExhentaiAPI
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
from pandora_daemon.providers.exhentai.upstream.models.comment import GalleryComment as ExHentaiGalleryComment
from pandora_daemon.providers.exhentai.upstream.models.gallery import (
    GalleryDetail as ExHentaiGalleryDetail,
    GalleryListItem,
)
from pandora_daemon.providers.exhentai.upstream.models.search import SearchParams
from pandora_daemon.providers.exhentai.upstream.models.vote import RateResult, VoteCommentResult
from pandora_daemon.providers.exhentai.upstream.models.toplist import TopListItem
from pandora_daemon.providers.contracts import (
    CommentVoteResult,
    GalleryComment,
    GalleryDetail,
    GallerySearchQuery,
    GallerySummary,
    RatingResult,
    ProviderContext,
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
from pandora_daemon.providers.exhentai.adapter import ExHentaiProvider, create_provider


def _gallery_item() -> GalleryListItem:
    return GalleryListItem(
        gid="123456",
        token="abcdef0123",
        title="Fixture Gallery",
        category="Manga",
        uploader="fixture-uploader",
        thumb_url="https://thumb.test/fixture.jpg",
        posted="2026-08-02 00:00",
        rating=4.75,
        pages=42,
        rated=True,
        thumb_width=250,
        thumb_height=350,
    )


def _summary(item: GalleryListItem) -> GallerySummary:
    return GallerySummary(
        gid=item.gid,
        token=item.token,
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

def _gallery_comment() -> ExHentaiGalleryComment:
    return ExHentaiGalleryComment(
        id=17,
        score=-2,
        user="fixture-reader",
        comment="<p>Fixture comment</p>",
        time="2026-08-02 00:01",
        is_uploader=True,
        vote_up_able=True,
        vote_down_able=True,
        vote_up_ed=True,
        vote_down_ed=False,
        editable=True,
        last_edited="2026-08-02 00:02",
    )


def _gallery_detail() -> ExHentaiGalleryDetail:
    return ExHentaiGalleryDetail(
        gid="123456",
        token="abcdef0123",
        title="Fixture Gallery",
        title_jpn="フィクスチャー",
        category="Manga",
        uploader="fixture-uploader",
        cover_url="https://thumb.test/cover.jpg",
        tags={"artist": ["fixture-artist"], "language": ["English"]},
        pages=42,
        size="42 MB",
        posted="2026-08-02 00:00",
        favorite_slot=7,
        preview_pages=3,
        viewer_urls=["https://exhentai.org/s/fixture/123456-1"],
        thumb_urls=["https://ehgt.org/fixture-thumb.jpg"],
        rating=4.75,
        rating_count=19,
        favorite_count=8,
        torrent_count=2,
        comments=[_gallery_comment()],
        comments_has_more=True,
        api_uid="fixture-api-uid",
        api_key="fixture-api-key",
    )


@pytest.mark.asyncio
async def test_homepage_forwards_cursor_and_normalizes_gallery_summaries() -> None:
    item = _gallery_item()
    api = AsyncMock(spec=ExhentaiAPI)
    api.get_homepage.return_value = [item]

    result = await ExHentaiProvider(api).get_homepage(next_gid="7654321")

    assert result == [_summary(item)]
    api.get_homepage.assert_awaited_once_with(next_gid="7654321")


@pytest.mark.asyncio
async def test_search_maps_every_generic_field_and_forwards_page_and_cursor() -> None:
    item = _gallery_item()
    api = AsyncMock(spec=ExhentaiAPI)
    api.search.return_value = [item]
    query = GallerySearchQuery(
        keyword="artist:fixture",
        category=37,
        minimum_rating=4,
        search_name=True,
        search_tags=True,
        search_description=True,
        search_torrents=True,
        search_low_power_tags=True,
        disable_language_filter=True,
        show_expunged=True,
        minimum_pages=12,
        maximum_pages=345,
    )
    expected_params = SearchParams(
        f_search="artist:fixture",
        f_cats=37,
        advsearch=True,
        f_sname=True,
        f_stags=True,
        f_sdesc=True,
        f_storr=True,
        f_sto=True,
        f_sdt1=True,
        f_sdt2=False,
        f_sh=True,
        f_sr=True,
        f_sp=True,
        f_srdd=4,
        f_spf=12,
        f_spt=345,
    )

    result = await ExHentaiProvider(api).search(query, page=6, next_gid="7654321")

    assert result == [_summary(item)]
    api.search.assert_awaited_once_with(
        expected_params,
        page=6,
        next_gid="7654321",
    )


@pytest.mark.asyncio
async def test_watched_forwards_page_and_cursor_and_normalizes_gallery_summaries() -> None:
    item = _gallery_item()
    api = AsyncMock(spec=ExhentaiAPI)
    api.get_watched.return_value = [item]

    result = await ExHentaiProvider(api).get_watched(page=4, next_gid="7654321")

    assert result == [_summary(item)]
    api.get_watched.assert_awaited_once_with(page=4, next_gid="7654321")

@pytest.mark.asyncio
async def test_gallery_details_map_to_generic_fields_and_keep_raw_state_opaque() -> None:
    raw_detail = _gallery_detail()
    api = AsyncMock(spec=ExhentaiAPI)
    api.get_gallery_details.return_value = raw_detail

    result = await ExHentaiProvider(api).get_gallery_details(raw_detail.gid, raw_detail.token)

    expected_comment = GalleryComment(
        id=17,
        user="fixture-reader",
        comment="<p>Fixture comment</p>",
        score=-2,
        time="2026-08-02 00:01",
        is_uploader=True,
        vote_up_able=True,
        vote_down_able=True,
        vote_up_ed=True,
        vote_down_ed=False,
        editable=True,
        last_edited="2026-08-02 00:02",
    )
    assert type(result) is GalleryDetail
    assert result == GalleryDetail(
        gid="123456",
        token="abcdef0123",
        title="Fixture Gallery",
        title_jpn="フィクスチャー",
        category="Manga",
        uploader="fixture-uploader",
        cover_url="https://thumb.test/cover.jpg",
        tags={"artist": ["fixture-artist"], "language": ["English"]},
        pages=42,
        size="42 MB",
        posted="2026-08-02 00:00",
        favorite_slot=7,
        url=raw_detail.url,
        provider_data=None,
        preview_page_count=3,
        rating=4.75,
        rating_count=19,
        favorite_count=8,
        torrent_count=2,
        comments=(expected_comment,),
        comments_has_more=True,
    )
    assert result.provider_data is raw_detail
    for raw_name in ("api_uid", "api_key", "viewer_urls", "thumb_urls", "thumb_sprites"):
        assert not hasattr(result, raw_name)
    assert "fixture-api-uid" not in repr(result)


@pytest.mark.asyncio
async def test_generic_interactions_translate_to_raw_exhentai_arguments() -> None:
    raw_detail = _gallery_detail()
    api = AsyncMock(spec=ExhentaiAPI)
    api.get_gallery_details.return_value = raw_detail
    api.rate_gallery.return_value = RateResult(rating=4.5, rating_count=42)
    api.vote_comment.return_value = VoteCommentResult(
        comment_id=17,
        comment_score=3,
        comment_vote=-1,
    )
    provider = ExHentaiProvider(api)
    detail = await provider.get_gallery_details(raw_detail.gid, raw_detail.token)

    assert await provider.rate_gallery(detail, 9) == RatingResult(
        rating=4.5,
        rating_count=42,
    )
    assert await provider.vote_comment(detail, 17, -1) == CommentVoteResult(
        comment_id=17,
        comment_score=3,
        comment_vote=-1,
    )

    api.rate_gallery.assert_awaited_once_with(
        raw_detail.api_uid,
        raw_detail.api_key,
        123456,
        raw_detail.token,
        9,
    )
    api.vote_comment.assert_awaited_once_with(
        raw_detail.api_uid,
        raw_detail.api_key,
        123456,
        raw_detail.token,
        17,
        -1,
    )


@pytest.mark.asyncio
async def test_toplist_normalizes_gallery_links_and_drops_unparseable_items() -> None:
    valid_link = "https://e-hentai.org/g/654321/0123abcde/?source=toplist"
    api = AsyncMock(spec=ExhentaiAPI)
    api.get_toplist.return_value = [
        TopListItem(type="Manga", name="Valid toplist gallery", link=valid_link),
        TopListItem(
            type="Manga",
            name="Unparseable toplist gallery",
            link="https://e-hentai.org/toplist.php?tl=15",
        ),
    ]

    result = await ExHentaiProvider(api).get_toplist(window="all")

    assert result == [
        GallerySummary(
            gid="654321",
            token="0123abcde",
            title="Valid toplist gallery",
            category="Manga",
            uploader="",
            thumb_url="",
            posted="",
            url=valid_link,
        )
    ]
    api.get_toplist.assert_awaited_once_with("all")


@pytest.mark.asyncio
async def test_owned_provider_closes_media_and_client_once() -> None:
    client = MagicMock()
    client.aclose = AsyncMock()
    api = AsyncMock(spec=ExhentaiAPI)
    api.client = client
    media = MagicMock()
    media.aclose = AsyncMock()
    provider = ExHentaiProvider(api, owns_client=True, media=media)

    await provider.aclose()
    await provider.aclose()

    media.aclose.assert_awaited_once_with()
    client.aclose.assert_awaited_once_with()
    api.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_media_methods_delegate_through_the_error_boundary() -> None:
    api = AsyncMock(spec=ExhentaiAPI)
    raw_detail = _gallery_detail()
    api.get_gallery_details.return_value = raw_detail
    media = MagicMock()
    media.fetch_image = AsyncMock(return_value=b"source")
    media.get_page_image = AsyncMock(return_value=b"page")
    media.get_thumbnail = AsyncMock(return_value=b"thumbnail")
    provider = ExHentaiProvider(api, media=media)
    detail = await provider.get_gallery_details(raw_detail.gid, raw_detail.token)

    assert await provider.fetch_image("https://ehgt.org/source.jpg") == b"source"
    assert await provider.get_page_image(detail, 2) == b"page"
    assert await provider.get_thumbnail(detail, 2) == b"thumbnail"
    media.fetch_image.assert_awaited_once_with("https://ehgt.org/source.jpg")
    media.get_page_image.assert_awaited_once_with(raw_detail, 2)
    media.get_thumbnail.assert_awaited_once_with(raw_detail, 2)

    source = NetworkError("connection reset")
    media.get_page_image.side_effect = source
    with pytest.raises(ProviderNetworkError) as raised:
        await provider.get_page_image(detail, 2)

    assert raised.value.__cause__ is source


def test_factory_forwards_credentials_and_network_context() -> None:
    context = ProviderContext(
        credentials={
            "igneous": "igneous-cookie",
            "ipb_member_id": "member-cookie",
            "ipb_pass_hash": "pass-hash-cookie",
        },
        proxy="socks5://proxy.test:1080",
        timeout=43,
    )
    client = MagicMock()
    api = AsyncMock(spec=ExhentaiAPI)
    api.client = client

    with (
        patch(
            "pandora_daemon.providers.exhentai.adapter.ExhentaiClient",
            return_value=client,
        ) as client_type,
        patch(
            "pandora_daemon.providers.exhentai.adapter.ExhentaiAPI",
            return_value=api,
        ) as api_type,
    ):
        provider = create_provider(context)

    client_type.assert_called_once_with(
        igneous="igneous-cookie",
        ipb_member_id="member-cookie",
        ipb_pass_hash="pass-hash-cookie",
        proxy="socks5://proxy.test:1080",
        timeout=43,
    )
    api_type.assert_called_once_with(client=client)
    assert provider.auth_configured is True

@pytest.mark.parametrize(
    ("credentials", "expected_auth_configured"),
    [
        pytest.param(
            {
                "igneous": "igneous-cookie",
                "ipb_member_id": "member-cookie",
                "ipb_pass_hash": "pass-hash-cookie",
            },
            True,
            id="complete-session-credentials",
        ),
        pytest.param(
            {"ipb_member_id": "member-cookie", "ipb_pass_hash": "pass-hash-cookie"},
            False,
            id="missing-igneous-cookie",
        ),
        pytest.param(
            {"igneous": "igneous-cookie", "ipb_pass_hash": "pass-hash-cookie"},
            False,
            id="missing-member-cookie",
        ),
        pytest.param(
            {"igneous": "igneous-cookie", "ipb_member_id": "member-cookie"},
            False,
            id="missing-pass-hash-cookie",
        ),
    ],
)
def test_factory_auth_state_uses_required_session_credentials(
    credentials: dict[str, str],
    expected_auth_configured: bool,
) -> None:
    context = ProviderContext(credentials=credentials, proxy="", timeout=30)
    client = MagicMock()
    api = AsyncMock(spec=ExhentaiAPI)

    with (
        patch(
            "pandora_daemon.providers.exhentai.adapter.ExhentaiClient",
            return_value=client,
        ),
        patch(
            "pandora_daemon.providers.exhentai.adapter.ExhentaiAPI",
            return_value=api,
        ),
    ):
        provider = create_provider(context)

    assert provider.auth_configured is expected_auth_configured


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "expected_type"),
    [
        pytest.param(
            SessionError("expired session"),
            ProviderSessionError,
            id="session-before-authentication",
        ),
        pytest.param(
            AuthenticationError("authentication rejected"),
            ProviderAuthenticationError,
            id="authentication",
        ),
        pytest.param(
            UpstreamError("upstream unavailable"),
            ProviderUpstreamError,
            id="upstream",
        ),
        pytest.param(
            ImageLimitError("image quota exhausted"),
            ProviderQuotaError,
            id="image-limit",
        ),
        pytest.param(
            GalleryNotFoundError("gallery unavailable"),
            ProviderGalleryNotFoundError,
            id="gallery-not-found",
        ),
        pytest.param(
            GalleryOffensiveError("content blocked"),
            ProviderContentBlockedError,
            id="content-blocked",
        ),
        pytest.param(ParseError("invalid markup"), ProviderParseError, id="parse"),
        pytest.param(NetworkError("connection reset"), ProviderNetworkError, id="network"),
        pytest.param(ExhentaiError("unknown failure"), ProviderError, id="generic"),
    ],
)
async def test_call_api_translates_every_exhentai_error(
    source: ExhentaiError,
    expected_type: type[ProviderError],
) -> None:
    provider = ExHentaiProvider(AsyncMock(spec=ExhentaiAPI))
    operation = AsyncMock(side_effect=source)

    with pytest.raises(expected_type) as raised:
        await provider._call_api(operation)

    assert type(raised.value) is expected_type
    assert str(raised.value) == str(source)
    assert raised.value.public_code == "exhentai"
    assert raised.value.__cause__ is source


@pytest.mark.asyncio
async def test_call_api_preserves_upstream_status_code() -> None:
    source = UpstreamError("upstream unavailable", status_code=503)
    provider = ExHentaiProvider(AsyncMock(spec=ExhentaiAPI))
    operation = AsyncMock(side_effect=source)

    with pytest.raises(ProviderUpstreamError) as raised:
        await provider._call_api(operation)

    assert raised.value.status_code == 503
    assert raised.value.public_code == "exhentai"
    assert raised.value.__cause__ is source


@pytest.mark.asyncio
async def test_call_api_leaves_non_exhentai_errors_unchanged() -> None:
    source = RuntimeError("unrelated failure")
    provider = ExHentaiProvider(AsyncMock(spec=ExhentaiAPI))
    operation = AsyncMock(side_effect=source)

    with pytest.raises(RuntimeError) as raised:
        await provider._call_api(operation)

    assert raised.value is source
    assert raised.value.__cause__ is None


@pytest.mark.asyncio
async def test_homepage_translates_exhentai_failure_at_adapter_boundary() -> None:
    source = NetworkError("connection reset")
    api = AsyncMock(spec=ExhentaiAPI)
    api.get_homepage.side_effect = source

    with pytest.raises(ProviderNetworkError) as raised:
        await ExHentaiProvider(api).get_homepage(next_gid="7654321")

    assert raised.value.__cause__ is source
    api.get_homepage.assert_awaited_once_with(next_gid="7654321")
