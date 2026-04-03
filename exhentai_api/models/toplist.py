from dataclasses import dataclass, field
from typing import List

@dataclass
class TopListItem:
    name: str
    href: str

@dataclass
class TopListTimeframe:
    all_time: List[TopListItem] = field(default_factory=list)
    past_year: List[TopListItem] = field(default_factory=list)
    past_month: List[TopListItem] = field(default_factory=list)
    yesterday: List[TopListItem] = field(default_factory=list)

@dataclass
class TopListResponse:
    gallery: TopListTimeframe = field(default_factory=TopListTimeframe)
    uploader: TopListTimeframe = field(default_factory=TopListTimeframe)
    tagging: TopListTimeframe = field(default_factory=TopListTimeframe)
    hentai_home: TopListTimeframe = field(default_factory=TopListTimeframe)
    eh_tracker: TopListTimeframe = field(default_factory=TopListTimeframe)
    cleanup: TopListTimeframe = field(default_factory=TopListTimeframe)
    rating_and_reviewing: TopListTimeframe = field(default_factory=TopListTimeframe)
