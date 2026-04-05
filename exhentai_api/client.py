import asyncio
import httpx
import typing
from typing import Optional

from exhentai_api.exceptions import (
    AuthenticationError,
    ImageLimitError,
    GalleryNotFoundError,
    GalleryOffensiveError,
    NetworkError,
    ExhentaiError,
)

# Sentinel: exceptions that must never be retried
_NO_RETRY = (AuthenticationError, ImageLimitError, GalleryNotFoundError, GalleryOffensiveError)


class ExhentaiClient:
    def __init__(self, igneous: str = "", ipb_member_id: str = "",
                 proxy: str = "", timeout: int = 30):
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

        client_kwargs: dict = {
            "cookies": self.cookies,
            "headers": self.headers,
            "timeout": float(timeout),
            "follow_redirects": True,
        }
        if proxy:
            client_kwargs["proxy"] = proxy
        self.session = httpx.AsyncClient(**client_kwargs)

    async def aclose(self):
        await self.session.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.aclose()

    async def get_html(self, url: str, params: Optional[dict] = None, retries: int = 3, backoff_factor: float = 0.1) -> str:
        last_exception: Optional[Exception] = None
        for attempt in range(retries):
            try:
                response = await self.session.get(url, params=params)

                # 1. Sad Panda (200 with special Content-Disposition header)
                if 'inline; filename="sadpanda.jpg"' in response.headers.get("Content-Disposition", ""):
                    raise AuthenticationError(
                        "Received Sad Panda. Your cookies might be invalid or your IP is blocked."
                    )

                # 2. HTTP status errors (catches 509 and others)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code == 509:
                        raise ImageLimitError("Image viewing limit exceeded (HTTP 509).") from http_err
                    raise NetworkError(f"HTTP error: {http_err}") from http_err

                html = response.text

                # 3. HTML content checks
                if "kokomade" in html or "This gallery has been removed" in html or "pining for the fjords" in html:
                    raise GalleryNotFoundError("Gallery is unavailable or has been removed.")
                if "Content Warning" in html and "offensive" in html:
                    raise GalleryOffensiveError("Gallery has an offensive content warning.")

                return html

            except _NO_RETRY:
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                wrapped = NetworkError(f"Network error: {e}")
                wrapped.__cause__ = e
                last_exception = wrapped
            except NetworkError as e:
                last_exception = e
            except Exception as e:
                wrapped = NetworkError(f"Unexpected error: {e}")
                wrapped.__cause__ = e
                last_exception = wrapped

            if attempt < retries - 1:
                await asyncio.sleep(backoff_factor * (2 ** attempt))

        if last_exception:
            raise last_exception
        return ""

    async def post_json(self, url: str, json: dict, retries: int = 3, backoff_factor: float = 0.1) -> dict:
        last_exception: Optional[Exception] = None
        for attempt in range(retries):
            try:
                response = await self.session.post(url, json=json)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code == 509:
                        raise ImageLimitError("Image viewing limit exceeded (HTTP 509).") from http_err
                    raise NetworkError(f"HTTP error: {http_err}") from http_err
                return response.json()
            except _NO_RETRY:
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                wrapped = NetworkError(f"Network error: {e}")
                wrapped.__cause__ = e
                last_exception = wrapped
            except NetworkError as e:
                last_exception = e
            except Exception as e:
                wrapped = NetworkError(f"Unexpected error: {e}")
                wrapped.__cause__ = e
                last_exception = wrapped

            if attempt < retries - 1:
                await asyncio.sleep(backoff_factor * (2 ** attempt))

        if last_exception:
            raise last_exception
        return {}

    async def post_form(self, url: str, data: typing.Union[dict, typing.List[typing.Tuple[str, str]]], retries: int = 3, backoff_factor: float = 0.1) -> str:
        last_exception: Optional[Exception] = None
        for attempt in range(retries):
            try:
                response = await self.session.post(url, data=data)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as http_err:
                    if http_err.response.status_code == 509:
                        raise ImageLimitError("Image viewing limit exceeded (HTTP 509).") from http_err
                    raise NetworkError(f"HTTP error: {http_err}") from http_err
                return response.text
            except _NO_RETRY:
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                wrapped = NetworkError(f"Network error: {e}")
                wrapped.__cause__ = e
                last_exception = wrapped
            except NetworkError as e:
                last_exception = e
            except Exception as e:
                wrapped = NetworkError(f"Unexpected error: {e}")
                wrapped.__cause__ = e
                last_exception = wrapped

            if attempt < retries - 1:
                await asyncio.sleep(backoff_factor * (2 ** attempt))

        if last_exception:
            raise last_exception
        return ""
