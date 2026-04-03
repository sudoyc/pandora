import pytest
from exhentai_api.models.toplist import TopListItem
from exhentai_api.parsers.toplist import parse_toplist
from exhentai_api.api import ExhentaiAPI

def test_parse_toplist():
    with open("tests/exhentai_api/data/toplist.html", "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_toplist(html)
    assert isinstance(result, list)
    assert len(result) > 0

    # Test mapping
    galleries = [i for i in result if i.type == "Gallery"]
    assert len(galleries) == 4
    assert galleries[0].name == "Gallery 1"
    assert galleries[0].link == "/g/1/abc"
    assert galleries[3].name == "Gallery 4"

    uploaders = [i for i in result if i.type == "Uploader"]
    assert len(uploaders) == 4
    assert uploaders[0].name == "Uploader 1"
    assert uploaders[0].link == "/u/1"
    assert uploaders[3].name == "Uploader 4"

@pytest.mark.asyncio
async def test_get_popular(monkeypatch):
    class MockClient:
        async def get_html(self, url, params=None):
            self.last_url = url
            return "<html><body><div class=\"itg\"><tr><td class=\"glname\">Pop 1</td><td class=\"gl3c\"><a href=\"https://exhentai.org/g/1/abcdef1234/\"></a></td></tr></div></body></html>"
        async def aclose(self):
            pass

    mock_client = MockClient()

    api = ExhentaiAPI(client=mock_client)
    result = await api.get_popular()

    assert len(result) == 1
    assert result[0].title == "Pop 1"
    assert mock_client.last_url == "https://exhentai.org/popular"

@pytest.mark.asyncio
async def test_get_toplist(monkeypatch):
    class MockClient:
        async def get_html(self, url, params=None):
            self.last_url = url
            return "<html><body><div class=\"ido\"><table><tr></tr><tr><td>G</td><td><div class=\"tun\"><a href=\"/g/1/abc\">Gal 1</a></div></td></tr></table></div></body></html>"
        async def aclose(self):
            pass

    mock_client = MockClient()

    api = ExhentaiAPI(client=mock_client)
    result = await api.get_toplist(tl="15")

    # Just asserting it returns a list and makes the correct API call
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].type == "G"
    assert result[0].name == "Gal 1"
    assert result[0].link == "/g/1/abc"
    assert mock_client.last_url == "https://exhentai.org/toplist.php"

