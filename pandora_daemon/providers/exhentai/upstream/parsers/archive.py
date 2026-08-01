from bs4 import BeautifulSoup
from pandora_daemon.providers.exhentai.upstream.models.archive import ArchiveOption, ArchiverData


def parse_archive_list(html: str) -> ArchiverData:
    soup = BeautifulSoup(html, "html.parser")

    funds = ""
    for p in soup.find_all("p"):
        text = p.get_text()
        if "funds" in text.lower() or "GP" in text or "Credits" in text:
            strongs = p.find_all("strong")
            if strongs:
                funds = " / ".join(s.get_text(strip=True) for s in strongs)
            break

    original = None
    resample = None
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if len(cells) >= 3:
            label = cells[0].get_text(strip=True)
            cost = cells[1].get_text(strip=True).replace("Cost: ", "")
            size = cells[2].get_text(strip=True).replace("Size: ", "")
            if "Original" in label:
                original = ArchiveOption(cost=cost, size=size)
            elif "Resample" in label:
                resample = ArchiveOption(cost=cost, size=size)

    return ArchiverData(original=original, resample=resample, funds=funds)
