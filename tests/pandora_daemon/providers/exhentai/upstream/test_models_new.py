from pandora_daemon.providers.exhentai.upstream.models.comment import GalleryComment
from pandora_daemon.providers.exhentai.upstream.models.torrent import TorrentItem
from pandora_daemon.providers.exhentai.upstream.models.archive import ArchiveOption, ArchiverData
from pandora_daemon.providers.exhentai.upstream.models.home import HomeDetail
from pandora_daemon.providers.exhentai.upstream.models.profile import ProfileResult
from pandora_daemon.providers.exhentai.upstream.models.vote import RateResult, VoteCommentResult


def test_gallery_comment_defaults():
    c = GalleryComment(id=123)
    assert c.id == 123
    assert c.score == 0
    assert c.user == ""
    assert c.comment == ""
    assert c.time == ""
    assert c.is_uploader is False
    assert c.vote_up_able is False
    assert c.vote_down_able is False
    assert c.vote_up_ed is False
    assert c.vote_down_ed is False
    assert c.editable is False
    assert c.last_edited == ""


def test_gallery_comment_full():
    c = GalleryComment(
        id=456, score=-5, user="alice", comment="<p>Great!</p>",
        time="14 December 2023, 15:30", is_uploader=True,
        vote_up_able=True, vote_down_able=True,
        vote_up_ed=True, vote_down_ed=False,
        editable=True, last_edited="15 December 2023, 10:00"
    )
    assert c.id == 456
    assert c.score == -5
    assert c.is_uploader is True
    assert c.editable is True


def test_torrent_item():
    t = TorrentItem(url="https://example.com/t.torrent", name="gallery.torrent")
    assert t.url == "https://example.com/t.torrent"
    assert t.name == "gallery.torrent"


def test_archive_option():
    opt = ArchiveOption(cost="Free!", size="123 MB")
    assert opt.cost == "Free!"
    assert opt.size == "123 MB"
    assert opt.url == ""


def test_archiver_data_defaults():
    a = ArchiverData()
    assert a.original is None
    assert a.resample is None
    assert a.funds == ""


def test_archiver_data_full():
    a = ArchiverData(
        original=ArchiveOption(cost="20 GP", size="200 MB", url="https://a.com/dl"),
        resample=ArchiveOption(cost="10 GP", size="100 MB"),
        funds="1,234 GP / 5,678 Credits"
    )
    assert a.original.cost == "20 GP"
    assert a.resample.size == "100 MB"
    assert a.funds == "1,234 GP / 5,678 Credits"


def test_home_detail_defaults():
    h = HomeDetail()
    assert h.image_used == 0
    assert h.image_total == 0
    assert h.reset_cost == 0
    assert h.gp_from_gallery == 0
    assert h.gp_from_torrent == 0
    assert h.gp_from_archive == 0
    assert h.gp_from_hath == 0
    assert h.moderation_power == 0


def test_profile_result_defaults():
    p = ProfileResult()
    assert p.display_name == ""
    assert p.avatar_url == ""


def test_rate_result():
    r = RateResult(rating=4.5, rating_count=123)
    assert r.rating == 4.5
    assert r.rating_count == 123


def test_vote_comment_result():
    v = VoteCommentResult(comment_id=99, comment_score=-3, comment_vote=1)
    assert v.comment_id == 99
    assert v.comment_score == -3
    assert v.comment_vote == 1
