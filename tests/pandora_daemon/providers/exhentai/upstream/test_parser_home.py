from pathlib import Path
from pandora_daemon.providers.exhentai.upstream.parsers.home import parse_home_detail

def test_parse_home_detail():
    html = (Path(__file__).parent / "data" / "home.html").read_text()
    detail = parse_home_detail(html)
    assert detail.image_used == 5000
    assert detail.image_total == 25000
    assert detail.reset_cost == 100
    assert detail.gp_from_gallery == 10000
    assert detail.gp_from_torrent == 5000
    assert detail.gp_from_archive == 2000
    assert detail.gp_from_hath == 1000

def test_parse_home_detail_empty():
    detail = parse_home_detail("<html><body></body></html>")
    assert detail.image_used == 0
    assert detail.image_total == 0
