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
        link_elem = row.find("td", class_="gl3c")
        if not link_elem:
            continue
        link_elem = link_elem.find("a")
        if not link_elem or not link_elem.get("href"):
            continue
        gid, token = extract_gallery_token(link_elem["href"])

        cat_elem = row.find(class_=lambda x: x in ["cn", "cs"])
        category = cat_elem.get_text(strip=True) if cat_elem else ""

        uploader_elem = row.find("td", class_=["glhide", "gl4c"])
        uploader = uploader_elem.get_text(strip=True) if uploader_elem else ""

        thumb_url = ""
        thumb_elem = row.find(class_=["glthumb", "gl1e", "gl3t"])
        if thumb_elem:
            img = thumb_elem.find("img")
            if img:
                thumb_url = img.get("data-src") or img.get("src") or ""

        import re
        posted = ""
        posted_elem = row.find(id=re.compile(r"^posted_"))
        if posted_elem:
            posted = posted_elem.get_text(strip=True)
        else:
            date_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row.get_text())
            if date_match:
                posted = date_match.group(0)

        items.append(GalleryListItem(
            gid=gid,
            token=token,
            title=title,
            category=category,
            uploader=uploader,
            thumb_url=thumb_url,
            posted=posted
        ))

    return items