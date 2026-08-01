from bs4 import BeautifulSoup
from pandora_daemon.providers.exhentai.upstream.models.favorites import FavoriteCategory, FavoritesResponse
from pandora_daemon.providers.exhentai.upstream.parsers.gallery import parse_gallery_list

def parse_favorites_list(html: str) -> FavoritesResponse:
    """Parses the favorites page HTML into a FavoritesResponse."""
    soup = BeautifulSoup(html, "html.parser")
    categories = []

    ido = soup.find(class_="ido")
    if ido:
        fps = ido.find_all(class_="fp")
        for i, fp in enumerate(fps):
            if i > 9: # Only slots 0-9
                break

            # In JSoup, child(int) refers to Element children.
            # In BeautifulSoup, we need to filter out NavigableStrings.
            elements = [c for c in fp.children if c.name is not None]

            count = 0
            name = ""

            if len(elements) > 0:
                count_str = elements[0].get_text(strip=True)
                # Keep only digits for count
                count_digits = "".join(filter(str.isdigit, count_str))
                if count_digits:
                    count = int(count_digits)

            if len(elements) > 2:
                name = elements[2].get_text(strip=True)

            categories.append(FavoriteCategory(slot=i, name=name, count=count))

    # Parse the standard gallery list
    galleries = parse_gallery_list(html)

    return FavoritesResponse(
        categories=categories,
        galleries=galleries
    )
