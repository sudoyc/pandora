from exhentai_api.models.gallery import GalleryListItem

def test_gallery_list_item():
    item = GalleryListItem(
        gid="123",
        token="abc",
        title="Test Gallery",
        category="Manga",
        uploader="testuser",
        thumb_url="http://example.com/thumb.jpg",
        posted="2023-01-01 12:00"
    )
    assert item.url == "https://exhentai.org/g/123/abc/"
