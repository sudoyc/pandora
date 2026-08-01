from bs4 import BeautifulSoup
from pandora_daemon.providers.exhentai.upstream.models.toplist import TopListItem

def parse_toplist(html: str) -> list[TopListItem]:
    soup = BeautifulSoup(html, "html.parser")

    items = []

    ido_container = soup.find(class_="ido")
    if not ido_container:
        return items

    table = ido_container.find("table")
    if not table:
        return items

    rows = table.find_all("tr", recursive=False)
    if not rows:
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr", recursive=False)

    for row in rows:
        # A category row usually has a structure where the first td/th contains the category type text
        # and subsequent columns contain `.tun` items (or maybe just one column if `tl` param is used).

        cells = row.find_all(["td", "th"], recursive=False)
        if not cells:
            continue

        # Try to find the category type
        # Sometimes the category name is just text in the first td
        category_type = cells[0].get_text(strip=True)
        if not category_type or category_type.isspace():
            continue

        # The data cells contain `.tun` elements
        for cell in cells[1:]:
            tun_items = cell.find_all(class_="tun")
            for tun in tun_items:
                a_tag = tun.find("a")
                if a_tag:
                    items.append(TopListItem(
                        type=category_type,
                        name=a_tag.get_text(strip=True),
                        link=a_tag.get("href", "")
                    ))

    return items
