import re
from bs4 import BeautifulSoup
from exhentai_api.models.gallery import GalleryDetail
from exhentai_api.parsers.comments import parse_comments


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
    favorite_count = 0
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
                    m = re.search(r"(\d+)", val.replace(",", ""))
                    if m:
                        pages = int(m.group(1))
                elif label == "Favorited:":
                    m = re.search(r"(\d+)", val.replace(",", ""))
                    if m:
                        favorite_count = int(m.group(1))

    gdf = soup.find(id="gdf")
    favorite_slot = None
    if gdf:
        fav_text = gdf.get_text(strip=True)
        if fav_text and fav_text != "Add to Favorites":
            favorite_slot = 0

    preview_pages = 1
    ptt = soup.find("table", class_="ptt")
    if ptt:
        tds = ptt.find_all("td")
        if len(tds) > 2:
            try:
                preview_pages = int(tds[-2].get_text(strip=True))
            except ValueError:
                pass

    preview_urls = []
    for gdt in soup.find_all(class_=["gdtm", "gdtl"]):
        a_tag = gdt.find("a")
        if a_tag and a_tag.get("href"):
            preview_urls.append(a_tag.get("href"))
    if not preview_urls:
        gdt_elem = soup.find(id="gdt")
        if gdt_elem:
            for a_tag in gdt_elem.find_all("a"):
                if a_tag and a_tag.get("href") and "/s/" in a_tag.get("href"):
                    preview_urls.append(a_tag.get("href"))

    thumb_urls = []
    for gdt in soup.find_all(class_=["gdtm", "gdtl"]):
        classes = gdt.get("class") or []
        # gdtm: thumbnail is CSS background-image on inner div (not the blank.gif spacer)
        if "gdtm" in classes:
            inner_div = gdt.find("div")
            if inner_div:
                style = inner_div.get("style", "")
                bg_match = re.search(r"url\((.+?)\)", style)
                if bg_match:
                    thumb_urls.append(bg_match.group(1))
                    continue
        # gdtl: thumbnail is direct <img src="..."> (not blank.gif)
        a_tag = gdt.find("a")
        if a_tag:
            img_tag = a_tag.find("img")
            if img_tag:
                src = img_tag.get("src") or img_tag.get("data-src") or ""
                if src and "blank.gif" not in src and "placeholder" not in src:
                    thumb_urls.append(src)
    # Fallback: extract from #gdt container if no thumb_urls found
    if not thumb_urls:
        gdt_elem = soup.find(id="gdt")
        if gdt_elem:
            for a_tag in gdt_elem.find_all("a"):
                if not a_tag.get("href") or "/s/" not in a_tag.get("href", ""):
                    continue
                img_tag = a_tag.find("img")
                if img_tag:
                    src = img_tag.get("src") or img_tag.get("data-src") or ""
                    if src and "blank.gif" not in src and "placeholder" not in src:
                        thumb_urls.append(src)
            # Still empty? Try CSS background-image on any div inside #gdt
            if not thumb_urls:
                for div in gdt_elem.find_all("div", style=True):
                    bg_match = re.search(r"url\((.+?)\)", div.get("style", ""))
                    if bg_match:
                        thumb_urls.append(bg_match.group(1))

    # Rating from #rating_label
    rating = 0.0
    rating_label = soup.find(id="rating_label")
    if rating_label:
        m = re.search(r"([\d.]+)", rating_label.get_text(strip=True))
        if m:
            rating = float(m.group(1))

    # Rating count
    rating_count = 0
    rating_count_elem = soup.find(id="rating_count")
    if rating_count_elem:
        m = re.search(r"(\d+)", rating_count_elem.get_text().replace(",", ""))
        if m:
            rating_count = int(m.group(1))

    # Torrent and archive info from #gd5
    torrent_count = 0
    torrent_url = ""
    archive_url = ""
    gd5 = soup.find(id="gd5")
    if gd5:
        for a_tag in gd5.find_all("a"):
            href = a_tag.get("href", "")
            text = a_tag.get_text(strip=True)
            if "gallerytorrents" in href:
                torrent_url = href
                tc_match = re.search(r"\((\d+)\)", text)
                if tc_match:
                    torrent_count = int(tc_match.group(1))
            elif "archiver" in href:
                archive_url = href

    # api_uid and api_key from <script> tags
    api_uid = ""
    api_key = ""
    for script in soup.find_all("script"):
        script_text = script.string or ""
        uid_match = re.search(r"apiuid\s*=\s*(\d+)", script_text)
        key_match = re.search(r'apikey\s*=\s*"([a-f0-9]+)"', script_text)
        if uid_match:
            api_uid = uid_match.group(1)
        if key_match:
            api_key = key_match.group(1)

    # Newer versions from #gnd
    newer_versions = []
    gnd = soup.find(id="gnd")
    if gnd:
        for a_tag in gnd.find_all("a"):
            href = a_tag.get("href", "")
            nv_match = re.search(r"/g/(\d+)/([0-9a-f]{10})/", href)
            if nv_match:
                newer_versions.append({
                    "gid": nv_match.group(1),
                    "token": nv_match.group(2),
                    "title": a_tag.get_text(strip=True),
                    "url": href,
                })

    # Parent URL from gdd
    parent_url = None
    if gdd:
        for tr in gdd.find_all("tr"):
            gdt1 = tr.find(class_="gdt1")
            if gdt1 and "Parent:" in gdt1.get_text():
                gdt2 = tr.find(class_="gdt2")
                if gdt2:
                    parent_link = gdt2.find("a")
                    if parent_link:
                        parent_url = parent_link.get("href")

    # Comments
    comments, comments_has_more = parse_comments(html)

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
        preview_pages=preview_pages,
        preview_urls=preview_urls,
        thumb_urls=thumb_urls,
        rating=rating,
        rating_count=rating_count,
        favorite_count=favorite_count,
        torrent_count=torrent_count,
        torrent_url=torrent_url,
        archive_url=archive_url,
        parent_url=parent_url,
        newer_versions=newer_versions,
        comments=comments,
        comments_has_more=comments_has_more,
        api_uid=api_uid,
        api_key=api_key,
    )
