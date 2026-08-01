from pathlib import Path
from pandora_daemon.providers.exhentai.upstream.parsers.torrent import parse_torrent_list

def test_parse_torrent_list():
    html = (Path(__file__).parent / "data" / "torrent_list.html").read_text()
    items = parse_torrent_list(html)
    assert len(items) == 2
    assert items[0].name == "Gallery Pack v1.torrent"
    assert "?p=" not in items[0].url
    assert "aaa.torrent" in items[0].url
    assert items[1].name == "[Author] Gallery Name.torrent"

def test_parse_torrent_list_empty():
    items = parse_torrent_list("<html><body></body></html>")
    assert items == []
