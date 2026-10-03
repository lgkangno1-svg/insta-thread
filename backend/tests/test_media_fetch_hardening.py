from app.services.media_fetch import _content_length


def test_content_length_parser_tolerates_cdn_variants():
    assert _content_length("877722") == 877722
    assert _content_length(" 877722 ") == 877722
    assert _content_length(None) == 0
    assert _content_length("") == 0
    assert _content_length("chunked") == 0
    assert _content_length("-1") == 0
