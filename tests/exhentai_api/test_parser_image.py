from exhentai_api.parsers.image import parse_image_viewer, parse_image_api_response

def test_parse_image_viewer():
    html = """
    <html><body>
        <img id="img" src="https://example.com/image1.jpg" />
        <div><a href="#" onclick="return nl('abcdef1234')">Reload Image</a></div>
    </body></html>
    """
    image_url, nl = parse_image_viewer(html)
    assert image_url == "https://example.com/image1.jpg"
    assert nl == "abcdef1234"

def test_parse_image_api_response():
    json_resp = {
        "n": "newnltoken5678",
        "i3": "<a href=\"#\"><img id=\"img\" src=\"https://example.com/image1_new.jpg\" style=\"\" /></a>",
        "i6": "onclick=\"return nl('newnltoken5678')\""
    }
    image_url, nl = parse_image_api_response(json_resp)
    assert image_url == "https://example.com/image1_new.jpg"
    assert nl == "newnltoken5678"
