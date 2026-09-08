import pytest
from fastapi import HTTPException

from app.platforms.router import detect_platform


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://www.instagram.com/reel/abc/", "instagram"),
        ("https://www.xiaohongshu.com/explore/abc", "xiaohongshu"),
        ("https://www.threads.com/@name/post/abc", "threads"),
        ("https://www.threads.net/@name/post/abc", "threads"),
        ("https://www.douyin.com/video/123", "douyin"),
        ("https://v.douyin.com/abc/", "douyin"),
    ],
)
def test_supported_platforms(url, expected):
    assert detect_platform(url).platform == expected


def test_rejects_unknown_domain():
    with pytest.raises(HTTPException) as exc:
        detect_platform("https://example.com/video")
    assert exc.value.status_code == 400


def test_rejects_non_http_scheme():
    with pytest.raises(HTTPException):
        detect_platform("file:///etc/passwd")
