from pathlib import Path
from exhentai_api.parsers.archive import parse_archive_list

def test_parse_archive_list():
    html = (Path(__file__).parent / "data" / "archive_list.html").read_text()
    data = parse_archive_list(html)
    assert "1,234 GP" in data.funds
    assert data.original is not None
    assert "20 GP" in data.original.cost
    assert "200 MB" in data.original.size
    assert data.resample is not None
    assert "10 GP" in data.resample.cost
    assert "100 MB" in data.resample.size

def test_parse_archive_list_empty():
    data = parse_archive_list("<html><body></body></html>")
    assert data.original is None
    assert data.resample is None
