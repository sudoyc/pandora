from dataclasses import dataclass


@dataclass
class GalleryComment:
    id: int
    score: int = 0
    user: str = ""
    comment: str = ""
    time: str = ""
    is_uploader: bool = False
    vote_up_able: bool = False
    vote_down_able: bool = False
    vote_up_ed: bool = False
    vote_down_ed: bool = False
    editable: bool = False
    last_edited: str = ""
