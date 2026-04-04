from bs4 import BeautifulSoup
from exhentai_api.models.tags import WatchedTag


def parse_mytags(html: str) -> list[WatchedTag]:
    soup = BeautifulSoup(html, "html.parser")
    outer = soup.find(id="usertags_outer")
    if not outer:
        return []

    tags = []
    children = list(outer.children)
    elements = [c for c in children if hasattr(c, "get") and c.name is not None]

    for elem in elements[1:]:  # skip header row
        elem_id = elem.get("id", "")
        if not elem_id.startswith("utag_"):
            continue

        tag_num = elem_id[5:]
        try:
            tag_id = int(tag_num)
        except ValueError:
            continue

        name_elem = elem.find(id=f"tagpreview{tag_num}")
        name = name_elem.get("title", "") if name_elem else ""

        watch_elem = elem.find(id=f"tagwatch{tag_num}")
        watched = watch_elem.get("checked") == "checked" if watch_elem else False

        hide_elem = elem.find(id=f"taghide{tag_num}")
        hidden = hide_elem.get("checked") == "checked" if hide_elem else False

        color_elem = elem.find(id=f"tagcolor{tag_num}")
        color = None
        if color_elem:
            color_val = color_elem.get("placeholder", "")
            color = color_val if color_val else None

        weight_elem = elem.find(id=f"tagweight{tag_num}")
        weight = 0
        if weight_elem:
            weight_str = weight_elem.get("value", "0")
            try:
                weight = int(weight_str) if weight_str else 0
            except ValueError:
                weight = 0

        tags.append(WatchedTag(
            id=tag_id, name=name, watched=watched,
            hidden=hidden, color=color, weight=weight
        ))

    return tags
