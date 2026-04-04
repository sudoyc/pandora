import re
from bs4 import BeautifulSoup
from exhentai_api.models.gallery import GalleryListItem
from exhentai_api.utils import extract_gallery_token


def _parse_rating(style: str) -> float:
    """Parse star rating from CSS background-position sprite.

    The rating stars use a sprite sheet. The formula is:
      rating = 5 - (x / 16)
    If the y offset is 21, subtract an additional 0.5 (half star).
    """
    match = re.search(r"background-position:\s*(-?\d+)(?:px)?\s+(-?\d+)(?:px)?", style)
    if not match:
        return 0.0
    x = abs(int(match.group(1)))
    y = abs(int(match.group(2)))
    rating = 5.0 - (x / 16.0)
    if y == 21:
        rating -= 0.5
    return max(0.0, rating)


def _parse_pages(text: str) -> int:
    """Extract page count from text like '123 pages'."""
    match = re.search(r"(\d+)\s+page", text)
    if match:
        return int(match.group(1))
    return 0


def _parse_thumb_dimensions(style: str) -> tuple[int, int]:
    """Extract width and height from inline style like 'height:200px;width:150px'.

    Returns (width, height).
    """
    width = 0
    height = 0
    w_match = re.search(r"width:\s*(\d+)px", style)
    h_match = re.search(r"height:\s*(\d+)px", style)
    if w_match:
        width = int(w_match.group(1))
    if h_match:
        height = int(h_match.group(1))
    return width, height


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
        thumb_width = 0
        thumb_height = 0
        thumb_elem = row.find(class_=["glthumb", "gl1e", "gl3t"])
        if thumb_elem:
            img = thumb_elem.find("img")
            if img:
                thumb_url = img.get("data-src") or img.get("src") or ""
            style = thumb_elem.get("style", "")
            if style:
                thumb_width, thumb_height = _parse_thumb_dimensions(style)

        posted = ""
        posted_elem = row.find(id=re.compile(r"^posted_"))
        if posted_elem:
            posted = posted_elem.get_text(strip=True)
        else:
            date_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row.get_text())
            if date_match:
                posted = date_match.group(0)

        # Parse rating from .ir / .irr / .irg / .irb element
        rating = 0.0
        rated = False
        rating_elem = row.find(class_=re.compile(r"^ir"))
        if rating_elem:
            rating_style = rating_elem.get("style", "")
            rating = _parse_rating(rating_style)
            classes = rating_elem.get("class", [])
            rated = any(c in classes for c in ("irr", "irg", "irb"))

        # Parse pages from text like "123 pages" in individual elements
        pages = 0
        for elem in row.find_all(string=re.compile(r"\d+\s+page")):
            pages = _parse_pages(elem)
            if pages > 0:
                break

        items.append(GalleryListItem(
            gid=gid,
            token=token,
            title=title,
            category=category,
            uploader=uploader,
            thumb_url=thumb_url,
            posted=posted,
            rating=rating,
            pages=pages,
            rated=rated,
            thumb_width=thumb_width,
            thumb_height=thumb_height,
        ))

    return items
