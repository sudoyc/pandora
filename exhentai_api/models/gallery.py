from dataclasses import dataclass
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
