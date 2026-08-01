import pytest
from unittest.mock import AsyncMock, patch
from exhentai_api.api import ExhentaiAPI
from exhentai_api.exceptions import ParseError
from exhentai_api.models.gallery import GalleryListItem, GalleryDetail
from exhentai_api.constants import BASE_URL

@pytest.mark.asyncio
async def test_get_homepage():
    mock_client = AsyncMock()

    mock_html = """
    <table class="itg"><tr>
      <td class="gl3c"><a href="https://exhentai.org/g/1/0123456789/"><div class="glname">Test</div></a></td>
      <td class="gl1c"><div class="cn">Manga</div></td>
    </tr></table>
    """

    mock_client.get_html.return_value = mock_html
    api = ExhentaiAPI(client=mock_client)

    items = await api.get_homepage()

    assert len(items) == 1
    assert items[0].gid == "1"

    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/")


@pytest.mark.asyncio
async def test_get_homepage_with_next_cursor():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = "<html>No hits found</html>"
    api = ExhentaiAPI(client=mock_client)

    await api.get_homepage(next_gid="4075469")

    mock_client.get_html.assert_called_once_with(
        f"{BASE_URL}/",
        params={"next": "4075469"},
    )


@pytest.mark.asyncio
async def test_parser_failure_raises_sanitized_parse_error():
    upstream_page = "<html>FULL_UPSTREAM_PAGE</html>"
    mock_client = AsyncMock()
    mock_client.get_html.return_value = upstream_page
    api = ExhentaiAPI(client=mock_client)

    with patch(
        "exhentai_api.api.parse_gallery_list",
        side_effect=ValueError(upstream_page),
    ):
        with pytest.raises(ParseError) as raised:
            await api.get_homepage()

    assert str(raised.value) == "Upstream response parse failed."
    assert "FULL_UPSTREAM_PAGE" not in str(raised.value)

@pytest.mark.asyncio
async def test_get_gallery_details():
    mock_client = AsyncMock()
    mock_html = "<h1 id='gn'>Title</h1>"
    mock_client.get_html.return_value = mock_html
    api = ExhentaiAPI(client=mock_client)

    detail = await api.get_gallery_details("123", "abc")

    assert isinstance(detail, GalleryDetail)
    assert detail.title == "Title"
    assert detail.gid == "123"
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/g/123/abc/")

from exhentai_api.models.image import ImageDetail

@pytest.mark.asyncio
async def test_get_image_url():
    mock_client = AsyncMock()
    mock_html = """<img id="img" src="https://ex.com/img.jpg"><div onclick="nl('xyz')"></div>"""
    mock_client.get_html.return_value = mock_html
    api = ExhentaiAPI(client=mock_client)

    # Test normal load
    image = await api.get_image_url("123", "abc", 1)
    assert image.gid == "123"
    assert image.page == 1
    assert image.image_url == "https://ex.com/img.jpg"
    assert image.nl == "xyz"
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/s/abc/123-1")

@pytest.mark.asyncio
async def test_get_image_url_with_nl():
    mock_client = AsyncMock()
    mock_client.post_json.return_value = {"i3": "<img src=\"https://ex.com/new.jpg\">", "i6": "nl('new_nl')"}
    api = ExhentaiAPI(client=mock_client)

    # Test NL reload
    image = await api.get_image_url("123", "abc", 1, nl="old_nl")
    assert image.image_url == "https://ex.com/new.jpg"
    assert image.nl == "new_nl"
    mock_client.post_json.assert_called_once_with(
        f"{BASE_URL}/api.php",
        json={"method": "showpage", "gid": "123", "page": "1", "imgkey": "abc", "showkey": "old_nl"}
    )
