from dataclasses import dataclass, field
from typing import List

@dataclass
class TopListItem:
    type: str
    name: str
    link: str
