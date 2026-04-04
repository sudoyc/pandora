import pytest
from pandora_daemon.cli import parse_gallery_url, build_daemon_url


def test_parse_gallery_url_standard():
    gid, token = parse_gallery_url("https://exhentai.org/g/1234567/a1b2c3d4e5/")
    assert gid == "1234567"
    assert token == "a1b2c3d4e5"


def test_parse_gallery_url_e_hentai():
    gid, token = parse_gallery_url("https://e-hentai.org/g/9999/abcdef0123/")
    assert gid == "9999"
    assert token == "abcdef0123"


def test_parse_gallery_url_invalid():
    with pytest.raises(ValueError, match="Invalid gallery URL"):
        parse_gallery_url("https://example.com/not/a/gallery")


def test_build_daemon_url_default():
    url = build_daemon_url("127.0.0.1", 7860)
    assert url == "http://127.0.0.1:7860"


def test_build_daemon_url_custom():
    url = build_daemon_url("0.0.0.0", 8080)
    assert url == "http://0.0.0.0:8080"
