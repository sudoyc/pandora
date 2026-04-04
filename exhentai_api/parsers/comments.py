import re
from bs4 import BeautifulSoup, Tag
from exhentai_api.models.comment import GalleryComment


def parse_comments(html: str) -> tuple[list[GalleryComment], bool]:
    """Parse comments from gallery detail page HTML.
    Returns (comments_list, has_more)."""
    soup = BeautifulSoup(html, "html.parser")
    cdiv = soup.find(id="cdiv")
    if not cdiv:
        return [], False

    comments = []
    c1_elements = cdiv.find_all(class_="c1")

    for c1 in c1_elements:
        comment = _parse_single_comment(c1)
        if comment:
            comments.append(comment)

    # Detect "has more" -- look for "click to show all" or check if chd says "All N comments"
    has_more = False
    chd = cdiv.find(id="chd")
    if chd:
        text = chd.get_text().lower()
        if "click to show all" in text:
            has_more = True

    return comments, has_more


def _parse_single_comment(element: Tag) -> GalleryComment | None:
    """Parse a single comment from a .c1 div element."""
    # Extract comment ID from previous sibling <a name="cNNN">
    comment_id = 0
    prev = element.find_previous_sibling("a")
    if prev and prev.get("name", "").startswith("c"):
        try:
            comment_id = int(prev["name"][1:])
        except (ValueError, IndexError):
            pass

    # Score from .c5
    score = 0
    c5 = element.find(class_="c5")
    if c5:
        score_text = c5.get_text(strip=True)
        score_match = re.search(r"([+-]?\d+)", score_text)
        if score_match:
            score = int(score_match.group(1))

    # User and time from .c3
    user = ""
    time_str = ""
    c3 = element.find(class_="c3")
    if c3:
        user_link = c3.find("a")
        if user_link:
            user = user_link.get_text(strip=True)
        # Extract time from own text nodes (not children)
        own_texts = []
        for child in c3.children:
            if isinstance(child, str):
                own_texts.append(child.strip())
        own_text = " ".join(own_texts)
        time_match = re.search(r"Posted on (.+?)(?:\s+by:|\s*$)", own_text)
        if time_match:
            time_str = time_match.group(1).strip()

    # Comment body from .c6
    comment_body = ""
    c6 = element.find(class_="c6")
    if c6:
        comment_body = c6.decode_contents().strip()

    # Vote/edit buttons from .c4
    vote_up_able = False
    vote_down_able = False
    vote_up_ed = False
    vote_down_ed = False
    editable = False
    c4 = element.find(class_="c4")
    if c4:
        for child in c4.find_all("a"):
            text = child.get_text(strip=True)
            if text == "Vote+":
                vote_up_able = True
                style = child.get("style", "").strip()
                vote_up_ed = style != ""
            elif text == "Vote-":
                vote_down_able = True
                style = child.get("style", "").strip()
                vote_down_ed = style != ""
            elif text == "Edit":
                editable = True

    # Last edited from .c8
    last_edited = ""
    c8 = element.find(class_="c8")
    if c8 and c8.find("a"):
        last_edited = c8.find("a").get_text(strip=True)

    return GalleryComment(
        id=comment_id,
        score=score,
        user=user,
        comment=comment_body,
        time=time_str,
        vote_up_able=vote_up_able,
        vote_down_able=vote_down_able,
        vote_up_ed=vote_up_ed,
        vote_down_ed=vote_down_ed,
        editable=editable,
        last_edited=last_edited,
    )
