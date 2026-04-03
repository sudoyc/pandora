from bs4 import BeautifulSoup
from exhentai_api.models.toplist import TopListResponse, TopListTimeframe, TopListItem

def parse_toplist_item_array(element) -> list[TopListItem]:
    if not element:
        return []

    items = []
    min_items = element.find_all(class_="tun")
    for item in min_items:
        a_tag = item.find("a")
        if a_tag:
            items.append(TopListItem(
                name=a_tag.get_text(strip=True),
                href=a_tag.get("href", "")
            ))
    return items

def parse_info(element) -> TopListTimeframe:
    if not element:
        return TopListTimeframe()

    children = list(element.children)
    # The structure in HTML usually has empty text nodes between elements when parsed by bs4,
    # so we'll filter out string nodes or navigate more safely.
    # A safer way is to find the tr/td elements.

    # In reference parser: elements.get(1).child(1).child(0)
    # It means: table -> tbody -> tr -> td ...
    # Let's just find the columns directly by looking for the 4 tables or columns

    # Structure of one category row usually contains 4 sub-tables for each timeframe
    # Let's find all `table` elements within this element
    tables = element.find_all("table", recursive=False)

    # But wait, looking at TopListParser.java:
    # Elements elements = element.children();
    # topListInfo.allTimeTopList = parseArray(elements.get(1).child(1).child(0));
    # topListInfo.pastYearTopList = parseArray(elements.get(2).child(1).child(0));
    # topListInfo.pastMonthTopList = parseArray(elements.get(3).child(1).child(0));
    # topListInfo.yesterdayTopList = parseArray(elements.get(4).child(1).child(0));

    # In HTML, `element` is probably a <tr>, and its children are <td>s.
    # <td>0</td> = label
    # <td>1</td> = all time
    # <td>2</td> = past year
    # <td>3</td> = past month
    # <td>4</td> = yesterday

    # Let's find all `td`s directly inside this `tr`
    tds = element.find_all("td", recursive=False)

    timeframe = TopListTimeframe()

    if len(tds) >= 5:
        timeframe.all_time = parse_toplist_item_array(tds[1])
        timeframe.past_year = parse_toplist_item_array(tds[2])
        timeframe.past_month = parse_toplist_item_array(tds[3])
        timeframe.yesterday = parse_toplist_item_array(tds[4])

    return timeframe

def parse_toplist(html: str) -> TopListResponse:
    soup = BeautifulSoup(html, "html.parser")

    ido_container = soup.find(class_="ido")
    if not ido_container:
        return TopListResponse()

    # In Java parser:
    # Elements elements = document.getElementsByClass("ido").get(0).children();
    # ehTopListDetail.galleryTopListInfo = parseInfo(elements.get(1), ...);
    # ehTopListDetail.uploaderTopListInfo = parseInfo(elements.get(3), ...);
    # ehTopListDetail.taggingTopListInfo = parseInfo(elements.get(5), ...);
    # ehTopListDetail.hentaiHomeTopListInfo = parseInfo(elements.get(7), ...);
    # ehTopListDetail.ehTrackerTopListInfo = parseInfo(elements.get(9), ...);
    # ehTopListDetail.cleanUpTopListInfo = parseInfo(elements.get(11), ...);
    # ehTopListDetail.ratingAndReviewingTopListInfo = parseInfo(elements.get(13), ...);

    # The `.ido` container has a direct child `table`.
    # Actually `elements` are children of `.ido` or a `table` inside it.
    # Usually it's `.ido > div > table > tbody > tr`

    # Let's find all the rows that might contain the data.
    # Since we don't have exact HTML, finding `td` with class="tun" helps.
    # But let's assume the rows we want are `tr`s inside the main table of `.ido`.
    table = ido_container.find("table")
    if not table:
        return TopListResponse()

    rows = table.find_all("tr", recursive=False)
    if not rows:
        # Check tbody
        tbody = table.find("tbody")
        if tbody:
            rows = tbody.find_all("tr", recursive=False)

    response = TopListResponse()

    # Usually there's a header row, then the categories.
    # Or multiple tables inside `.ido`.
    # Looking at Java: elements.get(1) means the 2nd child. If it's `tr`s,
    # 0 = header, 1 = gallery, 2 = spacer, 3 = uploader, 4 = spacer...
    # So skipping by 2.

    if len(rows) >= 2:
        response.gallery = parse_info(rows[1])
    if len(rows) >= 4:
        response.uploader = parse_info(rows[3])
    if len(rows) >= 6:
        response.tagging = parse_info(rows[5])
    if len(rows) >= 8:
        response.hentai_home = parse_info(rows[7])
    if len(rows) >= 10:
        response.eh_tracker = parse_info(rows[9])
    if len(rows) >= 12:
        response.cleanup = parse_info(rows[11])
    if len(rows) >= 14:
        response.rating_and_reviewing = parse_info(rows[13])

    return response
