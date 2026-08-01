from dataclasses import dataclass

@dataclass
class ImageDetail:
    gid: str
    page: int
    image_url: str
    nl: str
