import pytest
import httpx
from unittest.mock import patch, AsyncMock
from exhentai_api.client import ExhentaiClient

@pytest.mark.asyncio
async def test_client_headers():
    client = ExhentaiClient(igneous="test_ig", ipb_member_id="123")
    assert client.cookies["igneous"] == "test_ig"
    assert client.cookies["ipb_member_id"] == "123"
    assert "User-Agent" in client.headers

@pytest.mark.asyncio
async def test_client_context_manager():
    async with ExhentaiClient() as client:
        assert isinstance(client, ExhentaiClient)
        assert not client.session.is_closed
    assert client.session.is_closed

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_success(mock_get):
    url = "https://exhentai.org"
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.text = "<html>Success</html>"
    mock_get.return_value = mock_response

    async with ExhentaiClient() as client:
        html = await client.get_html(url)
        assert html == "<html>Success</html>"

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_sad_panda(mock_get):
    url = "https://exhentai.org"
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"Content-Disposition": 'inline; filename="sadpanda.jpg"'}
    mock_get.return_value = mock_response

    async with ExhentaiClient() as client:
        with pytest.raises(Exception, match="Sad Panda"):
            await client.get_html(url)

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_retry(mock_get):
    url = "https://exhentai.org"

    mock_response_success = AsyncMock(spec=httpx.Response)
    mock_response_success.status_code = 200
    mock_response_success.headers = {}
    mock_response_success.text = "<html>Success after retry</html>"

    # Fail twice, succeed on third attempt
    mock_get.side_effect = [
        httpx.ConnectError("Network error"),
        httpx.ConnectError("Network error"),
        mock_response_success
    ]

    async with ExhentaiClient() as client:
        html = await client.get_html(url, retries=3, backoff_factor=0.01)
        assert html == "<html>Success after retry</html>"
        assert mock_get.call_count == 3

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_retry_failure(mock_get):
    url = "https://exhentai.org"

    # Fail always
    mock_get.side_effect = httpx.ConnectError("Network error")

    async with ExhentaiClient() as client:
        with pytest.raises(Exception, match="Network error"):
            await client.get_html(url, retries=2, backoff_factor=0.01)
        assert mock_get.call_count == 2

@pytest.mark.asyncio
async def test_post_json():
    async with ExhentaiClient() as client:
        with patch.object(client.session, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock(spec=httpx.Response)
            mock_response.json.return_value = {"success": True}
            mock_post.return_value = mock_response

            result = await client.post_json("https://example.com/api", json={"test": 123})

            mock_post.assert_called_once_with("https://example.com/api", json={"test": 123})
            assert result == {"success": True}

@pytest.mark.asyncio
async def test_post_json_retry_success():
    url = "https://example.com/api"
    payload = {"test": 123}

    async with ExhentaiClient() as client:
        with patch.object(client.session, 'post', new_callable=AsyncMock) as mock_post:
            mock_response_success = AsyncMock(spec=httpx.Response)
            mock_response_success.json.return_value = {"success": True}

            mock_post.side_effect = [
                httpx.ConnectError("Network error"),
                httpx.ConnectError("Network error"),
                mock_response_success
            ]

            result = await client.post_json(url, json=payload, retries=3, backoff_factor=0.01)

            assert result == {"success": True}
            assert mock_post.call_count == 3

@pytest.mark.asyncio
async def test_post_json_retry_failure():
    url = "https://example.com/api"
    payload = {"test": 123}

    async with ExhentaiClient() as client:
        with patch.object(client.session, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Network error")

            with pytest.raises(Exception, match="Network error"):
                await client.post_json(url, json=payload, retries=2, backoff_factor=0.01)

            assert mock_post.call_count == 2

@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_get_html_with_params(mock_get):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.text = "<html>Params Success</html>"
    mock_get.return_value = mock_response

    async with ExhentaiClient() as client:
        html = await client.get_html("https://ex.org", params={"f_search": "test"})
        assert html == "<html>Params Success</html>"
        mock_get.assert_called_once_with("https://ex.org", params={"f_search": "test"})

@pytest.mark.asyncio
async def test_post_form():
    async with ExhentaiClient() as client:
        with patch.object(client.session, 'post', new_callable=AsyncMock) as mock_post:
            mock_response = AsyncMock(spec=httpx.Response)
            mock_response.text = "Form OK"
            mock_response.raise_for_status = list # Just needs to be callable
            mock_post.return_value = mock_response

            result = await client.post_form("https://ex.org/api", data={"favcat": "1"})
            mock_post.assert_called_once_with("https://ex.org/api", data={"favcat": "1"})
            assert result == "Form OK"


@pytest.mark.asyncio
async def test_client_default_timeout():
    client = ExhentaiClient()
    assert client.session.timeout.connect == 30.0
    await client.aclose()

@pytest.mark.asyncio
async def test_client_custom_timeout():
    client = ExhentaiClient(timeout=60)
    assert client.session.timeout.connect == 60.0
    await client.aclose()

@pytest.mark.asyncio
async def test_client_no_proxy_by_default():
    client = ExhentaiClient()
    # httpx stores proxy as _transport_for_url mapping; no proxy means default transport
    assert client.session._mounts == {}  # no custom mounts when no proxy
    await client.aclose()
