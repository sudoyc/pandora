import hashlib
import re
from typing import Any, Callable, Optional, List, TypeVar

from exhentai_api.client import ExhentaiClient
from exhentai_api.parsers.gallery import parse_gallery_list
from exhentai_api.parsers.gallery_detail import parse_gallery_detail
from exhentai_api.parsers.image import parse_image_viewer, parse_image_api_response
from exhentai_api.parsers.favorites import parse_favorites_list
from exhentai_api.parsers.toplist import parse_toplist
from exhentai_api.parsers.comments import parse_comments
from exhentai_api.parsers.torrent import parse_torrent_list
from exhentai_api.parsers.archive import parse_archive_list
from exhentai_api.parsers.home import parse_home_detail
from exhentai_api.parsers.profile import parse_profile
from exhentai_api.parsers.mytags import parse_mytags
from exhentai_api.models.gallery import GalleryDetail, GalleryListItem
from exhentai_api.models.image import ImageDetail
from exhentai_api.models.search import SearchParams
from exhentai_api.models.favorites import FavoritesResponse
from exhentai_api.models.toplist import TopListItem
from exhentai_api.models.comment import GalleryComment
from exhentai_api.models.torrent import TorrentItem
from exhentai_api.models.archive import ArchiverData
from exhentai_api.models.home import HomeDetail
from exhentai_api.models.profile import ProfileResult
from exhentai_api.models.vote import RateResult, VoteCommentResult
from exhentai_api.models.tags import WatchedTag
from exhentai_api.constants import BASE_URL, HOME_URL
from exhentai_api.exceptions import ParseError


ParsedT = TypeVar("ParsedT")


def _parse_response(
    parser: Callable[..., ParsedT],
    *args: Any,
) -> ParsedT:
    try:
        return parser(*args)
    except ParseError:
        raise
    except Exception as exc:
        raise ParseError("Upstream response parse failed.") from exc


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

    # ── Existing methods (unchanged) ──────────────────────────────────

    async def get_homepage(self):
        html = await self.client.get_html(f"{BASE_URL}/")
        return _parse_response(parse_gallery_list, html)

    async def search(self, params: SearchParams, page: int = 0) -> list[GalleryListItem]:
        query_params = params.to_dict()
        if page > 0:
            query_params["page"] = str(page)

        html = await self.client.get_html(f"{BASE_URL}/", params=query_params)
        return _parse_response(parse_gallery_list, html)

    async def get_gallery_details(self, gid: str, token: str) -> GalleryDetail:
        url = f"{BASE_URL}/g/{gid}/{token}/"
        html = await self.client.get_html(url)
        return _parse_response(parse_gallery_detail, html, gid, token)

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
            image_url, new_nl = _parse_response(parse_image_api_response, json_resp)
            return ImageDetail(gid=str(gid), page=page, image_url=image_url, nl=new_nl)
        else:
            # Initial load from viewer page
            url = f"{BASE_URL}/s/{imgkey}/{gid}-{page}"
            html = await self.client.get_html(url)
            image_url, new_nl = _parse_response(parse_image_viewer, html)
            return ImageDetail(gid=str(gid), page=page, image_url=image_url, nl=new_nl)

    async def get_favorites(
        self,
        favcat: int = -1,
        page: int = 0,
        keyword: str = "",
        sn: bool = False,
        st: bool = False,
        sf: bool = False,
    ) -> FavoritesResponse:
        params = {}
        if favcat != -1:
            params["favcat"] = str(favcat)
        if page > 0:
            params["page"] = str(page)
        if keyword:
            params["f_search"] = keyword
            if sn:
                params["sn"] = "on"
            if st:
                params["st"] = "on"
            if sf:
                params["sf"] = "on"

        html = await self.client.get_html(f"{BASE_URL}/favorites.php", params=params if params else None)
        return _parse_response(parse_favorites_list, html)

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

    async def get_popular(self) -> List[GalleryListItem]:
        html = await self.client.get_html(f"{BASE_URL}/popular")
        return _parse_response(parse_gallery_list, html)

    async def get_toplist(self, tl: str = "15") -> List[TopListItem]:
        url = f"{BASE_URL}/toplist.php"
        params = {}
        if tl:
            params["tl"] = tl

        # Note: Toplist is only supported on e-hentai.org natively,
        # but spec requires f"{BASE_URL}/toplist.php?tl={tl}"
        html = await self.client.get_html(url, params=params if params else None)
        return _parse_response(parse_toplist, html)

    # ── New methods ───────────────────────────────────────────────────

    async def comment_gallery(
        self,
        gid: str,
        token: str,
        comment: str,
        edit_id: Optional[int] = None,
    ) -> list[GalleryComment]:
        """Post or edit a comment on a gallery. Returns updated comment list."""
        url = f"{BASE_URL}/g/{gid}/{token}/"
        data: dict = {"comment_text": comment}
        if edit_id is not None:
            data["edit_comment"] = str(edit_id)

        html = await self.client.post_form(url, data=data)
        comments, _ = _parse_response(parse_comments, html)
        return comments

    async def vote_comment(
        self,
        api_uid: str,
        api_key: str,
        gid: int,
        token: str,
        comment_id: int,
        vote: int,
    ) -> VoteCommentResult:
        """Vote on a comment. vote should be 1 (up) or -1 (down)."""
        payload = {
            "method": "votecomment",
            "apiuid": api_uid,
            "apikey": api_key,
            "gid": gid,
            "token": token,
            "comment_id": comment_id,
            "comment_vote": vote,
        }
        resp = await self.client.post_json(f"{BASE_URL}/api.php", json=payload)
        return VoteCommentResult(
            comment_id=resp.get("comment_id", 0),
            comment_score=resp.get("comment_score", 0),
            comment_vote=resp.get("comment_vote", 0),
        )

    async def rate_gallery(
        self,
        api_uid: str,
        api_key: str,
        gid: int,
        token: str,
        rating: int,
    ) -> RateResult:
        """Rate a gallery. rating is an integer (e.g. 2-10, representing 1-5 stars in 0.5 steps)."""
        payload = {
            "method": "rategallery",
            "apiuid": api_uid,
            "apikey": api_key,
            "gid": gid,
            "token": token,
            "rating": rating,
        }
        resp = await self.client.post_json(f"{BASE_URL}/api.php", json=payload)
        return RateResult(
            rating=resp.get("rating_avg", 0.0),
            rating_count=resp.get("rating_cnt", 0),
        )

    async def get_torrent_list(self, gid: str, token: str) -> list[TorrentItem]:
        """Fetch the list of available torrents for a gallery."""
        url = f"{BASE_URL}/gallerytorrents.php?gid={gid}&t={token}"
        html = await self.client.get_html(url)
        return _parse_response(parse_torrent_list, html)

    async def get_archive_list(self, gid: str, token: str) -> ArchiverData:
        """Fetch archive download options for a gallery."""
        url = f"{BASE_URL}/archiver.php?gid={gid}&token={token}"
        html = await self.client.get_html(url)
        return _parse_response(parse_archive_list, html)

    async def download_archive(self, archive_url: str, resolution: str = "org") -> str:
        """Initiate an archive download and return the download URL.

        Args:
            archive_url: The archiver URL (from GalleryDetail.archive_url or ArchiverData).
            resolution: "org" for original, "res" for resample.

        Returns:
            The direct download URL string.
        """
        if resolution == "res":
            dlcheck = "Download Resample Archive"
        else:
            dlcheck = "Download Original Archive"

        data = {
            "dltype": resolution,
            "dlcheck": dlcheck,
        }
        html = await self.client.post_form(archive_url, data=data)

        match = re.search(r'href="(.+?)">Click Here To Start Downloading', html)
        if match:
            return match.group(1)
        return ""

    async def get_mytags(self) -> list[WatchedTag]:
        """Fetch the user's watched/hidden tag configuration."""
        html = await self.client.get_html(f"{BASE_URL}/mytags")
        return _parse_response(parse_mytags, html)

    async def add_tag(
        self,
        tag_name: str,
        watched: bool = False,
        hidden: bool = False,
        color: str = "",
        weight: int = 0,
    ) -> list[WatchedTag]:
        """Add a new watched/hidden tag. Returns updated tag list."""
        data = {
            "tagname_new": tag_name,
            "tagwatch_new": "on" if watched else "",
            "taghide_new": "on" if hidden else "",
            "tagcolor_new": color,
            "tagweight_new": str(weight),
            "usertags_action": "add",
        }
        html = await self.client.post_form(f"{BASE_URL}/mytags", data=data)
        return _parse_response(parse_mytags, html)

    async def delete_tag(self, tag_id: int) -> list[WatchedTag]:
        """Delete a watched/hidden tag by ID. Returns updated tag list."""
        form_data = [
            ("usertags_action", "delete"),
            ("modify_usertags[]", str(tag_id)),
        ]
        html = await self.client.post_form(f"{BASE_URL}/mytags", data=form_data)
        return _parse_response(parse_mytags, html)

    async def get_watched(self, page: int = 0) -> list[GalleryListItem]:
        """Fetch galleries matching the user's watched tags."""
        params = None
        if page > 0:
            params = {"page": str(page)}

        html = await self.client.get_html(f"{BASE_URL}/watched", params=params)
        return _parse_response(parse_gallery_list, html)

    async def get_home_detail(self) -> HomeDetail:
        """Fetch the user's home page with image limits and GP stats."""
        html = await self.client.get_html(HOME_URL)
        return _parse_response(parse_home_detail, html)

    async def reset_image_limit(self) -> HomeDetail:
        """Reset the image viewing limit by spending GP. Returns updated home detail."""
        html = await self.client.post_form(
            HOME_URL,
            data={"reset_imagelimit": "Reset Limit"},
        )
        return _parse_response(parse_home_detail, html)

    async def get_profile(self) -> ProfileResult:
        """Fetch the current user's profile (display name, avatar).

        First fetches the forums index to find the profile link, then
        fetches the actual profile page.
        """
        forums_url = "https://forums.e-hentai.org/index.php"
        html = await self.client.get_html(forums_url)

        # Extract profile link from forums page
        match = re.search(r'href="(https://forums\.e-hentai\.org/index\.php\?showuser=\d+)"', html)
        if not match:
            return ProfileResult()

        profile_url = match.group(1)
        profile_html = await self.client.get_html(profile_url)
        return _parse_response(parse_profile, profile_html)

    async def get_gallery_token(self, gid: int, imgkey: str, page: int) -> str:
        """Fetch the gallery token for a specific page using the gtoken API.

        Returns the token string.
        """
        payload = {
            "method": "gtoken",
            "pagelist": [[gid, imgkey, page]],
        }
        resp = await self.client.post_json(f"{BASE_URL}/api.php", json=payload)
        token_list = resp.get("tokenlist", [])
        if token_list:
            return token_list[0].get("token", "")
        return ""

    async def image_search(
        self,
        file_path: str,
        similar: bool = True,
        covers: bool = True,
        exp: bool = True,
    ) -> list[GalleryListItem]:
        """Search for galleries by image file (SHA1 hash-based).

        Args:
            file_path: Path to the image file on disk.
            similar: Search for similar galleries.
            covers: Search by cover images.
            exp: Include expunged galleries.

        Returns:
            List of matching galleries.
        """
        sha1 = hashlib.sha1()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                sha1.update(chunk)

        params: dict[str, str] = {
            "f_shash": sha1.hexdigest(),
        }
        if similar:
            params["fs_similar"] = "on"
        if covers:
            params["fs_covers"] = "on"
        if exp:
            params["fs_exp"] = "on"

        html = await self.client.get_html(f"{BASE_URL}/", params=params)
        return _parse_response(parse_gallery_list, html)
