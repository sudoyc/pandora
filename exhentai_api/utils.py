import re

def extract_gallery_token(url: str) -> tuple[str, str]:
    match = re.search(r"/(?:g|mpv)/(\d+)/([0-9a-f]{10})", url)
    if not match:
        raise ValueError("Invalid gallery URL")
    return match.group(1), match.group(2)
