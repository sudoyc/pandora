import re
from bs4 import BeautifulSoup
from typing import Tuple, Dict, Any

def parse_image_viewer(html: str) -> Tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    img = soup.find(id="img")
    image_url = img.get("src") if img else ""

    nl = ""
    match = re.search(r"nl\('([^']+)'\)", html)
    if match:
        nl = match.group(1)

    return image_url, nl

def parse_image_api_response(json_data: Dict[str, Any]) -> Tuple[str, str]:
    image_url = ""
    nl = ""

    i3 = json_data.get("i3", "")
    img_match = re.search(r"src=\"([^\"]+)\"", i3)
    if img_match:
        image_url = img_match.group(1)

    i6 = json_data.get("i6", "")
    nl_match = re.search(r"nl\('([^']+)'\)", i6)
    if nl_match:
        nl = nl_match.group(1)
    elif "n" in json_data:
        nl = json_data["n"]

    return image_url, nl
