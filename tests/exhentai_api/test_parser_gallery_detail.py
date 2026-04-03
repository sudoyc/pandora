from pathlib import Path
from exhentai_api.parsers.gallery_detail import parse_gallery_detail

def test_parse_gallery_detail():
    html_path = Path(__file__).parent / "data" / "gallery_detail.html"
    html = html_path.read_text()

    detail = parse_gallery_detail(html, "12345", "abcdef1234")

    assert detail.gid == "12345"
    assert detail.token == "abcdef1234"
    assert detail.title == "Test Gallery Title"
    assert detail.title_jpn == "Test Gallery Title JPN"
    assert detail.category == "Manga"
    assert detail.uploader == "UploaderName"
    assert detail.cover_url == "https://example.com/cover.jpg"
    assert detail.tags == {"parody": ["tag1", "tag2"]}
    assert detail.pages == 20
    assert detail.size == "100 MB"
    assert detail.posted == "2023-01-01 12:00"
    assert detail.favorite_slot == 0  # Assuming favorited if not 'Add to Favorites'
    assert detail.preview_pages == 3