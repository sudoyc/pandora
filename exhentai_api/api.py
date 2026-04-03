from typing import Optional
from exhentai_api.client import ExhentaiClient
from exhentai_api.parsers.gallery import parse_gallery_list
from exhentai_api.parsers.gallery_detail import parse_gallery_detail
from exhentai_api.models.gallery import GalleryDetail
from exhentai_api.constants import BASE_URL

class ExhentaiAPI:
    def __init__(self, client: Optional[ExhentaiClient] = None):
        self._owns_client = client is None
        self.client = client or ExhentaiClient()

    async def aclose(self):
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def get_homepage(self):
        html = await self.client.get_html(f"{BASE_URL}/")
        return parse_gallery_list(html)

    async def get_gallery_details(self, gid: str, token: str) -> GalleryDetail:
        url = f"{BASE_URL}/g/{gid}/{token}/"
        html = await self.client.get_html(url)
        return parse_gallery_detail(html, gid, token)
