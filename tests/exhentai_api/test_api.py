import pytest
from unittest.mock import AsyncMock
from exhentai_api.api import ExhentaiAPI
from exhentai_api.models.gallery import GalleryListItem
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
