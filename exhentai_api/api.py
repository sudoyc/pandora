from typing import Optional, List
from exhentai_api.client import ExhentaiClient
from exhentai_api.parsers.gallery import parse_gallery_list
from exhentai_api.parsers.gallery_detail import parse_gallery_detail
from exhentai_api.parsers.image import parse_image_viewer, parse_image_api_response
from exhentai_api.parsers.favorites import parse_favorites_list
from exhentai_api.models.gallery import GalleryDetail, GalleryListItem
from exhentai_api.models.image import ImageDetail
from exhentai_api.models.search import SearchParams
from exhentai_api.models.favorites import FavoritesResponse
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

    async def search(self, params: SearchParams, page: int = 0) -> list[GalleryListItem]:
        query_params = params.to_dict()
        if page > 0:
            query_params["page"] = str(page)

        html = await self.client.get_html(f"{BASE_URL}/", params=query_params)
        return parse_gallery_list(html)

    async def get_gallery_details(self, gid: str, token: str) -> GalleryDetail:
        url = f"{BASE_URL}/g/{gid}/{token}/"
        html = await self.client.get_html(url)
        return parse_gallery_detail(html, gid, token)

    async def get_image_url(self, gid: str, imgkey: str, page: int, nl: Optional[str] = None) -> ImageDetail:
        if nl:
            # Use api.php to reload the image URL using the nl token
            payload = {
                "method": "showpage",
                "gid": gid,
                "page": str(page),
                "imgkey": imgkey,
                "showkey": nl
            }
            json_resp = await self.client.post_json(f"{BASE_URL}/api.php", json=payload)
            image_url, new_nl = parse_image_api_response(json_resp)
            return ImageDetail(gid=str(gid), page=page, image_url=image_url, nl=new_nl)
        else:
            # Initial load from viewer page
            url = f"{BASE_URL}/s/{imgkey}/{gid}-{page}"
            html = await self.client.get_html(url)
            image_url, new_nl = parse_image_viewer(html)
            return ImageDetail(gid=str(gid), page=page, image_url=image_url, nl=new_nl)

    async def get_favorites(self, favcat: int = -1, page: int = 0) -> FavoritesResponse:
        params = {}
        if favcat != -1:
            params["favcat"] = str(favcat)
        if page > 0:
            params["page"] = str(page)

        html = await self.client.get_html(f"{BASE_URL}/favorites.php", params=params if params else None)
        return parse_favorites_list(html)

    async def add_favorite(self, gid: str, token: str, favcat: int = 0, favnote: str = "") -> str:
        url = f"{BASE_URL}/gallerypopups.php?gid={gid}&t={token}&act=addfav"

        favcat_val = "favdel" if favcat == -1 else str(favcat)
        payload = {
            "favcat": favcat_val,
            "favnote": favnote,
            "submit": "Apply Changes",
            "update": "1"
        }

        return await self.client.post_form(url, data=payload)

    async def modify_favorites(self, gids: List[str], ddact: str) -> str:
        import re
        if ddact != "delete" and not re.match(r"^fav[0-9]$", ddact):
            raise ValueError("ddact must be 'delete' or 'fav[0-9]'")

        url = f"{BASE_URL}/favorites.php"

        payload = {
            "ddact": ddact,
            "apply": "Apply"
        }

        # httpx post_form with multiple identical keys requires a sequence of tuples
        # so we need to construct a list of tuples instead of a dict for this specific request
        form_data = list(payload.items())
        for gid in gids:
            form_data.append(("modifygids[]", str(gid)))

        return await self.client.post_form(url, data=form_data)
