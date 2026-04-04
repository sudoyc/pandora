from pathlib import Path
from exhentai_api.parsers.gallery_detail import parse_gallery_detail


def test_parse_gallery_detail():
    html_path = Path(__file__).parent / "data" / "gallery_detail.html"
    html = html_path.read_text()

    detail = parse_gallery_detail(html, "12345", "abcdef1234")

    # Existing assertions
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
    assert detail.favorite_slot == 0
    assert detail.preview_pages == 3

    # NEW field assertions
    assert detail.rating == 4.65
    assert detail.favorite_count == 42
    assert detail.torrent_count == 3
    assert "gallerytorrents.php" in detail.torrent_url
    assert "archiver.php" in detail.archive_url
    assert detail.api_uid == "12345"
    assert detail.api_key == "abcdef0123456789"

    # Comments
    assert len(detail.comments) == 2
    assert detail.comments[0].id == 100
    assert detail.comments[0].user == "TestUser"
    assert detail.comments[0].comment == "Great gallery!"
    assert detail.comments[0].vote_up_able is True
    assert detail.comments[0].vote_down_ed is True
    assert detail.comments[1].user == "Uploader"
    assert detail.comments[1].editable is True
    assert detail.comments[1].last_edited != ""

    # Newer versions
    assert len(detail.newer_versions) >= 1
    assert detail.newer_versions[0]["gid"] == "99999"
    assert detail.newer_versions[0]["token"] == "fedcba9876"

    # Rating count
    assert detail.rating_count == 150

    # Parent URL (no Parent row in fixture)
    assert detail.parent_url is None

    # Comments has-more flag (fixture says "All 5 comments", not "click to show all")
    assert detail.comments_has_more is False


def test_parse_gallery_detail_thumb_urls():
    html_path = Path(__file__).parent / "data" / "gallery_detail.html"
    html = html_path.read_text()

    detail = parse_gallery_detail(html, "12345", "abcdef1234")

    assert detail.thumb_urls == [
        "https://exhentai.org/t/thumb1.jpg",
        "https://exhentai.org/t/thumb2.jpg",
        "https://exhentai.org/t/thumb3.jpg",
    ]
