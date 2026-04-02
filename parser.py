import re
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

def parse_gallery_url(url: str) -> Optional[Dict[str, str]]:
    """Extracts gid and token from gallery URL."""
    # Matches: https://exhentai.org/g/1234567/a1b2c3d4e5/
    pattern = re.compile(r"/(?:g|mpv)/(\d+)/([0-9a-f]{10})")
    match = pattern.search(url)
    if match:
        return {"gid": match.group(1), "token": match.group(2)}
    return None

def _extract_language(title: str) -> str:
    """Guesses language indicator from title, similar to reference project or standard practice."""
    t_lower = title.lower()
    if "[chinese]" in t_lower or "汉化" in t_lower or "漢化" in t_lower or "中文" in t_lower:
        return "ZH"
    if "[japanese]" in t_lower:
        return "JP"
    if "[english]" in t_lower:
        return "EN"
    if "[korean]" in t_lower:
        return "KR"
    return ""

def parse_gallery_list(html: str) -> List[Dict[str, str]]:
    """Parses a gallery list page (e.g., homepage or search results)."""
    soup = BeautifulSoup(html, "html.parser")
    galleries = []
    
    table = soup.find("table", class_="itg")
    if table:
        rows = table.find_all("tr")
        for row in rows[1:]:  # Skip header row
            gallery = {
                "title": "Unknown",
                "url": "",
                "thumb_url": "",
                "uploader": "Unknown",
                "category": "Unknown",
                "posted": "",
                "language": ""
            }
            
            # Category
            cn = row.find(class_="cn")
            cs = row.find(class_="cs")
            if cn:
                gallery["category"] = cn.get_text(strip=True)
            elif cs:
                gallery["category"] = cs.get_text(strip=True)
                
            # Date (posted)
            posted_elem = row.find(id=re.compile(r"^posted_"))
            if posted_elem:
                gallery["posted"] = posted_elem.get_text(strip=True)
            else:
                date_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", row.get_text())
                if date_match:
                    gallery["posted"] = date_match.group(0)
            
            # Usually in compact/extended mode it's in td.gl3c
            gl3c = row.find("td", class_="gl3c")
            if gl3c:
                a_tag = gl3c.find("a")
                if a_tag:
                    gallery["url"] = a_tag.get("href", "")
                    title_div = a_tag.find("div", class_="glink")
                    if title_div:
                        gallery["title"] = title_div.get_text(strip=True)
                    else:
                        gallery["title"] = a_tag.get_text(strip=True)
            
            gallery["language"] = _extract_language(gallery["title"])

            gl2c = row.find("td", class_="gl2c")
            if gl2c:
                img_tag = gl2c.find("img")
                if img_tag:
                    gallery["thumb_url"] = img_tag.get("data-src") or img_tag.get("src", "")
                     
            gl4c = row.find("td", class_="gl4c")
            if not gl4c:
                 gl4c = row.find("td", class_="glhide")
            if gl4c:
                a_upl = gl4c.find("a")
                if a_upl:
                    gallery["uploader"] = a_upl.get_text(strip=True)
            
            if gallery["url"]:
                galleries.append(gallery)
                
    return galleries

def parse_gallery_detail(html: str) -> Dict:
    """Parses the main gallery page."""
    soup = BeautifulSoup(html, "html.parser")

    details = {
        "title": "Unknown Title",
        "title_jpn": "",
        "uploader": "Unknown",
        "category": "Unknown",
        "tags": {},
        "pages": 0,
        "preview_urls": []
    }

    # Titles
    gn = soup.find(id="gn")
    if gn:
        details["title"] = gn.get_text(strip=True)
    gj = soup.find(id="gj")
    if gj:
        details["title_jpn"] = gj.get_text(strip=True)

    # Uploader
    gdn = soup.find(id="gdn")
    if gdn:
        details["uploader"] = gdn.get_text(strip=True)

    # Category
    gdc = soup.find(id="gdc")
    if gdc:
        details["category"] = gdc.get_text(strip=True)

    # Tags
    taglist = soup.find(id="taglist")
    if taglist:
        trs = taglist.find_all("tr")
        for tr in trs:
            tds = tr.find_all("td")
            if len(tds) >= 2:
                namespace = tds[0].get_text(strip=True).strip(":")
                tags = [a.get_text(strip=True) for a in tds[1].find_all("a")]
                details["tags"][namespace] = tags

    # Number of pages
    gdd = soup.find(id="gdd")
    if gdd:
        length_td = gdd.find("td", string=re.compile(r"^Length:"))
        if length_td:
            val_td = length_td.find_next_sibling("td")
            if val_td:
                pages_match = re.search(r"([\d,]+)\s+pages", val_td.get_text())
                if pages_match:
                    details["pages"] = int(pages_match.group(1).replace(",", ""))

    # Preview Links (for image viewer)
    gdt = soup.find(id="gdt")
    if gdt:
        for a in gdt.find_all("a"):
            href = a.get("href")
            if href:
                details["preview_urls"].append(href)

    return details

def parse_image_viewer_page(html: str) -> Optional[str]:
    """Parses the image viewer page to get the actual image URL."""
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find("img", id="img")
    if img and img.get("src"):
        return img.get("src")
    return None

def parse_next_page_url(html: str) -> Optional[str]:
    """Parses the gallery detail page to see if there is a next page of thumbnails."""
    soup = BeautifulSoup(html, "html.parser")
    ptb = soup.find("table", class_="ptt")
    if ptb:
        next_td = ptb.find("td", onclick=True, string=re.compile(r">"))
        if next_td:
            a = next_td.find("a")
            if a and a.get("href"):
                return a.get("href")
    return None
