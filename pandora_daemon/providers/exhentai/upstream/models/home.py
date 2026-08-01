from dataclasses import dataclass


@dataclass
class HomeDetail:
    image_used: int = 0
    image_total: int = 0
    reset_cost: int = 0
    gp_from_gallery: int = 0
    gp_from_torrent: int = 0
    gp_from_archive: int = 0
    gp_from_hath: int = 0
    moderation_power: int = 0
