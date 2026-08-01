"""Image service for pandora-daemon.

Coordinates image proxy, caching, page resolution, and prefetching.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from exhentai_api.parsers.gallery_detail import parse_gallery_detail
from exhentai_api.parsers.image import parse_image_viewer
from pandora_daemon.cache import CacheManager
from pandora_daemon.config import CacheConfig

logger = logging.getLogger(__name__)

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
        addr = ipaddress.ip_address(host)
    except ValueError:
        return True
    return addr.is_global


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
            addr = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            return False
        if not _address_is_allowed(addr):
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


def _validate_response_peer(resp: httpx.Response) -> None:
    """Best-effort guard against DNS rebinding between validation and connect."""
    extensions = getattr(resp, "extensions", {})
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
        addr = ipaddress.ip_address(peername[0])
    except (ValueError, TypeError):
        raise PermissionError("Image host connected to a restricted address")
    if not _address_is_allowed(addr):
        raise PermissionError("Image host connected to a restricted address")


def _validate_image_response(resp: httpx.Response) -> bytes:
    length = resp.headers.get("content-length")
    if length is not None:
        try:
            if int(length) > _MAX_PROXY_IMAGE_BYTES:
                raise RuntimeError("Image response is too large")
        except ValueError:
            raise RuntimeError("Invalid image response length") from None

    content_type = resp.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type and not content_type.startswith("image/"):
        raise RuntimeError("Image response has invalid content type")

    data = resp.content
    if len(data) > _MAX_PROXY_IMAGE_BYTES:
        raise RuntimeError("Image response is too large")
    if not data or not data.startswith(_IMAGE_MAGIC_PREFIXES):
        raise RuntimeError("Image response has invalid image signature")
    if data.startswith(b"RIFF") and data[8:12] != b"WEBP":
        raise RuntimeError("Image response has invalid image signature")
    return data


class ImageService:
    """Proxies all image requests through cache with background prefetch."""

    def __init__(self, api, cache: CacheManager, config: CacheConfig) -> None:
        self._api = api
        self._cache = cache
        self._config = config
        self._prefetch_tasks: dict[str, asyncio.Task] = {}
        self._page_url_cache: dict[str, str] = {}  # "{gid}:{page}" -> image_url
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

    async def proxy_image(self, url: str) -> bytes:
        """Restricted public image proxy with caching."""
        _validate_proxy_url(url)
        cached = await self._cache.get_image(url)
        if cached is not None:
            return cached

        data = await self._fetch_public_image(url)
        await self._cache.put_image(url, data)
        return data

    async def _fetch_public_image(self, url: str) -> bytes:
        """Fetch a validated public image URL without ExHentai cookies."""
        async with self._fetch_semaphore:
            _validate_proxy_url(url)
            client = self._get_public_image_client()
            for attempt in range(len(_IMAGE_TRANSPORT_RETRY_DELAYS) + 1):
                current_url = url
                try:
                    for _ in range(_MAX_REDIRECTS + 1):
                        client.cookies.clear()
                        try:
                            resp = await client.get(
                                current_url,
                                headers=_IMAGE_REQUEST_HEADERS,
                            )
                        finally:
                            client.cookies.clear()
                        _validate_response_peer(resp)
                        if resp.status_code in {301, 302, 303, 307, 308}:
                            location = resp.headers.get("location")
                            if not location:
                                raise RuntimeError("Image redirect missing location")
                            next_url = urljoin(str(resp.url), location)
                            _validate_proxy_url(next_url)
                            current_url = next_url
                            continue
                        resp.raise_for_status()
                        return _validate_image_response(resp)
                    raise RuntimeError("Too many redirects")
                except httpx.TransportError:
                    if attempt >= len(_IMAGE_TRANSPORT_RETRY_DELAYS):
                        raise
                    await asyncio.sleep(_IMAGE_TRANSPORT_RETRY_DELAYS[attempt])

        raise RuntimeError("Image fetch failed")

    async def get_page_image(self, gid: str, token: str, page: int) -> bytes:
        """Get full-size image for a gallery page. Cache-first."""
        # Check if we already know the CDN URL for this page
        page_key = f"{gid}:{page}"
        known_url = self._page_url_cache.get(page_key)
        if known_url:
            cached = await self._cache.get_image(known_url)
            if cached is not None:
                return cached

        # Resolve the viewer URL from gallery detail
        detail = self._cache.get_gallery(gid, token)
        if detail is None:
            detail = await self._api.get_gallery_details(gid, token)
            self._cache.put_gallery(detail)

        page_idx = page - 1
        if page_idx < 0 or page_idx >= detail.pages:
            raise ValueError(f"Page {page} out of range (1-{detail.pages})")

        # If page is beyond currently loaded viewer_urls, fetch the needed preview page
        if page_idx >= len(detail.viewer_urls):
            await self._load_preview_page(detail, page_idx)

        if page_idx >= len(detail.viewer_urls):
            raise ValueError(f"Could not resolve viewer URL for page {page}")

        viewer_url = detail.viewer_urls[page_idx]

        # Fetch and parse the viewer page to get the CDN image URL
        html = await self._api.client.get_html(viewer_url)
        image_url, nl = parse_image_viewer(html)

        if not image_url:
            raise RuntimeError(f"Could not resolve image URL for page {page}")

        _validate_proxy_url(image_url)

        # Cache the CDN URL mapping
        self._page_url_cache[page_key] = image_url

        # Check if the image is already cached (maybe by a different code path)
        cached = await self._cache.get_image(image_url)
        if cached is not None:
            return cached

        # Fetch the actual image without sending ExHentai cookies to the image host.
        data = await self._fetch_public_image(image_url)
        await self._cache.put_image(image_url, data)
        return data

    async def _load_preview_page(self, detail, target_page_idx: int) -> None:
        """Fetch additional gallery preview pages to resolve viewer URLs beyond page 1."""
        items_per_page = len(detail.viewer_urls) if detail.viewer_urls else 20
        if items_per_page == 0:
            return
        # Which preview page do we need?
        needed_preview_page = target_page_idx // items_per_page
        # Fetch all missing preview pages up to the needed one
        for p in range(1, needed_preview_page + 1):
            if len(detail.viewer_urls) > target_page_idx:
                break  # Already have enough
            page_url = f"{detail.url}?p={p}"
            html = await self._api.client.get_html(page_url)
            page_detail = parse_gallery_detail(html, detail.gid, detail.token)
            detail.viewer_urls.extend(page_detail.viewer_urls)
            detail.thumb_urls.extend(page_detail.thumb_urls)

    async def prefetch(self, gid: str, token: str, current_page: int, total_pages: int) -> None:
        """Schedule background prefetch for pages around current_page."""
        # Prune completed prefetch tasks to prevent unbounded growth
        done_keys = [k for k, t in self._prefetch_tasks.items() if t.done()]
        for k in done_keys:
            del self._prefetch_tasks[k]

        start = max(1, current_page - self._config.prefetch_behind)
        end = min(total_pages, current_page + self._config.prefetch_ahead)

        for p in range(start, end + 1):
            if p == current_page:
                continue
            page_key = f"{gid}:{p}"
            # Skip if already cached or already being prefetched
            if page_key in self._page_url_cache:
                known_url = self._page_url_cache[page_key]
                cached = await self._cache.get_image(known_url)
                if cached is not None:
                    continue
            if page_key in self._prefetch_tasks and not self._prefetch_tasks[page_key].done():
                continue

            task = asyncio.create_task(self._prefetch_page(gid, token, p))
            self._prefetch_tasks[page_key] = task

    async def _prefetch_page(self, gid: str, token: str, page: int) -> None:
        """Prefetch a single page (fire-and-forget)."""
        try:
            await self.get_page_image(gid, token, page)
        except Exception as e:
            logger.debug("Prefetch failed for %s:%d: %s", gid, page, e)

    async def shutdown(self) -> None:
        """Cancel all in-flight prefetch tasks."""
        for task in self._prefetch_tasks.values():
            task.cancel()
        if self._prefetch_tasks:
            await asyncio.gather(*self._prefetch_tasks.values(), return_exceptions=True)
        self._prefetch_tasks.clear()
        if self._public_image_client is not None:
            await self._public_image_client.aclose()
            self._public_image_client = None
