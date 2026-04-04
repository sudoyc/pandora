from pathlib import Path
from exhentai_api.parsers.profile import parse_profile

def test_parse_profile():
    html = (Path(__file__).parent / "data" / "profile.html").read_text()
    result = parse_profile(html)
    assert result.display_name == "TestDisplayUser"
    assert "avatar_12345" in result.avatar_url

def test_parse_profile_empty():
    result = parse_profile("<html><body></body></html>")
    assert result.display_name == ""
    assert result.avatar_url == ""
