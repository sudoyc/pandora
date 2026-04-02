from bs4 import BeautifulSoup
from exhentai_api.models.gallery import GalleryListItem
from exhentai_api.utils import extract_gallery_token

def parse_gallery_list(html: str) -> list[GalleryListItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    itg = soup.find(class_="itg")
    if not itg:
        return []

    for row in itg.find_all("tr"):
        title_elem = row.find(class_="glname")
        if not title_elem:
            continue

        title = title_elem.get_text(strip=True)
        link_elem = row.find("td", class_="gl3c").find("a")
        gid, token = extract_gallery_token(link_elem["href"])

        cat_elem = row.find(class_=lambda x: x in ["cn", "cs"])
        category = cat_elem.get_text(strip=True) if cat_elem else ""

        uploader_elem = row.find("td", class_=["glhide", "gl4c"])
        uploader = uploader_elem.get_text(strip=True) if uploader_elem else ""

        items.append(GalleryListItem(
            gid=gid,
            token=token,
            title=title,
            category=category,
            uploader=uploader,
            thumb_url="", # Simplified for minimal pass
            posted=""     # Simplified for minimal pass
        ))

    return items