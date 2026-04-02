from exhentai_api.client import ExhentaiClient
from exhentai_api.parsers.gallery import parse_gallery_list
from exhentai_api.constants import BASE_URL

class ExhentaiAPI:
    def __init__(self, client: ExhentaiClient = None):
        self.client = client or ExhentaiClient()
        
    async def get_homepage(self):
        html = await self.client.get_html(f"{BASE_URL}/")
        return parse_gallery_list(html)
