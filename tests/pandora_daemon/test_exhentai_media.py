"""Deterministic tests for ExHentai-specific media handling."""
from __future__ import annotations

import asyncio
from collections import namedtuple
from io import BytesIO
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest
from PIL import Image
from exhentai_api.models.gallery import ThumbSprite

from pandora_daemon.providers.exhentai.media import ExHentaiMedia


@pytest.fixture
def public_dns():
    address = namedtuple("Address", "family type proto canonname sockaddr")

    def resolve(host, *args, **kwargs):
        if host in {
            "e-hentai.org",
            "exhentai.org",
            "ehgt.org",
            "fixture.hath.network",
            "s.exhentai.org",
        }:
            return [address(0, 0, 0, "", ("93.184.216.34", 0))]
        raise socket.gaierror()

    with patch(
        "pandora_daemon.providers.exhentai.media.socket.getaddrinfo",
        side_effect=resolve,
    ):
        yield


@pytest.fixture
def gallery_client():
    client = MagicMock()
    client.get_html = AsyncMock()
    return client


def _image_response(
    data: bytes = b"\xff\xd8\xffimage",
    *,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.headers = headers or {"content-type": "image/jpeg"}
    response.content = data
    response.extensions = {}
    response.raise_for_status = MagicMock()
    response.url = "https://exhentai.org/images/fixture.jpg"
    return response


def _public_image_client(response_or_side_effect) -> MagicMock:
    client = MagicMock()
    client.cookies = MagicMock()
    if isinstance(response_or_side_effect, (list, tuple)) or asyncio.iscoroutinefunction(
        response_or_side_effect
    ):
        client.get = AsyncMock(side_effect=response_or_side_effect)
    else:
        client.get = AsyncMock(return_value=response_or_side_effect)
    client.aclose = AsyncMock()
    return client


def _detail(**overrides):
    values = {
        "gid": "123",
        "token": "token",
        "pages": 1,
        "url": "https://exhentai.org/g/123/token/",
        "viewer_urls": ["https://exhentai.org/s/first/123-1"],
        "thumb_urls": [],
        "thumb_sprites": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_fetch_image_uses_its_own_cookie_free_transport(public_dns, gallery_client) -> None:
    response = _image_response()
    public_client = _public_image_client(response)

    with patch(
        "pandora_daemon.providers.exhentai.media.httpx.AsyncClient",
        return_value=public_client,
    ) as client_type:
        media = ExHentaiMedia(gallery_client)
        result = await media.fetch_image("https://exhentai.org/images/fixture.jpg")

    assert result == b"\xff\xd8\xffimage"
    assert not hasattr(media, "_cache")
    gallery_client.get_html.assert_not_called()
    client_type.assert_called_once()
    client_kwargs = client_type.call_args.kwargs
    assert client_kwargs["follow_redirects"] is False
    assert client_kwargs["timeout"] == 10.0
    assert client_kwargs["limits"].max_connections == 4
    assert client_kwargs["limits"].max_keepalive_connections == 4
    public_client.get.assert_awaited_once_with(
        "https://exhentai.org/images/fixture.jpg",
        headers={"Referer": "https://exhentai.org/"},
    )
    assert public_client.cookies.clear.call_count == 2


@pytest.mark.asyncio
async def test_fetch_image_rejects_untrusted_sources_and_redirects(public_dns, gallery_client) -> None:
    media = ExHentaiMedia(gallery_client)
    with pytest.raises(PermissionError):
        await media.fetch_image("https://example.com/image.jpg")

    redirect = _image_response(status_code=302, headers={"location": "https://example.com/image.jpg"})
    public_client = _public_image_client(redirect)
    with patch(
        "pandora_daemon.providers.exhentai.media.httpx.AsyncClient",
        return_value=public_client,
    ):
        with pytest.raises(PermissionError):
            await media.fetch_image("https://exhentai.org/images/fixture.jpg")


@pytest.mark.asyncio
async def test_fetch_image_allows_tun_fake_ip_but_rejects_private_peer(
    public_dns, gallery_client
) -> None:
    address = namedtuple("Address", "family type proto canonname sockaddr")
    response = _image_response(data=b"RIFF\x04\x00\x00\x00WEBP", headers={"content-type": "image/webp"})
    stream = MagicMock()
    stream.get_extra_info.return_value = ("198.18.0.89", 443)
    response.extensions = {"network_stream": stream}
    public_client = _public_image_client(response)

    with (
        patch(
            "pandora_daemon.providers.exhentai.media.socket.getaddrinfo",
            return_value=[address(0, 0, 0, "", ("198.18.0.89", 0))],
        ),
        patch(
            "pandora_daemon.providers.exhentai.media.httpx.AsyncClient",
            return_value=public_client,
        ),
    ):
        media = ExHentaiMedia(gallery_client)
        assert await media.fetch_image("https://s.exhentai.org/image.webp") == b"RIFF\x04\x00\x00\x00WEBP"

    private_peer = _image_response()
    private_stream = MagicMock()
    private_stream.get_extra_info.return_value = ("10.0.0.7", 443)
    private_peer.extensions = {"network_stream": private_stream}
    private_client = _public_image_client(private_peer)
    with patch(
        "pandora_daemon.providers.exhentai.media.httpx.AsyncClient",
        return_value=private_client,
    ):
        with pytest.raises(PermissionError, match="restricted address"):
            await ExHentaiMedia(gallery_client).fetch_image(
                "https://s.exhentai.org/image.webp"
            )


@pytest.mark.asyncio
async def test_fetch_image_retries_once_reuses_client_and_closes_once(
    public_dns, gallery_client
) -> None:
    response = _image_response()
    public_client = _public_image_client(
        [httpx.ConnectTimeout("connection timed out"), response, response]
    )

    with (
        patch(
            "pandora_daemon.providers.exhentai.media.httpx.AsyncClient",
            return_value=public_client,
        ) as client_type,
        patch(
            "pandora_daemon.providers.exhentai.media.asyncio.sleep",
            new_callable=AsyncMock,
        ) as sleep,
    ):
        media = ExHentaiMedia(gallery_client)
        first = await media.fetch_image("https://exhentai.org/images/first.jpg")
        second = await media.fetch_image("https://exhentai.org/images/second.jpg")
        await media.aclose()
        await media.aclose()

    assert first == second == b"\xff\xd8\xffimage"
    client_type.assert_called_once()
    assert public_client.get.await_count == 3
    sleep.assert_awaited_once_with(0.2)
    public_client.aclose.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_fetch_image_bounds_upstream_concurrency(public_dns, gallery_client) -> None:
    active = 0
    peak = 0

    async def fetch(*args, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return _image_response()

    public_client = _public_image_client(fetch)
    with patch(
        "pandora_daemon.providers.exhentai.media.httpx.AsyncClient",
        return_value=public_client,
    ):
        media = ExHentaiMedia(gallery_client)
        await asyncio.gather(
            *(
                media.fetch_image(f"https://exhentai.org/images/{index}.jpg")
                for index in range(8)
            )
        )
        await media.aclose()

    assert peak == 4


@pytest.mark.asyncio
async def test_get_page_image_resolves_viewer_and_enforces_bounds(gallery_client) -> None:
    detail = _detail()
    gallery_client.get_html.return_value = (
        '<img id="img" src="https://fixture.hath.network/full.jpg" />'
    )
    media = ExHentaiMedia(gallery_client)
    media.fetch_image = AsyncMock(return_value=b"page-bytes")

    assert await media.get_page_image(detail, 1) == b"page-bytes"
    gallery_client.get_html.assert_awaited_once_with(detail.viewer_urls[0])
    media.fetch_image.assert_awaited_once_with("https://fixture.hath.network/full.jpg")

    with pytest.raises(ValueError, match="out of range"):
        await media.get_page_image(detail, 2)


@pytest.mark.asyncio
async def test_preview_loading_extends_all_media_assets(gallery_client) -> None:
    initial_sprite = ThumbSprite("https://ehgt.org/sprite-1.jpg", 0, 0, 1, 1)
    next_sprite = ThumbSprite("https://ehgt.org/sprite-2.jpg", 1, 0, 1, 1)
    detail = _detail(
        pages=2,
        viewer_urls=["https://exhentai.org/s/first/123-1"],
        thumb_urls=["https://ehgt.org/thumb-1.jpg"],
        thumb_sprites=[initial_sprite],
    )
    parsed_preview = _detail(
        viewer_urls=["https://exhentai.org/s/second/123-2"],
        thumb_urls=["https://ehgt.org/thumb-2.jpg"],
        thumb_sprites=[next_sprite],
    )
    gallery_client.get_html.side_effect = [
        "<html>preview</html>",
        '<img id="img" src="https://fixture.hath.network/full-2.jpg" />',
    ]
    media = ExHentaiMedia(gallery_client)
    media.fetch_image = AsyncMock(return_value=b"page-two")

    with patch(
        "pandora_daemon.providers.exhentai.media.parse_gallery_detail",
        return_value=parsed_preview,
    ) as parse_detail:
        assert await media.get_page_image(detail, 2) == b"page-two"

    gallery_client.get_html.assert_has_awaits(
        [
            call("https://exhentai.org/g/123/token/?p=1"),
            call("https://exhentai.org/s/second/123-2"),
        ]
    )
    parse_detail.assert_called_once_with("<html>preview</html>", "123", "token")
    assert detail.viewer_urls == [
        "https://exhentai.org/s/first/123-1",
        "https://exhentai.org/s/second/123-2",
    ]
    assert detail.thumb_urls == ["https://ehgt.org/thumb-1.jpg", "https://ehgt.org/thumb-2.jpg"]
    assert detail.thumb_sprites == [initial_sprite, next_sprite]


@pytest.mark.asyncio
async def test_get_thumbnail_crops_sprite(gallery_client) -> None:
    source = Image.new("RGB", (4, 2), "black")
    source.putpixel((1, 0), (255, 0, 0))
    source.putpixel((2, 0), (0, 255, 0))
    sprite_bytes = BytesIO()
    source.save(sprite_bytes, format="PNG")
    detail = _detail(
        thumb_sprites=[
            ThumbSprite("https://ehgt.org/sprite.png", offset_x=1, offset_y=0, width=2, height=1)
        ]
    )
    media = ExHentaiMedia(gallery_client)
    media.fetch_image = AsyncMock(return_value=sprite_bytes.getvalue())

    result = await media.get_thumbnail(detail, 1)

    media.fetch_image.assert_awaited_once_with("https://ehgt.org/sprite.png")
    with Image.open(BytesIO(result)) as cropped:
        assert cropped.size == (2, 1)
        assert cropped.getpixel((0, 0)) == (255, 0, 0)
        assert cropped.getpixel((1, 0)) == (0, 255, 0)


@pytest.mark.asyncio
async def test_get_thumbnail_falls_back_to_direct_thumbnail(gallery_client) -> None:
    direct_url = "https://ehgt.org/thumb.jpg"
    detail = _detail(
        thumb_urls=[direct_url],
        thumb_sprites=[ThumbSprite(direct_url, offset_x=0, offset_y=0, width=0, height=0)],
    )
    media = ExHentaiMedia(gallery_client)
    media.fetch_image = AsyncMock(return_value=b"direct-thumbnail")

    assert await media.get_thumbnail(detail, 1) == b"direct-thumbnail"
    media.fetch_image.assert_awaited_once_with(direct_url)

    missing = _detail(thumb_urls=[], thumb_sprites=[])
    with pytest.raises(LookupError, match="No thumbnail"):
        await media.get_thumbnail(missing, 1)
