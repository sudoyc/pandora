from dataclasses import dataclass
from typing import Optional


@dataclass
class ArchiveOption:
    cost: str
    size: str
    url: str = ""


@dataclass
class ArchiverData:
    original: Optional[ArchiveOption] = None
    resample: Optional[ArchiveOption] = None
    funds: str = ""
