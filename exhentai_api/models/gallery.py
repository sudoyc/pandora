from dataclasses import dataclass, field
from typing import Optional, Dict, List
from exhentai_api.constants import BASE_URL

@dataclass
class GalleryListItem:
    gid: str
    token: str
    title: str
    category: str
    uploader: str
    thumb_url: str
    posted: str

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

    @property
    def url(self) -> str:
        return f"{BASE_URL}/g/{self.gid}/{self.token}/"
