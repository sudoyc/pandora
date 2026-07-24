import asyncio
import httpx
import typing
from typing import Optional

from exhentai_api.exceptions import (
    AuthenticationError,
    SessionError,
    UpstreamError,
    ImageLimitError,
    GalleryNotFoundError,
    GalleryOffensiveError,
    NetworkError,
    ParseError,
    ExhentaiError,
)

# Sentinel: exceptions that must never be retried
_NO_RETRY = (AuthenticationError, ImageLimitError, GalleryNotFoundError, GalleryOffensiveError)
_SESSION_ERROR_MESSAGE = "Sad Panda response indicates an invalid upstream session."
_NETWORK_ERROR_MESSAGE = "Network error while requesting the upstream service."


def _raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 509:
            raise ImageLimitError("Image viewing limit exceeded.") from exc
        if status_code == 401:
            raise SessionError(_SESSION_ERROR_MESSAGE) from exc
        raise UpstreamError(status_code=status_code) from exc


class ExhentaiClient:
    def __init__(self, igneous: str = "", ipb_member_id: str = "",
                 ipb_pass_hash: str = "", proxy: str = "", timeout: int = 30):
        self.cookies = {}
        if igneous:
            self.cookies["igneous"] = igneous
        if ipb_member_id:
            self.cookies["ipb_member_id"] = ipb_member_id
        if ipb_pass_hash:
            self.cookies["ipb_pass_hash"] = ipb_pass_hash

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
                    raise SessionError(_SESSION_ERROR_MESSAGE)

                # 2. HTTP status errors (catches 509 and others)
                _raise_for_status(response)

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
                wrapped = NetworkError(_NETWORK_ERROR_MESSAGE)
                wrapped.__cause__ = e
                last_exception = wrapped
            except (NetworkError, UpstreamError, ParseError) as e:
                last_exception = e
            except Exception as e:
                wrapped = NetworkError("Unexpected upstream client failure.")
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
                _raise_for_status(response)
                try:
                    return response.json()
                except ValueError as exc:
                    raise ParseError("Upstream response parse failed.") from exc
            except _NO_RETRY:
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                wrapped = NetworkError(_NETWORK_ERROR_MESSAGE)
                wrapped.__cause__ = e
                last_exception = wrapped
            except (NetworkError, UpstreamError, ParseError) as e:
                last_exception = e
            except Exception as e:
                wrapped = NetworkError("Unexpected upstream client failure.")
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
                _raise_for_status(response)
                return response.text
            except _NO_RETRY:
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                wrapped = NetworkError(_NETWORK_ERROR_MESSAGE)
                wrapped.__cause__ = e
                last_exception = wrapped
            except (NetworkError, UpstreamError, ParseError) as e:
                last_exception = e
            except Exception as e:
                wrapped = NetworkError("Unexpected upstream client failure.")
                wrapped.__cause__ = e
                last_exception = wrapped

            if attempt < retries - 1:
                await asyncio.sleep(backoff_factor * (2 ** attempt))

        if last_exception:
            raise last_exception
        return ""
