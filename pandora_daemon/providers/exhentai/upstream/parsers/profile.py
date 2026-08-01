from bs4 import BeautifulSoup
from pandora_daemon.providers.exhentai.upstream.models.profile import ProfileResult


def parse_profile(html: str) -> ProfileResult:
    soup = BeautifulSoup(html, "html.parser")
    result = ProfileResult()

    profilename = soup.find(id="profilename")
    if profilename:
        first_child = profilename.find()
        if first_child:
            result.display_name = first_child.get_text(strip=True)
        else:
            result.display_name = profilename.get_text(strip=True)

        avatar_container = profilename.find_next_sibling()
        if avatar_container:
            avatar_container = avatar_container.find_next_sibling()
        if avatar_container:
            img = avatar_container.find("img")
            if img:
                result.avatar_url = img.get("src", "")

    if not result.display_name:
        userlinks = soup.find(id="userlinks")
        if userlinks:
            try:
                result.display_name = userlinks.find().find().find().get_text(strip=True)
            except (AttributeError, TypeError):
                pass
            avatar_container = userlinks.find_next_sibling()
            if avatar_container:
                avatar_container = avatar_container.find_next_sibling()
            if avatar_container:
                img = avatar_container.find("img")
                if img:
                    result.avatar_url = img.get("src", "")

    return result
