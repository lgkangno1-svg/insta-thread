from app.platforms.router import detect_platform, extract_supported_url
from app.platforms import xiaohongshu_adapter


def test_observed_xhs_pc_feed_explore_url_is_preserved():
    raw = (
        "https://www.xiaohongshu.com/explore/67adf355000000002903897e?"
        "xsec_token=CBN7UgqNCyw61T0_AIiBV1doeZNxFgnqmA-rFyxVZ070Q="
        "&xsec_source=pc_feed"
    )
    assert extract_supported_url(raw) == raw
    assert detect_platform(raw).platform == "xiaohongshu"
    assert xiaohongshu_adapter._extract_note_id(raw) == "67adf355000000002903897e"


def test_xhs_candidate_pages_preserve_raw_query_token_padding():
    raw = (
        "https://www.xiaohongshu.com/explore/67adf355000000002903897e?"
        "xsec_token=token-with-padding=&xsec_source=pc_feed"
    )
    candidates = xiaohongshu_adapter._candidate_note_pages(raw, "67adf355000000002903897e")
    assert candidates[0] == raw
    assert any("/discovery/item/67adf355000000002903897e?" in item for item in candidates)
    assert all("xsec_token=token-with-padding=" in item for item in candidates)
    assert all(item.endswith("xsec_source=pc_feed") for item in candidates)
