from bs4 import BeautifulSoup
from exhentai_api.parsers.gallery import parse_gallery_list

def test_parse_gallery_list():
    with open("tests/exhentai_api/data/gallery_list.html", "r") as f:
        html = f.read()

    items = parse_gallery_list(html)
    assert len(items) == 1
    assert items[0].gid == "12345"
    assert items[0].token == "abcdef1234"
    assert items[0].title == "Test Title"
    assert items[0].category == "Manga"
    assert items[0].uploader == "uploader_name"