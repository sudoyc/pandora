"""TDD tests for exception detection in ExhentaiClient."""
import pytest
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

from exhentai_api.client import ExhentaiClient
from exhentai_api.exceptions import (
    AuthenticationError,
    ImageLimitError,
    GalleryNotFoundError,
    GalleryOffensiveError,
    NetworkError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code=200, text="<html>OK</html>", headers=None):
    """Build a mock httpx.Response."""
    mock = AsyncMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.text = text
    mock.headers = headers or {}
    if status_code >= 400:
        mock.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}",
            request=MagicMock(),
            response=MagicMock(status_code=status_code),
        )
    else:
        mock.raise_for_status.return_value = None
    return mock


# ---------------------------------------------------------------------------
# get_html — semantic exceptions (no retry)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_sad_panda_raises_authentication_error(mock_get):
    mock_get.return_value = _make_response(
        headers={"Content-Disposition": 'inline; filename="sadpanda.jpg"'}
    )
    async with ExhentaiClient() as client:
        with pytest.raises(AuthenticationError, match="Sad Panda"):
            await client.get_html("https://exhentai.org", backoff_factor=0.01)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_509_raises_image_limit_error(mock_get):
    mock_get.return_value = _make_response(status_code=509)
    async with ExhentaiClient() as client:
        with pytest.raises(ImageLimitError):
            await client.get_html("https://exhentai.org", backoff_factor=0.01)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_kokomade_raises_gallery_not_found(mock_get):
    mock_get.return_value = _make_response(text="<html>kokomade</html>")
    async with ExhentaiClient() as client:
        with pytest.raises(GalleryNotFoundError):
            await client.get_html("https://exhentai.org", backoff_factor=0.01)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_gallery_removed_raises_gallery_not_found(mock_get):
    mock_get.return_value = _make_response(
        text="<html>This gallery has been removed or is unavailable.</html>"
    )
    async with ExhentaiClient() as client:
        with pytest.raises(GalleryNotFoundError):
            await client.get_html("https://exhentai.org", backoff_factor=0.01)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_pining_raises_gallery_not_found(mock_get):
    mock_get.return_value = _make_response(
        text="<html>pining for the fjords</html>"
    )
    async with ExhentaiClient() as client:
        with pytest.raises(GalleryNotFoundError):
            await client.get_html("https://exhentai.org", backoff_factor=0.01)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_offensive_content_raises_gallery_offensive_error(mock_get):
    mock_get.return_value = _make_response(
        text="<html>Content Warning: This gallery contains offensive material.</html>"
    )
    async with ExhentaiClient() as client:
        with pytest.raises(GalleryOffensiveError):
            await client.get_html("https://exhentai.org", backoff_factor=0.01)


# ---------------------------------------------------------------------------
# get_html — network errors (retry → NetworkError)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_timeout_raises_network_error(mock_get):
    mock_get.side_effect = httpx.TimeoutException("timed out")
    async with ExhentaiClient() as client:
        with pytest.raises(NetworkError):
            await client.get_html("https://exhentai.org", retries=2, backoff_factor=0.01)


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_connect_error_raises_network_error(mock_get):
    mock_get.side_effect = httpx.ConnectError("connection refused")
    async with ExhentaiClient() as client:
        with pytest.raises(NetworkError):
            await client.get_html("https://exhentai.org", retries=2, backoff_factor=0.01)


# ---------------------------------------------------------------------------
# get_html — normal success
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_normal_200_returns_text(mock_get):
    mock_get.return_value = _make_response(text="<html>Normal page</html>")
    async with ExhentaiClient() as client:
        result = await client.get_html("https://exhentai.org", backoff_factor=0.01)
    assert result == "<html>Normal page</html>"


# ---------------------------------------------------------------------------
# get_html — retry behaviour
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_sad_panda_no_retry(mock_get):
    """Sad Panda must raise immediately — only 1 request made."""
    mock_get.return_value = _make_response(
        headers={"Content-Disposition": 'inline; filename="sadpanda.jpg"'}
    )
    async with ExhentaiClient() as client:
        with pytest.raises(AuthenticationError):
            await client.get_html("https://exhentai.org", retries=3, backoff_factor=0.01)
    assert mock_get.call_count == 1


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_network_error_retries_then_succeeds(mock_get):
    """Two timeouts then success → 3 requests total, returns HTML."""
    success = _make_response(text="<html>OK after retry</html>")
    mock_get.side_effect = [
        httpx.TimeoutException("timeout"),
        httpx.TimeoutException("timeout"),
        success,
    ]
    async with ExhentaiClient() as client:
        result = await client.get_html(
            "https://exhentai.org", retries=3, backoff_factor=0.01
        )
    assert result == "<html>OK after retry</html>"
    assert mock_get.call_count == 3


# ---------------------------------------------------------------------------
# post_json — 509 and network errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_json_509_raises_image_limit_error():
    async with ExhentaiClient() as client:
        with patch.object(client.session, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _make_response(status_code=509)
            with pytest.raises(ImageLimitError):
                await client.post_json(
                    "https://exhentai.org/api.php", json={}, backoff_factor=0.01
                )


@pytest.mark.asyncio
async def test_post_json_timeout_raises_network_error():
    async with ExhentaiClient() as client:
        with patch.object(client.session, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timed out")
            with pytest.raises(NetworkError):
                await client.post_json(
                    "https://exhentai.org/api.php",
                    json={},
                    retries=2,
                    backoff_factor=0.01,
                )


# ---------------------------------------------------------------------------
# post_form — timeout → NetworkError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_form_timeout_raises_network_error():
    async with ExhentaiClient() as client:
        with patch.object(client.session, "post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timed out")
            with pytest.raises(NetworkError):
                await client.post_form(
                    "https://exhentai.org/archiver.php",
                    data={},
                    retries=2,
                    backoff_factor=0.01,
                )
