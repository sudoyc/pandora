from dataclasses import dataclass, field
from typing import List
from .gallery import GalleryListItem

@dataclass
class FavoriteCategory:
    """Represents a favorite category (slot)."""
    slot: int
    name: str
    count: int

@dataclass
class FavoritesResponse:
    """Response containing favorite categories and the current page of favorite galleries."""
    categories: List[FavoriteCategory] = field(default_factory=list)
    galleries: List[GalleryListItem] = field(default_factory=list)
