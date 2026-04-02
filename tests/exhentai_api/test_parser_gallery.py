from bs4 import BeautifulSoup
from exhentai_api.parsers.gallery import parse_gallery_list

def test_parse_gallery_list():
    with open("tests/exhentai_api/data/gallery_list.html", "r") as f:
        html = f.read()

    items = parse_gallery_list(html)
    assert len(items) == 4

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