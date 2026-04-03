import asyncio
import httpx
from typing import Optional

class ExhentaiClient:
    def __init__(self, igneous: str = "", ipb_member_id: str = ""):
        self.cookies = {}
        if igneous:
            self.cookies["igneous"] = igneous
        if ipb_member_id:
            self.cookies["ipb_member_id"] = ipb_member_id

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        }

        self.session = httpx.AsyncClient(cookies=self.cookies, headers=self.headers, timeout=30.0)

    async def aclose(self):
        await self.session.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def get_html(self, url: str, retries: int = 3, backoff_factor: float = 0.1) -> str:
        last_exception = None
        for attempt in range(retries):
            try:
                response = await self.session.get(url)
                response.raise_for_status()

                # Check for sad panda
                if 'inline; filename="sadpanda.jpg"' in response.headers.get("Content-Disposition", ""):
                    raise Exception("Received Sad Panda. Your cookies might be invalid or your IP is blocked.")

                return response.text
            except Exception as e:
                # If it's a sad panda, don't retry, just raise immediately
                if "Sad Panda" in str(e):
                    raise
                last_exception = e
                if attempt < retries - 1:
                    await asyncio.sleep(backoff_factor * (2 ** attempt))

        if last_exception:
            raise last_exception

        return ""

    async def post_json(self, url: str, json: dict, retries: int = 3, backoff_factor: float = 0.1) -> dict:
        last_exception = None
        for attempt in range(retries):
            try:
                response = await self.session.post(url, json=json)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                last_exception = e
                if attempt < retries - 1:
                    await asyncio.sleep(backoff_factor * (2 ** attempt))

        if last_exception:
            raise last_exception
        return {}
