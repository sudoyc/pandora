from pathlib import Path

import pytest

from exhentai_api.exceptions import ParseError
from exhentai_api.parsers.gallery import parse_gallery_list
from exhentai_api.parsers.home import parse_home_detail


DATA = Path(__file__).parent / "data"


def _fixture(name: str) -> str:
    return (DATA / name).read_text(encoding="utf-8")


def test_current_homepage_fixture_parses_gallery_rows():
    items = parse_gallery_list(_fixture("homepage_2026_07_24.html"))

    assert [(item.gid, item.token, item.title) for item in items] == [
        ("100001", "aaaaaaaaaa", "Fixture Homepage Gallery 1"),
        ("100002", "bbbbbbbbbb", "Fixture Homepage Gallery 2"),
    ]
    assert items[0].category == "Manga"
    assert items[0].uploader == "fixture_uploader_1"
    assert items[0].thumb_url == "https://example.test/homepage-thumb-1.jpg"


def test_current_search_fixture_is_a_legitimate_empty_result():
    assert parse_gallery_list(_fixture("search_empty_2026_07_24.html")) == []


def test_current_popular_fixture_parses_gallery_rows():
    items = parse_gallery_list(_fixture("popular_2026_07_24.html"))

    assert [(item.gid, item.token, item.title) for item in items] == [
        ("200001", "aaaaaaaaaa", "Fixture Popular Gallery 1"),
        ("200002", "bbbbbbbbbb", "Fixture Popular Gallery 2"),
    ]
    assert items[1].category == "Doujinshi"
    assert items[1].uploader == "fixture_uploader_2"
    assert items[1].thumb_url == "https://example.test/popular-thumb-2.jpg"


def test_unrecognized_gallery_page_is_not_reported_as_empty():
    with pytest.raises(ParseError, match="gallery list structure changed"):
        parse_gallery_list("<html><body><main>Unexpected response</main></body></html>")


def test_current_home_fixture_parses_account_statistics():
    detail = parse_home_detail(_fixture("home_2026_07_24.html"))

    assert detail.image_used == 0
    assert detail.image_total == 0
    assert detail.reset_cost == 100
    assert detail.gp_from_gallery == 10000
    assert detail.gp_from_torrent == 5000
    assert detail.gp_from_archive == 2000
    assert detail.gp_from_hath == 1000
    assert detail.moderation_power == 42
