from pathlib import Path
from pandora_daemon.providers.exhentai.upstream.parsers.mytags import parse_mytags

def test_parse_mytags():
    html = (Path(__file__).parent / "data" / "mytags.html").read_text()
    tags = parse_mytags(html)
    assert len(tags) == 2
    assert tags[0].id == 100
    assert tags[0].name == "artist:testartist"
    assert tags[0].watched is True
    assert tags[0].hidden is False
    assert tags[0].color == "#ff0000"
    assert tags[0].weight == 10
    assert tags[1].id == 200
    assert tags[1].name == "parody:testparody"
    assert tags[1].watched is False
    assert tags[1].hidden is True
    assert tags[1].color is None
    assert tags[1].weight == 5

def test_parse_mytags_empty():
    tags = parse_mytags("<html><body></body></html>")
    assert tags == []
