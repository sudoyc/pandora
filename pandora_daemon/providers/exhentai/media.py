"""ExHentai-specific image transport and gallery media resolution."""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from io import BytesIO
from exhentai_api.models.gallery import GalleryDetail as ExHentaiGalleryDetail
from urllib.parse import urljoin, urlsplit

import httpx
from PIL import Image
from exhentai_api.client import ExhentaiClient
from exhentai_api.parsers.gallery_detail import parse_gallery_detail
from exhentai_api.parsers.image import parse_image_viewer

_ALLOWED_IMAGE_HOSTS = (
    "e-hentai.org",
    "exhentai.org",
    "ehgt.org",
    "ehgt.org.gslb.e-hentai.org",
    "hath.network",
)
# RFC 2544 benchmarking space is commonly used by TUN proxies for DNS fake-IP
# routing. URLs still have to pass the HTTPS image-host allowlist above.
_ALLOWED_TUN_FAKE_IP_NETWORKS = (ipaddress.ip_network("198.18.0.0/15"),)
_IMAGE_REQUEST_HEADERS = {"Referer": "https://exhentai.org/"}
_IMAGE_FETCH_CONCURRENCY = 4
_IMAGE_TRANSPORT_RETRY_DELAYS = (0.2,)
_MAX_REDIRECTS = 5
_MAX_PROXY_IMAGE_BYTES = 50 * 1024 * 1024
_IMAGE_MAGIC_PREFIXES = (
    b"\xff\xd8\xff",  # JPEG
    b"\x89PNG\r\n\x1a\n",
    b"GIF87a",
    b"GIF89a",
    b"RIFF",  # WEBP starts with RIFF....WEBP
)


def _host_is_allowed(host: str) -> bool:
    return any(host == base or host.endswith(f".{base}") for base in _ALLOWED_IMAGE_HOSTS)


def _host_looks_public(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return address.is_global


def _address_is_allowed(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return address.is_global or any(
        address in network for network in _ALLOWED_TUN_FAKE_IP_NETWORKS
    )


def _host_resolves_to_public_ip(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False

    seen = False
    for info in infos:
        sockaddr = info[4]
        if not sockaddr:
            continue
        seen = True
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if not _address_is_allowed(address):
            return False
    return seen


def _validate_proxy_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError("Only https image URLs are allowed")
    if parsed.username or parsed.password:
        raise PermissionError("Credentials are not allowed in image URLs")
    host = parsed.hostname
    if not host:
        raise ValueError("Image URL must include a host")
    if not _host_looks_public(host.lower()):
        raise PermissionError("Image host is not allowed")
    if not _host_is_allowed(host.lower()):
        raise PermissionError("Image host is not allowed")
    if not _host_resolves_to_public_ip(host):
        raise PermissionError("Image host resolves to a restricted address")


def _validate_response_peer(response: httpx.Response) -> None:
    """Best-effort guard against DNS rebinding between validation and connect."""
    extensions = getattr(response, "extensions", {})
    if not isinstance(extensions, dict):
        return
    stream = extensions.get("network_stream")
    if stream is None:
        return
    try:
        peername = stream.get_extra_info("peername")
    except Exception:
        return
    if not peername:
        return
    try:
        address = ipaddress.ip_address(peername[0])
    except (ValueError, TypeError):
        raise PermissionError("Image host connected to a restricted address") from None
    if not _address_is_allowed(address):
        raise PermissionError("Image host connected to a restricted address")


def _validate_image_response(response: httpx.Response) -> bytes:
    length = response.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > _MAX_PROXY_IMAGE_BYTES:
                raise RuntimeError("Image response is too large")
        except ValueError:
            raise RuntimeError("Invalid image response length") from None

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type and not content_type.startswith("image/"):
        raise RuntimeError("Image response has invalid content type")

    data = response.content
    if len(data) > _MAX_PROXY_IMAGE_BYTES:
        raise RuntimeError("Image response is too large")
    if not data or not data.startswith(_IMAGE_MAGIC_PREFIXES):
        raise RuntimeError("Image response has invalid image signature")
    if data.startswith(b"RIFF") and data[8:12] != b"WEBP":
        raise RuntimeError("Image response has invalid image signature")
    return data


def _preview_page_size(detail: ExHentaiGalleryDetail) -> int:
    """Use the smallest populated asset collection as the current preview width."""
    lengths = [
        len(values)
        for values in (
            getattr(detail, "viewer_urls", ()),
            getattr(detail, "thumb_urls", ()),
            getattr(detail, "thumb_sprites", ()),
        )
        if values
    ]
    return min(lengths, default=20)


def _has_thumbnail(detail: ExHentaiGalleryDetail, page_index: int) -> bool:
    sprites = getattr(detail, "thumb_sprites", ())
    if page_index < len(sprites):
        sprite = sprites[page_index]
        if (
            getattr(sprite, "url", "")
            and getattr(sprite, "width", 0) > 0
            and getattr(sprite, "height", 0) > 0
        ):
            return True
    return page_index < len(getattr(detail, "thumb_urls", ()))


class ExHentaiMedia:
    """Own ExHentai image transport, page resolution, and thumbnail extraction."""

    def __init__(self, client: ExhentaiClient) -> None:
        self._client = client
        self._fetch_semaphore = asyncio.Semaphore(_IMAGE_FETCH_CONCURRENCY)
        self._public_image_client: httpx.AsyncClient | None = None

    def _get_public_image_client(self) -> httpx.AsyncClient:
        if self._public_image_client is None:
            self._public_image_client = httpx.AsyncClient(
                follow_redirects=False,
                timeout=10.0,
                limits=httpx.Limits(
                    max_connections=_IMAGE_FETCH_CONCURRENCY,
                    max_keepalive_connections=_IMAGE_FETCH_CONCURRENCY,
                ),
            )
        return self._public_image_client

    async def fetch_image(self, source: str) -> bytes:
        """Fetch one validated ExH image URL without carrying gallery cookies."""
        _validate_proxy_url(source)
        async with self._fetch_semaphore:
            _validate_proxy_url(source)
            client = self._get_public_image_client()
            for attempt in range(len(_IMAGE_TRANSPORT_RETRY_DELAYS) + 1):
                current_url = source
                try:
                    for _ in range(_MAX_REDIRECTS + 1):
                        client.cookies.clear()
                        try:
                            response = await client.get(
                                current_url,
                                headers=_IMAGE_REQUEST_HEADERS,
                            )
                        finally:
                            client.cookies.clear()
                        _validate_response_peer(response)
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("location")
                            if not location:
                                raise RuntimeError("Image redirect missing location")
                            next_url = urljoin(str(response.url), location)
                            _validate_proxy_url(next_url)
                            current_url = next_url
                            continue
                        response.raise_for_status()
                        return _validate_image_response(response)
                    raise RuntimeError("Too many redirects")
                except httpx.TransportError:
                    if attempt >= len(_IMAGE_TRANSPORT_RETRY_DELAYS):
                        raise
                    await asyncio.sleep(_IMAGE_TRANSPORT_RETRY_DELAYS[attempt])

        raise RuntimeError("Image fetch failed")

    async def get_page_image(self, detail: ExHentaiGalleryDetail, page: int) -> bytes:
        """Resolve a gallery viewer page and fetch its full-size image."""
        page_index = page - 1
        if page_index < 0 or page_index >= detail.pages:
            raise ValueError(f"Page {page} out of range (1-{detail.pages})")

        if page_index >= len(detail.viewer_urls):
            await self._load_preview_page(detail, page_index, asset="viewer")
        if page_index >= len(detail.viewer_urls):
            raise ValueError(f"Could not resolve viewer URL for page {page}")

        html = await self._client.get_html(detail.viewer_urls[page_index])
        image_url, _ = parse_image_viewer(html)
        if not image_url:
            raise RuntimeError(f"Could not resolve image URL for page {page}")
        return await self.fetch_image(image_url)

    async def get_thumbnail(self, detail: ExHentaiGalleryDetail, page: int) -> bytes:
        """Fetch and crop a thumbnail sprite, or return a direct thumbnail."""
        page_index = page - 1
        if page_index < 0 or page_index >= detail.pages:
            raise ValueError(f"Page {page} out of range (1-{detail.pages})")

        if not _has_thumbnail(detail, page_index):
            await self._load_preview_page(detail, page_index, asset="thumbnail")

        sprites = detail.thumb_sprites
        if page_index < len(sprites):
            sprite = sprites[page_index]
            if (
                getattr(sprite, "url", "")
                and getattr(sprite, "width", 0) > 0
                and getattr(sprite, "height", 0) > 0
            ):
                sprite_data = await self.fetch_image(sprite.url)
                with Image.open(BytesIO(sprite_data)) as image:
                    left = sprite.offset_x
                    top = sprite.offset_y
                    cropped = image.crop(
                        (left, top, left + sprite.width, top + sprite.height)
                    )
                    output = BytesIO()
                    cropped.save(output, format=image.format or "JPEG")
                    return output.getvalue()

        thumb_urls = detail.thumb_urls
        direct_url = thumb_urls[page_index] if page_index < len(thumb_urls) else ""
        if not direct_url and page_index < len(sprites):
            direct_url = getattr(sprites[page_index], "url", "")
        if direct_url:
            return await self.fetch_image(direct_url)

        raise LookupError(f"No thumbnail for page {page}")

    async def _load_preview_page(
        self,
        detail: ExHentaiGalleryDetail,
        target_page_index: int,
        *,
        asset: str = "viewer",
    ) -> None:
        """Load preview pages through the authenticated ExH client as needed."""
        items_per_page = _preview_page_size(detail)
        needed_preview_page = target_page_index // items_per_page

        for preview_page in range(1, needed_preview_page + 1):
            if asset == "viewer":
                if target_page_index < len(detail.viewer_urls):
                    break
            elif _has_thumbnail(detail, target_page_index):
                break
            page_url = f"{detail.url}?p={preview_page}"
            html = await self._client.get_html(page_url)
            page_detail = parse_gallery_detail(html, detail.gid, detail.token)
            detail.viewer_urls.extend(page_detail.viewer_urls)
            detail.thumb_urls.extend(page_detail.thumb_urls)
            detail.thumb_sprites.extend(page_detail.thumb_sprites)

    async def aclose(self) -> None:
        """Close the reusable public-image transport once."""
        client = self._public_image_client
        self._public_image_client = None
        if client is not None:
            await client.aclose()
