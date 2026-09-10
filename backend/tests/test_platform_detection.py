import pytest
from fastapi import HTTPException

from app.platforms.router import detect_platform, extract_supported_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://www.youtube.com/shorts/abc?si=token", "youtube"),
        ("https://www.instagram.com/reel/abc/", "instagram"),
        ("https://www.instagram.com/reels/abc/?igsh=test", "instagram"),
        ("https://www.instagram.com/share/abc", "instagram"),
        ("https://www.xiaohongshu.com/explore/6a73dffa000000002c006ead", "xiaohongshu"),
        ("https://www.rednote.com/explore/6a73dffa000000002c006ead", "xiaohongshu"),
        ("https://xhslink.com/m/1gJ5tOG6M1b", "xiaohongshu"),
        ("https://www.threads.com/@name/post/abc", "threads"),
        ("https://www.threads.com/share/abc", "threads"),
        ("https://www.threads.net/@name/post/abc", "threads"),
        ("https://www.douyin.com/video/7534679152504376595", "douyin"),
        ("https://www.douyin.com/note/7534679152504376595", "douyin"),
        ("https://www.douyin.com/jingxuan?modal_id=7534679152504376595", "douyin"),
        ("https://v.douyin.com/abc/", "douyin"),
        ("https://www.iesdouyin.com/share/video/7534679152504376595", "douyin"),
    ],
)
def test_supported_platforms(url, expected):
    assert detect_platform(url).platform == expected


def test_extracts_observed_xiaohongshu_pc_feed_explore_url_unchanged():
    raw = (
        "https://www.xiaohongshu.com/explore/67adf355000000002903897e?"
        "xsec_token=CBN7UgqNCyw61T0_AIiBV1doeZNxFgnqmA-rFyxVZ070Q="
        "&xsec_source=pc_feed"
    )
    assert extract_supported_url(raw) == raw
    assert detect_platform(raw).platform == "xiaohongshu"


def test_extracts_xiaohongshu_url_from_pc_share_text_and_preserves_token_padding():
    raw = (
        "54 [叠加收纳不浪费，橱柜又多出一倍空间‼️ - creator | rednote] "
        "sharecode https://www.xiaohongshu.com/discovery/item/6a8cfcaa000000002a026526?"
        "source=webshare&xhsshare=pc_web&xsec_token=example-token-with-padding=&xsec_source=pc_share"
    )
    extracted = extract_supported_url(raw)
    assert extracted.startswith("https://www.xiaohongshu.com/discovery/item/6a8cfcaa000000002a026526?")
    assert "xsec_token=example-token-with-padding=" in extracted
    assert extracted.endswith("xsec_source=pc_share")


@pytest.mark.parametrize(
    ("raw", "expected_platform", "url_piece"),
    [
        ("复制打开抖音，看看这个视频 https://v.douyin.com/AbCdEf/ 03/08", "douyin", "v.douyin.com/AbCdEf/"),
        ("Watch this ▶ https://youtu.be/AbCdEf?t=32", "youtube", "youtu.be/AbCdEf?t=32"),
        ("Shared from Instagram https://www.instagram.com/reel/Ab_Cd/?igsh=abc123", "instagram", "/reel/Ab_Cd/"),
        ("Threads post https://www.threads.com/share/AbCdEf?xmt=abc", "threads", "/share/AbCdEf"),
        ("小红书分享 xhslink.com/m/1gJ5tOG6M1b 复制后打开", "xiaohongshu", "xhslink.com/m/1gJ5tOG6M1b"),
    ],
)
def test_extracts_supported_url_from_full_share_message(raw, expected_platform, url_piece):
    extracted = extract_supported_url(raw)
    assert url_piece in extracted
    assert detect_platform(raw).platform == expected_platform


def test_xhs_profile_note_url_is_canonicalized_and_keeps_token():
    raw = "https://www.xiaohongshu.com/user/profile/5bbe0958abc123/6a73dffa000000002c006ead?xsec_token=keep-me&xsec_source=app_share"
    extracted = extract_supported_url(raw)
    assert extracted == (
        "https://www.xiaohongshu.com/explore/6a73dffa000000002c006ead?"
        "xsec_token=keep-me&xsec_source=app_share"
    )


def test_rednote_note_url_maps_to_xiaohongshu_and_keeps_query():
    raw = "https://www.rednote.com/explore/6a73dffa000000002c006ead?xsec_token=keep-me"
    extracted = extract_supported_url(raw)
    assert extracted == "https://www.xiaohongshu.com/explore/6a73dffa000000002c006ead?xsec_token=keep-me"


def test_bare_xhs_note_id_is_accepted():
    assert extract_supported_url("6A73DFFA000000002C006EAD") == "https://www.xiaohongshu.com/explore/6a73dffa000000002c006ead"


def test_douyin_modal_note_legacy_and_bare_ids_are_canonicalized():
    aweme_id = "7534679152504376595"
    expected = f"https://www.douyin.com/video/{aweme_id}"
    assert extract_supported_url(f"https://www.douyin.com/jingxuan?modal_id={aweme_id}") == expected
    assert extract_supported_url(f"https://www.douyin.com/discover?modal_id={aweme_id}") == expected
    assert extract_supported_url(f"https://www.douyin.com/note/{aweme_id}") == expected
    assert extract_supported_url(f"https://www.iesdouyin.com/share/video/{aweme_id}") == expected
    assert extract_supported_url(aweme_id) == expected


def test_skips_unrelated_url_and_uses_supported_url():
    raw = "Info https://example.com/x then https://www.youtube.com/watch?v=abc."
    assert extract_supported_url(raw) == "https://www.youtube.com/watch?v=abc"


def test_rejects_unknown_domain():
    with pytest.raises(HTTPException) as exc:
        detect_platform("https://example.com/video")
    assert exc.value.status_code == 400


def test_rejects_non_http_scheme():
    with pytest.raises(HTTPException):
        detect_platform("file:///etc/passwd")


def test_rejects_credentials_in_supported_url():
    with pytest.raises(HTTPException):
        extract_supported_url("https://user:pass@youtube.com/watch?v=abc")
