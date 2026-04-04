from bs4 import BeautifulSoup
from exhentai_api.parsers.gallery import parse_gallery_list

def test_parse_gallery_list():
    with open("tests/exhentai_api/data/gallery_list.html", "r") as f:
        html = f.read()

    items = parse_gallery_list(html)
    assert len(items) == 5

    # Test item 1: Standard data-src thumbnail and regular date
    assert items[0].gid == "12345"
    assert items[0].token == "abcdef1234"
    assert items[0].title == "Test Title"
    assert items[0].category == "Manga"
    assert items[0].uploader == "uploader_name"
    assert items[0].thumb_url == "http://thumb.jpg"
    assert items[0].posted == "2023-01-01 12:00"

    # Test item 2: Fallback to src thumbnail and posted_ id date
    assert items[1].gid == "67890"
    assert items[1].token == "abcdef5678"
    assert items[1].title == "Another Title"
    assert items[1].thumb_url == "http://thumb2.jpg"
    assert items[1].posted == "2023-01-02 14:30"

    # Test item 3: Missing elements handling
    assert items[2].gid == "11111"
    assert items[2].token == "abcdef1111"
    assert items[2].title == "Missing Data Title"
    assert items[2].thumb_url == ""
    assert items[2].posted == ""

    # Test item 4: Missing href skips token parsing
    assert items[3].gid == "22222"
    assert items[3].token == "abcdef2222"

    # Test item 5: Unitless zero in background-position (e.g. "0 -21px")
    assert items[4].gid == "33333"
    assert items[4].token == "abcdef3333"
    assert items[4].title == "Unitless Zero Title"


def test_parse_gallery_list_rating_and_pages():
    with open("tests/exhentai_api/data/gallery_list.html", "r") as f:
        html = f.read()

    items = parse_gallery_list(html)

    # Item 1: ir irr with background-position:-16px -1px
    # Formula: 5 - (16/16) = 4.0, y != 21 so no -0.5, irr => rated=True
    assert items[0].rating == 4.0
    assert items[0].rated is True
    assert items[0].pages == 123
    assert items[0].thumb_width == 150
    assert items[0].thumb_height == 200

    # Item 2: ir with background-position:0px -21px
    # Formula: 5 - (0/16) = 5.0, y == 21 so -0.5 => 4.5, no irr/irg/irb => rated=False
    assert items[1].rating == 4.5
    assert items[1].rated is False
    assert items[1].pages == 45
    assert items[1].thumb_width == 130
    assert items[1].thumb_height == 180

    # Item 3: No rating element => defaults
    assert items[2].rating == 0.0
    assert items[2].rated is False
    assert items[2].pages == 0
    assert items[2].thumb_width == 0
    assert items[2].thumb_height == 0

    # Item 5 (index 4): Unitless zero "background-position:0 -21px"
    # Formula: 5 - (0/16) = 5.0, y == 21 so -0.5 => 4.5, irg => rated=True
    assert items[4].rating == 4.5
    assert items[4].rated is True
    assert items[4].pages == 77
    assert items[4].thumb_width == 140
    assert items[4].thumb_height == 190