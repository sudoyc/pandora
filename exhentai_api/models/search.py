from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SearchParams:
    """Represents parameters for advanced gallery search."""
    f_search: str = ""
    f_cats: Optional[int] = None
    advsearch: bool = False

    # Advanced toggles (bool mapped to "on"/None)
    f_sname: bool = False
    f_stags: bool = False
    f_sdesc: bool = False
    f_storr: bool = False
    f_sto: bool = False
    f_sdt1: bool = False
    f_sdt2: bool = False
    f_sh: bool = False
    f_sr: bool = False
    f_sp: bool = False

    # Advanced values
    f_srdd: Optional[int] = None
    f_spf: Optional[int] = None
    f_spt: Optional[int] = None

    def to_dict(self) -> dict[str, str]:
        """Converts the dataclass to a dictionary suitable for httpx query parameters.
        Ignores None values and false booleans unless they are required.
        """
        params = {}
        if self.f_search:
            params["f_search"] = self.f_search

        if self.f_cats is not None:
            # f_cats on ExHentai is a bitmask of categories to EXCLUDE.
            # We assume self.f_cats is the bitmask of categories to INCLUDE.
            inverted_cats = (~self.f_cats) & 1023
            params["f_cats"] = str(inverted_cats)

        if self.advsearch:
            params["advsearch"] = "1"
            if self.f_sname: params["f_sname"] = "on"
            if self.f_stags: params["f_stags"] = "on"
            if self.f_sdesc: params["f_sdesc"] = "on"
            if self.f_storr: params["f_storr"] = "on"
            if self.f_sto: params["f_sto"] = "on"
            if self.f_sdt1: params["f_sdt1"] = "on"
            if self.f_sdt2: params["f_sdt2"] = "on"

            if self.f_sr and self.f_srdd is not None:
                params["f_sr"] = "on"
                params["f_srdd"] = str(self.f_srdd)

            if self.f_sp:
                params["f_sp"] = "on"
                if self.f_spf is not None:
                    params["f_spf"] = str(self.f_spf)
                if self.f_spt is not None:
                    params["f_spt"] = str(self.f_spt)

        # f_sh can be used without advsearch
        if self.f_sh:
            params["f_sh"] = "on"

        return params
