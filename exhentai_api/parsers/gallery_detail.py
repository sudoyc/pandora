import re
from bs4 import BeautifulSoup
from exhentai_api.models.gallery import GalleryDetail

def parse_gallery_detail(html: str, gid: str, token: str) -> GalleryDetail:
    soup = BeautifulSoup(html, "html.parser")

    gn = soup.find(id="gn")
    title = gn.get_text(strip=True) if gn else ""

    gj = soup.find(id="gj")
    title_jpn = gj.get_text(strip=True) if gj else None

    gdc = soup.find(id="gdc")
    category = gdc.get_text(strip=True) if gdc else ""

    gdn = soup.find(id="gdn")
    uploader = gdn.get_text(strip=True) if gdn else ""

    gd1 = soup.find(id="gd1")
    cover_url = ""
    if gd1 and gd1.find("div"):
        style = gd1.find("div").get("style", "")
        match = re.search(r"url\((.+?)\)", style)
        if match:
            cover_url = match.group(1)

    tags = {}
    taglist = soup.find(id="taglist")
    if taglist:
        for tr in taglist.find_all("tr"):
            tc = tr.find(class_="tc")
            if tc:
                namespace = tc.get_text(strip=True).replace(":", "")
                tag_vals = [t.get_text(strip=True) for t in tr.find_all(class_="gt")]
                tags[namespace] = tag_vals

    pages = 0
    size = ""
    posted = ""
    gdd = soup.find(id="gdd")
    if gdd:
        for tr in gdd.find_all("tr"):
            gdt1 = tr.find(class_="gdt1")
            gdt2 = tr.find(class_="gdt2")
            if gdt1 and gdt2:
                label = gdt1.get_text(strip=True)
                val = gdt2.get_text(strip=True)
                if label == "Posted:":
                    posted = val
                elif label == "File Size:":
                    size = val
                elif label == "Length:":
                    match = re.search(r"(\d+)", val.replace(",", ""))
                    if match:
                        pages = int(match.group(1))

    gdf = soup.find(id="gdf")
    favorite_slot = None
    if gdf:
        fav_text = gdf.get_text(strip=True)
        if fav_text and fav_text != "Add to Favorites":
            favorite_slot = 0 # Placeholder for actual slot parsing if needed

    preview_pages = 1
    ptt = soup.find("table", class_="ptt")
    if ptt:
        tds = ptt.find_all("td")
        if len(tds) > 2:
            try:
                preview_pages = int(tds[-2].get_text(strip=True))
            except ValueError:
                pass

    return GalleryDetail(
        gid=gid,
        token=token,
        title=title,
        title_jpn=title_jpn,
        category=category,
        uploader=uploader,
        cover_url=cover_url,
        tags=tags,
        pages=pages,
        size=size,
        posted=posted,
        favorite_slot=favorite_slot,
        preview_pages=preview_pages
    )