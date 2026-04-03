import pytest
from exhentai_api.models.search import SearchParams
from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from unittest.mock import AsyncMock, patch

def test_search_params_basic():
    params = SearchParams(f_search="test query")
    d = params.to_dict()
    assert d == {"f_search": "test query"}

def test_search_params_advanced():
    params = SearchParams(
        f_search="test",
        f_cats=1,
        advsearch=True,
        f_sname=True,
        f_stags=True,
        f_sr=True,
        f_srdd=4,
        f_sp=True,
        f_spf=10,
        f_spt=20,
        f_sh=True
    )
    d = params.to_dict()
    assert d == {
        "f_search": "test",
        "f_cats": "1",
        "advsearch": "1",
        "f_sname": "on",
        "f_stags": "on",
        "f_sr": "on",
        "f_srdd": "4",
        "f_sp": "on",
        "f_spf": "10",
        "f_spt": "20",
        "f_sh": "on"
    }

@pytest.mark.asyncio
async def test_search_api():
    client = ExhentaiClient()
    client.get_html = AsyncMock(return_value="<html></html>")

    with patch("exhentai_api.api.parse_gallery_list", return_value=[]):
        api = ExhentaiAPI(client=client)

        # Test basic search
        params = SearchParams(f_search="hello")
        await api.search(params)

        client.get_html.assert_called_with("https://exhentai.org/", params={"f_search": "hello"})

        # Test with category bitmask (1 represents the category we want)
        # ~1 & 1023 -> 1022
        params = SearchParams(f_search="test", f_cats=1)
        await api.search(params, page=2)

        client.get_html.assert_called_with(
            "https://exhentai.org/",
            params={"f_search": "test", "f_cats": "1022", "page": "2"}
        )
