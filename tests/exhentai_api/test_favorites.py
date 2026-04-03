import pytest
from unittest.mock import AsyncMock, patch
from exhentai_api.api import ExhentaiAPI
from exhentai_api.client import ExhentaiClient
from exhentai_api.parsers.favorites import parse_favorites_list

def test_parse_favorites_list():
    html = """
    <html>
        <body>
            <div class="ido">
                <div class="fp">
                    <span class="fp1">15</span>
                    <span class="some-separator"></span>
                    <span class="fp2">My Favs 1</span>
                </div>
                <div class="fp">
                    <span class="fp1">2</span>
                    <span class="some-separator"></span>
                    <span class="fp2">Special</span>
                </div>
            </div>
            <!-- mock standard gallery list -->
            <div class="itg">
                <tr>
                    <td class="gl3c"><a href="https://exhentai.org/g/123/0123456789/">Gallery</a></td>
                    <td class="glname">Test Gallery</td>
                </tr>
            </div>
        </body>
    </html>
    """

    resp = parse_favorites_list(html)

    # Test categories
    assert len(resp.categories) == 2

    assert resp.categories[0].slot == 0
    assert resp.categories[0].name == "My Favs 1"
    assert resp.categories[0].count == 15

    assert resp.categories[1].slot == 1
    assert resp.categories[1].name == "Special"
    assert resp.categories[1].count == 2

    # Test galleries fallback
    assert len(resp.galleries) == 1
    assert resp.galleries[0].gid == "123"
    assert resp.galleries[0].token == "0123456789"
    assert resp.galleries[0].title == "Test Gallery"

@pytest.mark.asyncio
async def test_get_favorites():
    client = ExhentaiClient()
    client.get_html = AsyncMock(return_value="<html></html>")

    with patch("exhentai_api.api.parse_favorites_list") as mock_parse:
        api = ExhentaiAPI(client=client)

        await api.get_favorites(favcat=2, page=1)

        client.get_html.assert_called_once_with(
            "https://exhentai.org/favorites.php",
            params={"favcat": "2", "page": "1"}
        )
        mock_parse.assert_called_once_with("<html></html>")

@pytest.mark.asyncio
async def test_add_favorite():
    client = ExhentaiClient()
    client.post_form = AsyncMock(return_value="Success")

    api = ExhentaiAPI(client=client)

    res = await api.add_favorite(gid="123", token="abc", favcat=5, favnote="Great")

    assert res == "Success"
    client.post_form.assert_called_once_with(
        "https://exhentai.org/gallerypopups.php?gid=123&t=abc&act=addfav",
        data={
            "favcat": "5",
            "favnote": "Great",
            "submit": "Apply Changes",
            "update": "1"
        }
    )

    # Test removal logic
    client.post_form.reset_mock()
    await api.add_favorite(gid="123", token="abc", favcat=-1)

    client.post_form.assert_called_once_with(
        "https://exhentai.org/gallerypopups.php?gid=123&t=abc&act=addfav",
        data={
            "favcat": "favdel",
            "favnote": "",
            "submit": "Apply Changes",
            "update": "1"
        }
    )

@pytest.mark.asyncio
async def test_modify_favorites():
    client = ExhentaiClient()
    client.post_form = AsyncMock(return_value="Success")

    api = ExhentaiAPI(client=client)

    res = await api.modify_favorites(gids=["123", "456"], ddact="delete")

    assert res == "Success"
    client.post_form.assert_called_once_with(
        "https://exhentai.org/favorites.php",
        data=[
            ("ddact", "delete"),
            ("apply", "Apply"),
            ("modifygids[]", "123"),
            ("modifygids[]", "456")
        ]
    )
