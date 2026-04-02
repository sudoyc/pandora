import httpx

class ExhentaiClient:
    def __init__(self, igneous: str = "", ipb_member_id: str = ""):
        self.cookies = {}
        if igneous:
            self.cookies["igneous"] = igneous
        if ipb_member_id:
            self.cookies["ipb_member_id"] = ipb_member_id

        self.session = httpx.AsyncClient(cookies=self.cookies)

    async def get_html(self, url: str) -> str:
        response = await self.session.get(url)
        response.raise_for_status()
        return response.text
