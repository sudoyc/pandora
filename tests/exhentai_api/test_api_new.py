import pytest
from unittest.mock import AsyncMock
from exhentai_api.api import ExhentaiAPI
from exhentai_api.constants import BASE_URL


@pytest.mark.asyncio
async def test_comment_gallery():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = '<div id="cdiv"><a name="c1"></a><div class="c1"><div class="c3">Posted on 01 January 2024, 12:00 by: <a>user</a></div><div class="c6">test</div></div></div>'
    api = ExhentaiAPI(client=mock_client)
    comments = await api.comment_gallery("123", "abc", "Hello!")
    mock_client.post_form.assert_called_once()
    call_args = mock_client.post_form.call_args
    assert call_args[0][0] == f"{BASE_URL}/g/123/abc/"
    assert call_args[1]["data"]["comment_text"] == "Hello!"


@pytest.mark.asyncio
async def test_comment_gallery_edit():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = '<div id="cdiv"></div>'
    api = ExhentaiAPI(client=mock_client)
    await api.comment_gallery("123", "abc", "Edited!", edit_id=456)
    call_data = mock_client.post_form.call_args[1]["data"]
    assert call_data["edit_comment"] == "456"


@pytest.mark.asyncio
async def test_vote_comment():
    mock_client = AsyncMock()
    mock_client.post_json.return_value = {"comment_id": 99, "comment_score": -3, "comment_vote": 1}
    api = ExhentaiAPI(client=mock_client)
    result = await api.vote_comment("uid1", "key1", 123, "abc", 99, 1)
    assert result.comment_id == 99
    assert result.comment_score == -3
    assert result.comment_vote == 1
    mock_client.post_json.assert_called_once_with(
        f"{BASE_URL}/api.php",
        json={"method": "votecomment", "apiuid": "uid1", "apikey": "key1", "gid": 123, "token": "abc", "comment_id": 99, "comment_vote": 1},
    )


@pytest.mark.asyncio
async def test_rate_gallery():
    mock_client = AsyncMock()
    mock_client.post_json.return_value = {"rating_avg": 4.5, "rating_cnt": 100}
    api = ExhentaiAPI(client=mock_client)
    result = await api.rate_gallery("uid1", "key1", 123, "abc", 8)
    assert result.rating == 4.5
    assert result.rating_count == 100
    mock_client.post_json.assert_called_once_with(
        f"{BASE_URL}/api.php",
        json={"method": "rategallery", "apiuid": "uid1", "apikey": "key1", "gid": 123, "token": "abc", "rating": 8},
    )


@pytest.mark.asyncio
async def test_get_torrent_list():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<table><tr><td colspan="5"> &nbsp; <a href="https://ex.com/t.torrent">name.torrent</a></td></tr></table>'
    api = ExhentaiAPI(client=mock_client)
    items = await api.get_torrent_list("123", "abc")
    assert len(items) == 1
    assert items[0].name == "name.torrent"
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/gallerytorrents.php?gid=123&t=abc")


@pytest.mark.asyncio
async def test_get_archive_list():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)
    data = await api.get_archive_list("123", "abc")
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/archiver.php?gid=123&token=abc")


@pytest.mark.asyncio
async def test_download_archive():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = 'blah blah <a href="https://ex.com/download/archive.zip">Click Here To Start Downloading</a> blah'
    api = ExhentaiAPI(client=mock_client)
    url = await api.download_archive("https://ex.com/archiver.php?or=xxx", resolution="org")
    assert url == "https://ex.com/download/archive.zip"
    call_args = mock_client.post_form.call_args
    assert call_args[0][0] == "https://ex.com/archiver.php?or=xxx"
    assert call_args[1]["data"]["dltype"] == "org"
    assert call_args[1]["data"]["dlcheck"] == "Download Original Archive"


@pytest.mark.asyncio
async def test_download_archive_resample():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = 'blah <a href="https://ex.com/download/resample.zip">Click Here To Start Downloading</a>'
    api = ExhentaiAPI(client=mock_client)
    url = await api.download_archive("https://ex.com/archiver.php?or=xxx", resolution="res")
    assert url == "https://ex.com/download/resample.zip"
    call_args = mock_client.post_form.call_args
    assert call_args[1]["data"]["dltype"] == "res"
    assert call_args[1]["data"]["dlcheck"] == "Download Resample Archive"


@pytest.mark.asyncio
async def test_get_mytags():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)
    tags = await api.get_mytags()
    assert tags == []
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/mytags")


@pytest.mark.asyncio
async def test_add_tag():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)
    tags = await api.add_tag("artist:test", watched=True, hidden=False, color="#ff0000", weight=10)
    assert tags == []
    call_args = mock_client.post_form.call_args
    assert call_args[0][0] == f"{BASE_URL}/mytags"


@pytest.mark.asyncio
async def test_delete_tag():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)
    tags = await api.delete_tag(42)
    assert tags == []
    call_args = mock_client.post_form.call_args
    assert call_args[0][0] == f"{BASE_URL}/mytags"


@pytest.mark.asyncio
async def test_get_watched():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<table class="itg"></table>'
    api = ExhentaiAPI(client=mock_client)
    items = await api.get_watched(page=2)
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/watched", params={"page": "2"})


@pytest.mark.asyncio
async def test_get_watched_default():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<table class="itg"></table>'
    api = ExhentaiAPI(client=mock_client)
    items = await api.get_watched()
    mock_client.get_html.assert_called_once_with(f"{BASE_URL}/watched", params=None)


@pytest.mark.asyncio
async def test_get_home_detail():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)
    detail = await api.get_home_detail()
    assert detail.image_used == 0
    mock_client.get_html.assert_called_once_with("https://e-hentai.org/home.php")


@pytest.mark.asyncio
async def test_reset_image_limit():
    mock_client = AsyncMock()
    mock_client.post_form.return_value = "<html><body></body></html>"
    api = ExhentaiAPI(client=mock_client)
    detail = await api.reset_image_limit()
    mock_client.post_form.assert_called_once_with(
        "https://e-hentai.org/home.php", data={"reset_imagelimit": "Reset Limit"},
    )


@pytest.mark.asyncio
async def test_get_gallery_token():
    mock_client = AsyncMock()
    mock_client.post_json.return_value = {"tokenlist": [{"gid": 123, "token": "abcdef1234"}]}
    api = ExhentaiAPI(client=mock_client)
    token = await api.get_gallery_token(123, "imgkey1", 5)
    assert token == "abcdef1234"


@pytest.mark.asyncio
async def test_get_gallery_token_payload():
    mock_client = AsyncMock()
    mock_client.post_json.return_value = {"tokenlist": [{"gid": 99, "token": "tok123"}]}
    api = ExhentaiAPI(client=mock_client)
    await api.get_gallery_token(99, "key2", 3)
    mock_client.post_json.assert_called_once_with(
        f"{BASE_URL}/api.php",
        json={"method": "gtoken", "pagelist": [[99, "key2", 3]]},
    )


@pytest.mark.asyncio
async def test_image_search():
    """image_search computes SHA1 of the file and passes it as f_shash."""
    import tempfile
    import hashlib
    import os

    content = b"fake image data for testing"
    expected_sha1 = hashlib.sha1(content).hexdigest()

    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<table class="itg"></table>'
    api = ExhentaiAPI(client=mock_client)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        f.write(content)
        tmp_path = f.name

    try:
        items = await api.image_search(tmp_path, similar=True, covers=True, exp=True)
        call_args = mock_client.get_html.call_args
        params = call_args[1]["params"]
        assert params["f_shash"] == expected_sha1
        assert params["fs_similar"] == "on"
        assert params["fs_covers"] == "on"
        assert params["fs_exp"] == "on"
    finally:
        os.unlink(tmp_path)


@pytest.mark.asyncio
async def test_get_favorites_with_keyword():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<html><body>No hits found</body></html>'
    api = ExhentaiAPI(client=mock_client)
    await api.get_favorites(favcat=0, keyword="test", sn=True, st=True)
    call_args = mock_client.get_html.call_args
    params = call_args[1].get("params") or {}
    assert params.get("f_search") == "test"
    assert params.get("sn") == "on"
    assert params.get("st") == "on"


@pytest.mark.asyncio
async def test_get_favorites_with_sf():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<html><body>No hits found</body></html>'
    api = ExhentaiAPI(client=mock_client)
    await api.get_favorites(favcat=2, keyword="query", sf=True)
    call_args = mock_client.get_html.call_args
    params = call_args[1].get("params") or {}
    assert params.get("f_search") == "query"
    assert params.get("sf") == "on"
    assert params.get("favcat") == "2"


@pytest.mark.asyncio
async def test_get_favorites_no_keyword():
    """Existing behavior: no keyword params when keyword is empty."""
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<html><body>No hits found</body></html>'
    api = ExhentaiAPI(client=mock_client)
    await api.get_favorites(favcat=0, page=1)
    call_args = mock_client.get_html.call_args
    params = call_args[1].get("params") or {}
    assert "f_search" not in params
    assert "sn" not in params


@pytest.mark.asyncio
async def test_get_profile():
    mock_client = AsyncMock()
    # First call: forums page to extract profile link
    forums_html = '<a href="https://forums.e-hentai.org/index.php?showuser=12345">My Profile</a>'
    # Second call: actual profile page
    profile_html = '<div id="profilename"><span>TestUser</span></div>'
    mock_client.get_html.side_effect = [forums_html, profile_html]
    api = ExhentaiAPI(client=mock_client)
    result = await api.get_profile()
    assert result.display_name == "TestUser"
    assert mock_client.get_html.call_count == 2


@pytest.mark.asyncio
async def test_get_profile_no_link():
    mock_client = AsyncMock()
    mock_client.get_html.return_value = '<html><body>No profile link here</body></html>'
    api = ExhentaiAPI(client=mock_client)
    result = await api.get_profile()
    # Should return empty ProfileResult when no profile link found
    assert result.display_name == ""
