from exhentai_api.models import GalleryListItem, GalleryDetail, Tag, WatchedTag, ImageDetail

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

def test_gallery_detail():
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
        favorite_slot=1
    )
    assert detail.url == "https://exhentai.org/g/456/def/"
    assert detail.title_jpn == "テストギャラリー"
    assert detail.tags["artist"] == ["test artist"]

def test_tag():
    tag = Tag(namespace="artist", name="some artist")
    assert tag.namespace == "artist"
    assert tag.name == "some artist"

def test_watched_tag():
    watched_tag = WatchedTag(
        id=1,
        name="some tag",
        watched=True,
        hidden=False,
        color="#ff0000",
        weight=10
    )
    assert watched_tag.id == 1
    assert watched_tag.name == "some tag"
    assert watched_tag.watched is True

def test_image_detail():
    image = ImageDetail(
        gid="123",
        page=1,
        image_url="http://example.com/img/1.jpg",
        nl="xyz123"
    )
    assert image.gid == "123"
    assert image.page == 1
    assert image.image_url == "http://example.com/img/1.jpg"
