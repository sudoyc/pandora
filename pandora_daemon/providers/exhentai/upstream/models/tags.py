from dataclasses import dataclass
from typing import Optional

@dataclass
class Tag:
    namespace: str
    name: str

@dataclass
class WatchedTag:
    id: int
    name: str
    watched: bool
    hidden: bool
    color: Optional[str]
    weight: int
