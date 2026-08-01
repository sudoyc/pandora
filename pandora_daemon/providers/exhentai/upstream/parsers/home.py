import re
from bs4 import BeautifulSoup
from pandora_daemon.providers.exhentai.upstream.models.home import HomeDetail

PATTERN_LIMITS = re.compile(
    r"at <strong>([\d,]+)</strong> towards (?:a limit|your account limit) of <strong>([\d,]+)</strong>",
    re.DOTALL,
)


def _parse_int(s: str) -> int:
    return int(s.replace(",", "")) if s else 0


def parse_home_detail(html: str) -> HomeDetail:
    detail = HomeDetail()

    limits_match = PATTERN_LIMITS.search(html)
    if limits_match:
        detail.image_used = _parse_int(limits_match.group(1))
        detail.image_total = _parse_int(limits_match.group(2))

    reset_match = re.search(r"Reset Cost:\s*<strong>([\d,]+)</strong>", html)
    if reset_match:
        detail.reset_cost = _parse_int(reset_match.group(1))
    else:
        reset_match2 = re.search(r"spending <strong>([\d,]+)</strong> GP", html)
        if reset_match2:
            detail.reset_cost = _parse_int(reset_match2.group(1))

    soup = BeautifulSoup(html, "html.parser")
    homeboxes = soup.find_all(class_="homebox")

    if len(homeboxes) >= 3:
        gp_box = homeboxes[2]
        rows = gp_box.find_all("tr")
        gp_values = []
        for row in rows:
            cells = row.find_all("td")
            if cells:
                val_text = cells[0].get_text(strip=True)
                gp_values.append(_parse_int(val_text))
        if len(gp_values) >= 1:
            detail.gp_from_gallery = gp_values[0]
        if len(gp_values) >= 2:
            detail.gp_from_torrent = gp_values[1]
        if len(gp_values) >= 3:
            detail.gp_from_archive = gp_values[2]
        if len(gp_values) >= 4:
            detail.gp_from_hath = gp_values[3]

    if len(homeboxes) >= 5:
        mod_box = homeboxes[4]
        mod_match = re.search(r"(\d[\d,]*)", mod_box.get_text())
        if mod_match:
            detail.moderation_power = _parse_int(mod_match.group(1))

    return detail
