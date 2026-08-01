from pandora_daemon.providers.exhentai.upstream.models import GalleryDetail, ImageDetail

def test_gallery_detail_model():
    detail = GalleryDetail(
        gid="456",
        token="def",
        title="Test Gallery Detail",
        title_jpn="テストギャラリー",
        category="Doujinshi",
        uploader="testuser2",
        cover_url="http://example.com/cover.jpg",
        tags={"artist": ["test artist"], "parody": ["test parody"]},
        pages=20,
        size="50 MB",
        posted="2023-01-02 12:00",
        favorite_slot=1,
        preview_pages=2
    )
    assert detail.url == "https://exhentai.org/g/456/def/"
    assert detail.title_jpn == "テストギャラリー"
    assert detail.tags["artist"] == ["test artist"]
    assert detail.preview_pages == 2

def test_image_detail_model():
    image = ImageDetail(
        gid="123",
        page=1,
        image_url="http://example.com/img/1.jpg",
        nl="xyz123"
    )
    assert image.gid == "123"
    assert image.page == 1
    assert image.image_url == "http://example.com/img/1.jpg"
    assert image.nl == "xyz123"
