import pytest
from exhentai_api.models.toplist import TopListResponse
from exhentai_api.parsers.toplist import parse_toplist
from exhentai_api.api import ExhentaiAPI

def test_parse_toplist():
    with open("tests/exhentai_api/data/toplist.html", "r", encoding="utf-8") as f:
        html = f.read()

    result = parse_toplist(html)
    assert isinstance(result, TopListResponse)

    assert len(result.gallery.all_time) == 1
    assert result.gallery.all_time[0].name == "Gallery 1"
    assert result.gallery.all_time[0].href == "/g/1/abc"

    assert len(result.gallery.past_year) == 1
    assert result.gallery.past_year[0].name == "Gallery 2"

    assert len(result.gallery.past_month) == 1
    assert result.gallery.past_month[0].name == "Gallery 3"

    assert len(result.gallery.yesterday) == 1
    assert result.gallery.yesterday[0].name == "Gallery 4"

    assert len(result.uploader.all_time) == 1
    assert result.uploader.all_time[0].name == "Uploader 1"
    assert result.uploader.all_time[0].href == "/u/1"

    assert len(result.uploader.yesterday) == 1
    assert result.uploader.yesterday[0].name == "Uploader 4"

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
    result = await api.get_toplist()

    # Just asserting it returns a TopListResponse and makes the correct API call
    assert isinstance(result, TopListResponse)
    assert mock_client.last_url == "https://e-hentai.org/toplist.php"
