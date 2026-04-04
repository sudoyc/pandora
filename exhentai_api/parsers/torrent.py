import re
from exhentai_api.models.torrent import TorrentItem

PATTERN_TORRENT = re.compile(
    r'<td colspan="5"> &nbsp; <a href="([^"]+)"[^<]*>([^<]+)</a></td>'
)


def parse_torrent_list(html: str) -> list[TorrentItem]:
    items = []
    for match in PATTERN_TORRENT.finditer(html):
        url = match.group(1)
        name = match.group(2)
        p_idx = url.find("?p=")
        if p_idx != -1:
            url = url[:p_idx]
        items.append(TorrentItem(url=url, name=name))
    return items
