import pytest
from exhentai_api.client import ExhentaiClient

@pytest.mark.asyncio
async def test_client_headers():
    client = ExhentaiClient(igneous="test_ig", ipb_member_id="123")
    assert client.cookies["igneous"] == "test_ig"
    assert client.cookies["ipb_member_id"] == "123"
