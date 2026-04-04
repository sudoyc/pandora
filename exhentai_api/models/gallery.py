from dataclasses import dataclass, field
from typing import Optional, Dict, List
from exhentai_api.constants import BASE_URL


@dataclass
class ThumbSprite:
    """A single thumbnail extracted from a CSS sprite sheet."""
    url: str       # Sprite image URL
    offset_x: int  # CSS background-position x (pixels, positive = crop from left)
    offset_y: int  # CSS background-position y (pixels, positive = crop from top)
    width: int     # Thumbnail width in pixels
    height: int    # Thumbnail height in pixels


@dataclass
class GalleryListItem:
    gid: str
    token: str
    title: str
    category: str
    uploader: str
    thumb_url: str
    posted: str
    rating: float = 0.0
    pages: int = 0
    rated: bool = False
    thumb_width: int = 0
    thumb_height: int = 0

    @property
    def url(self) -> str:
        return f"{BASE_URL}/g/{self.gid}/{self.token}/"

@dataclass
class GalleryDetail:
    gid: str
    token: str
    title: str
    title_jpn: Optional[str]
    category: str
    uploader: str
    cover_url: str
    tags: Dict[str, List[str]]
    pages: int
    size: str
    posted: str
    favorite_slot: Optional[int]
    preview_pages: int = 1
    preview_urls: List[str] = field(default_factory=list)
    thumb_urls: List[str] = field(default_factory=list)
    thumb_sprites: List[ThumbSprite] = field(default_factory=list)
    rating: float = 0.0
    rating_count: int = 0
    favorite_count: int = 0
    torrent_count: int = 0
    torrent_url: str = ""
    archive_url: str = ""
    parent_url: Optional[str] = None
    newer_versions: List[dict] = field(default_factory=list)
    comments: list = field(default_factory=list)
    comments_has_more: bool = False
    api_uid: str = ""
    api_key: str = ""

    @property
    def url(self) -> str:
        return f"{BASE_URL}/g/{self.gid}/{self.token}/"
