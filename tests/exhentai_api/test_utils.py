from exhentai_api.utils import extract_gallery_token

def test_extract_gallery_token():
    url = "https://exhentai.org/g/1234567/abcdef1234/"
    gid, token = extract_gallery_token(url)
    assert gid == "1234567"
    assert token == "abcdef1234"
