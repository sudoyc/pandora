from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from exhentai_api.api import ExhentaiAPI
from exhentai_api.exceptions import (
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
from exhentai_api.models.gallery import GalleryListItem
from exhentai_api.models.search import SearchParams
from exhentai_api.models.toplist import TopListItem
from pandora_daemon.providers.contracts import (
    GallerySearchQuery,
    GallerySummary,
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
    media = MagicMock()
    media.fetch_image = AsyncMock(return_value=b"source")
    media.get_page_image = AsyncMock(return_value=b"page")
    media.get_thumbnail = AsyncMock(return_value=b"thumbnail")
    provider = ExHentaiProvider(api, media=media)
    detail = object()

    assert await provider.fetch_image("https://ehgt.org/source.jpg") == b"source"
    assert await provider.get_page_image(detail, 2) == b"page"
    assert await provider.get_thumbnail(detail, 2) == b"thumbnail"
    media.fetch_image.assert_awaited_once_with("https://ehgt.org/source.jpg")
    media.get_page_image.assert_awaited_once_with(detail, 2)
    media.get_thumbnail.assert_awaited_once_with(detail, 2)

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
    assert provider.client is client


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
