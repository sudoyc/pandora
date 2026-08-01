"""Tests for pandora_daemon.image_service module."""
from __future__ import annotations

import asyncio
from collections import namedtuple
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pandora_daemon.config import CacheConfig
from pandora_daemon.image_service import ImageService


@pytest.fixture
def cache_config(tmp_path):
    return CacheConfig(
        image_dir=str(tmp_path / "images"),
        image_max_size_mb=2048,
        gallery_ttl_seconds=300,
        prefetch_ahead=3,
        prefetch_behind=1,
    )


@pytest.fixture
def mock_api():
    api = MagicMock()
    api.client = MagicMock()
    return api


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get_image = AsyncMock(return_value=None)
    cache.put_image = AsyncMock()
    cache.get_gallery = MagicMock(return_value=None)
    cache.put_gallery = MagicMock()
    return cache


@pytest.fixture
def allow_public_dns():
    addr = namedtuple("Addr", "family type proto canonname sockaddr")

    def _mock(host, *args, **kwargs):
        if host in {"exhentai.org", "e-hentai.org", "ehgt.org", "fixture.hath.network"}:
            return [addr(0, 0, 0, "", ("93.184.216.34", 0))]
        raise socket.gaierror()

    with patch("pandora_daemon.image_service.socket.getaddrinfo", side_effect=_mock):
        yield


@pytest.fixture
def tun_fake_ip_dns():
    addr = namedtuple("Addr", "family type proto canonname sockaddr")

    def _mock(host, *args, **kwargs):
        if host == "s.exhentai.org":
            return [addr(0, 0, 0, "", ("198.18.0.89", 0))]
        raise socket.gaierror()

    with patch("pandora_daemon.image_service.socket.getaddrinfo", side_effect=_mock):
        yield


class TestProxyImage:
    @pytest.mark.asyncio
    async def test_proxy_cache_hit(self, mock_api, mock_cache, cache_config, allow_public_dns):
        mock_cache.get_image = AsyncMock(return_value=b"cached_bytes")
        svc = ImageService(mock_api, mock_cache, cache_config)

        result = await svc.proxy_image("https://exhentai.org/images/img.jpg")

        assert result == b"cached_bytes"
        mock_cache.get_image.assert_awaited_once_with("https://exhentai.org/images/img.jpg")

    @pytest.mark.asyncio
    async def test_proxy_cache_miss_fetches(self, mock_api, mock_cache, cache_config, allow_public_dns):
        mock_cache.get_image = AsyncMock(return_value=None)
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.content = b"\xff\xd8\xfffetched_bytes"
        resp.headers = {"content-type": "image/jpeg"}
        mock_api.client.session = MagicMock()

        svc = ImageService(mock_api, mock_cache, cache_config)
        with patch("pandora_daemon.image_service.httpx.AsyncClient") as mock_client_cls:
            client = AsyncMock()
            client.cookies = MagicMock()
            client.get = AsyncMock(return_value=resp)
            mock_client_cls.return_value = client

            result = await svc.proxy_image("https://exhentai.org/images/img.jpg")

        assert result == b"\xff\xd8\xfffetched_bytes"
        mock_cache.put_image.assert_awaited_once_with("https://exhentai.org/images/img.jpg", b"\xff\xd8\xfffetched_bytes")
        mock_api.client.session.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_proxy_rejects_non_allowlisted_host(self, mock_api, mock_cache, cache_config):
        svc = ImageService(mock_api, mock_cache, cache_config)

        with pytest.raises(PermissionError):
            await svc.proxy_image("https://example.com/img.jpg")

    @pytest.mark.asyncio
    async def test_proxy_rejects_credentials(self, mock_api, mock_cache, cache_config, allow_public_dns):
        svc = ImageService(mock_api, mock_cache, cache_config)

        with pytest.raises(PermissionError):
            await svc.proxy_image("https://user:pass@exhentai.org/img.jpg")

    @pytest.mark.asyncio
    async def test_proxy_allows_allowlisted_host_through_tun_fake_ip(
        self,
        mock_api,
        mock_cache,
        cache_config,
        tun_fake_ip_dns,
    ):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b"RIFF\x04\x00\x00\x00WEBP"
        response.headers = {"content-type": "image/webp"}
        stream = MagicMock()
        stream.get_extra_info.return_value = ("198.18.0.89", 443)
        response.extensions = {"network_stream": stream}

        with patch("pandora_daemon.image_service.httpx.AsyncClient") as mock_client_cls:
            client = AsyncMock()
            client.cookies = MagicMock()
            client.get = AsyncMock(return_value=response)
            mock_client_cls.return_value = client

            svc = ImageService(mock_api, mock_cache, cache_config)
            result = await svc.proxy_image("https://s.exhentai.org/w/02/532/example.webp")

        assert result == b"RIFF\x04\x00\x00\x00WEBP"
        client.get.assert_awaited_once_with(
            "https://s.exhentai.org/w/02/532/example.webp",
            headers={"Referer": "https://exhentai.org/"},
        )
        assert client.cookies.clear.call_count == 2

    @pytest.mark.asyncio
    async def test_proxy_still_rejects_private_peer(
        self,
        mock_api,
        mock_cache,
        cache_config,
        allow_public_dns,
    ):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b"\xff\xd8\xffimage"
        response.headers = {"content-type": "image/jpeg"}
        stream = MagicMock()
        stream.get_extra_info.return_value = ("10.0.0.7", 443)
        response.extensions = {"network_stream": stream}

        with patch("pandora_daemon.image_service.httpx.AsyncClient") as mock_client_cls:
            client = AsyncMock()
            client.cookies = MagicMock()
            client.get = AsyncMock(return_value=response)
            mock_client_cls.return_value = client

            svc = ImageService(mock_api, mock_cache, cache_config)
            with pytest.raises(PermissionError, match="restricted address"):
                await svc.proxy_image("https://exhentai.org/images/img.jpg")

    @pytest.mark.asyncio
    async def test_proxy_rejects_empty_image_response(
        self,
        mock_api,
        mock_cache,
        cache_config,
        allow_public_dns,
    ):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b""
        response.headers = {"content-type": "image/jpeg"}
        response.extensions = {}

        with patch("pandora_daemon.image_service.httpx.AsyncClient") as mock_client_cls:
            client = AsyncMock()
            client.cookies = MagicMock()
            client.get = AsyncMock(return_value=response)
            mock_client_cls.return_value = client

            svc = ImageService(mock_api, mock_cache, cache_config)
            with pytest.raises(RuntimeError, match="invalid image signature"):
                await svc.proxy_image("https://exhentai.org/images/empty.jpg")

        mock_cache.put_image.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_proxy_bounds_concurrent_upstream_fetches(
        self,
        mock_api,
        mock_cache,
        cache_config,
        allow_public_dns,
    ):
        active = 0
        peak = 0

        async def fetch(*args, **kwargs):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.01)
            active -= 1
            response = MagicMock()
            response.status_code = 200
            response.raise_for_status = MagicMock()
            response.content = b"\xff\xd8\xffimage"
            response.headers = {"content-type": "image/jpeg"}
            response.extensions = {}
            return response

        with patch("pandora_daemon.image_service.httpx.AsyncClient") as mock_client_cls:
            client = AsyncMock()
            client.cookies = MagicMock()
            client.get = AsyncMock(side_effect=fetch)
            mock_client_cls.return_value = client

            svc = ImageService(mock_api, mock_cache, cache_config)
            await asyncio.gather(*(
                svc.proxy_image(f"https://exhentai.org/images/{index}.jpg")
                for index in range(8)
            ))

        assert peak == 4

    @pytest.mark.asyncio
    async def test_proxy_reuses_client_and_retries_one_transport_failure(
        self,
        mock_api,
        mock_cache,
        cache_config,
        allow_public_dns,
    ):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()
        response.content = b"\xff\xd8\xffimage"
        response.headers = {"content-type": "image/jpeg"}
        response.extensions = {}
        timeout = httpx.ConnectTimeout("connection timed out")

        with (
            patch("pandora_daemon.image_service.httpx.AsyncClient") as mock_client_cls,
            patch(
                "pandora_daemon.image_service.asyncio.sleep",
                new_callable=AsyncMock,
            ) as sleep,
        ):
            client = AsyncMock()
            client.cookies = MagicMock()
            client.get = AsyncMock(side_effect=[timeout, response, response])
            mock_client_cls.return_value = client

            svc = ImageService(mock_api, mock_cache, cache_config)
            first = await svc.proxy_image("https://exhentai.org/images/first.jpg")
            second = await svc.proxy_image("https://exhentai.org/images/second.jpg")
            await svc.shutdown()

        assert first == b"\xff\xd8\xffimage"
        assert second == b"\xff\xd8\xffimage"
        mock_client_cls.assert_called_once()
        assert client.get.await_count == 3
        sleep.assert_awaited_once()
        client.aclose.assert_awaited_once()


class TestGetPageImage:
    @pytest.mark.asyncio
    async def test_page_image_cached(self, mock_api, mock_cache, cache_config, allow_public_dns):
        svc = ImageService(mock_api, mock_cache, cache_config)
        svc._page_url_cache["123:1"] = "https://ehgt.org/full.jpg"
        mock_cache.get_image = AsyncMock(return_value=b"page_bytes")

        result = await svc.get_page_image("123", "abc", 1)

        assert result == b"page_bytes"
        mock_cache.get_image.assert_awaited_once_with("https://ehgt.org/full.jpg")

    @pytest.mark.asyncio
    async def test_page_image_not_cached(self, mock_api, mock_cache, cache_config, allow_public_dns):
        detail = MagicMock()
        detail.viewer_urls = ["https://exhentai.org/s/imgkey1/123-1"]
        detail.pages = 1
        mock_cache.get_gallery = MagicMock(return_value=detail)

        viewer_html = '<html><body><img id="img" src="https://fixture.hath.network/full.jpg" /><script>nl(\'nltoken\')</script></body></html>'
        mock_api.client.get_html = AsyncMock(return_value=viewer_html)

        mock_cache.get_image = AsyncMock(return_value=None)
        img_resp = MagicMock()
        img_resp.raise_for_status = MagicMock()
        img_resp.content = b"\xff\xd8\xffimage_data"
        img_resp.headers = {"content-type": "image/jpeg"}
        mock_api.client.session = MagicMock()
        mock_api.client.session.get = AsyncMock(return_value=img_resp)

        with patch("pandora_daemon.image_service.httpx.AsyncClient") as mock_client_cls:
            client = AsyncMock()
            client.cookies = MagicMock()
            client.get = AsyncMock(return_value=img_resp)
            mock_client_cls.return_value = client

            svc = ImageService(mock_api, mock_cache, cache_config)
            result = await svc.get_page_image("123", "abc", 1)

        assert result == b"\xff\xd8\xffimage_data"
        mock_cache.put_image.assert_awaited_once_with(
            "https://fixture.hath.network/full.jpg",
            b"\xff\xd8\xffimage_data",
        )
        mock_api.client.session.get.assert_not_called()
        client.get.assert_awaited_once_with(
            "https://fixture.hath.network/full.jpg",
            headers={"Referer": "https://exhentai.org/"},
        )
        assert svc._page_url_cache["123:1"] == "https://fixture.hath.network/full.jpg"

    @pytest.mark.asyncio
    async def test_proxy_rejects_redirect_to_non_allowlisted_host(self, mock_api, mock_cache, cache_config, allow_public_dns):
        mock_cache.get_image = AsyncMock(return_value=None)
        first = MagicMock()
        first.status_code = 302
        first.headers = {"location": "https://example.com/img.jpg"}
        first.url = "https://exhentai.org/images/img.jpg"

        with patch("pandora_daemon.image_service.httpx.AsyncClient") as mock_client_cls:
            client = AsyncMock()
            client.cookies = MagicMock()
            client.get = AsyncMock(return_value=first)
            mock_client_cls.return_value = client

            svc = ImageService(mock_api, mock_cache, cache_config)

            with pytest.raises(PermissionError):
                await svc.proxy_image("https://exhentai.org/images/img.jpg")


class TestPrefetch:
    @pytest.mark.asyncio
    async def test_prefetch_schedules_tasks(self, mock_api, mock_cache, cache_config, allow_public_dns):
        detail = MagicMock()
        detail.viewer_urls = [f"https://exhentai.org/s/key{i}/123-{i+1}" for i in range(10)]
        mock_cache.get_gallery = MagicMock(return_value=detail)

        svc = ImageService(mock_api, mock_cache, cache_config)
        svc.get_page_image = AsyncMock(return_value=b"data")

        await svc.prefetch("123", "abc", current_page=5, total_pages=10)
        await asyncio.sleep(0.05)

        expected_keys = {"123:4", "123:6", "123:7", "123:8"}
        actual_keys = set(svc._prefetch_tasks.keys())
        assert expected_keys.issubset(actual_keys)

        await svc.shutdown()

    @pytest.mark.asyncio
    async def test_prefetch_clamps_to_bounds(self, mock_api, mock_cache, cache_config, allow_public_dns):
        detail = MagicMock()
        detail.viewer_urls = [f"https://exhentai.org/s/key{i}/123-{i+1}" for i in range(5)]
        mock_cache.get_gallery = MagicMock(return_value=detail)

        svc = ImageService(mock_api, mock_cache, cache_config)
        svc.get_page_image = AsyncMock(return_value=b"data")

        await svc.prefetch("123", "abc", current_page=1, total_pages=5)
        await asyncio.sleep(0.05)

        assert "123:0" not in svc._prefetch_tasks

        await svc.shutdown()


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_cancels_prefetch(self, mock_api, mock_cache, cache_config):
        svc = ImageService(mock_api, mock_cache, cache_config)

        async def slow():
            await asyncio.sleep(999)

        task = asyncio.create_task(slow())
        svc._prefetch_tasks["123:1"] = task

        await svc.shutdown()

        assert task.cancelled()
        assert len(svc._prefetch_tasks) == 0
