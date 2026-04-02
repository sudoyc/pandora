from exhentai_api.utils import extract_gallery_token
import pytest

def test_extract_gallery_token():
    url = "https://exhentai.org/g/1234567/abcdef1234/"
    gid, token = extract_gallery_token(url)
    assert gid == "1234567"
    assert token == "abcdef1234"

def test_extract_gallery_token_invalid():
    url = "https://exhentai.org/invalid/url"
    with pytest.raises(ValueError, match=f"Invalid gallery URL: {url}"):
        extract_gallery_token(url)
