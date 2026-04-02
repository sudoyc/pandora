import pytest
from unittest.mock import patch, AsyncMock
from exhentai_api.api import ExhentaiAPI
from exhentai_api.models.gallery import GalleryListItem

@pytest.mark.asyncio
async def test_get_homepage():
    api = ExhentaiAPI()
    
    mock_html = """
    <table class="itg"><tr>
      <td class="gl3c"><a href="https://exhentai.org/g/1/0123456789/"><div class="glname">Test</div></a></td>
      <td class="gl1c"><div class="cn">Manga</div></td>
    </tr></table>
    """
    
    with patch("exhentai_api.client.ExhentaiClient.get_html", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_html
        items = await api.get_homepage()
        
        assert len(items) == 1
        assert items[0].gid == "1"
