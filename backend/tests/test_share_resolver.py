import pytest
from fastapi import HTTPException

from app.platforms import share_resolver


class FakeResponse:
    def __init__(self, status_code, location=None, text=""):
        self.status_code = status_code
        self.headers = {"location": location} if location else {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, responses, *args, **kwargs):
        self.responses = list(responses)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, _url):
        return self.responses.pop(0)


def test_xhs_short_link_resolves_profile_note_to_canonical_url(monkeypatch):
    responses = [
        FakeResponse(
            302,
            "https://www.xiaohongshu.com/user/profile/author123/6a73dffa000000002c006ead?xsec_token=keep=&xsec_source=app_share",
        ),
        FakeResponse(200),
    ]
    monkeypatch.setattr(share_resolver.httpx, "Client", lambda *a, **k: FakeClient(responses))
    result = share_resolver.resolve_share_url("https://xhslink.com/m/abc")
    assert result == (
        "https://www.xiaohongshu.com/explore/6a73dffa000000002c006ead?"
        "xsec_token=keep=&xsec_source=app_share"
    )


def test_instagram_share_wrapper_resolves_redirect_to_reel(monkeypatch):
    responses = [
        FakeResponse(302, "https://www.instagram.com/reel/Ab_Cd/?igsh=test"),
        FakeResponse(200),
    ]
    monkeypatch.setattr(share_resolver.httpx, "Client", lambda *a, **k: FakeClient(responses))
    assert share_resolver.resolve_share_url("https://www.instagram.com/share/xyz") == (
        "https://www.instagram.com/reel/Ab_Cd/?igsh=test"
    )


def test_instagram_share_wrapper_resolves_200_canonical_page(monkeypatch):
    page = '<html><head><link href="https://www.instagram.com/reel/Real_Code/?igsh=abc&amp;utm_source=share" rel="canonical"></head></html>'
    responses = [FakeResponse(200, text=page)]
    monkeypatch.setattr(share_resolver.httpx, "Client", lambda *a, **k: FakeClient(responses))
    assert share_resolver.resolve_share_url("https://www.instagram.com/share/reel/opaque") == (
        "https://www.instagram.com/reel/Real_Code/?igsh=abc&utm_source=share"
    )


def test_threads_short_wrapper_resolves_200_canonical_page(monkeypatch):
    page = '<meta property="og:url" content="https://www.threads.com/@creator/post/Ab_Cd-123?xmt=test">'
    responses = [FakeResponse(200, text=page)]
    monkeypatch.setattr(share_resolver.httpx, "Client", lambda *a, **k: FakeClient(responses))
    assert share_resolver.resolve_share_url("https://www.threads.com/t/Ab_Cd-123") == (
        "https://www.threads.com/@creator/post/Ab_Cd-123?xmt=test"
    )


def test_expired_short_link_landing_on_home_is_rejected(monkeypatch):
    responses = [
        FakeResponse(302, "https://www.xiaohongshu.com/"),
        FakeResponse(200, text='<link rel="canonical" href="https://www.xiaohongshu.com/explore">'),
    ]
    monkeypatch.setattr(share_resolver.httpx, "Client", lambda *a, **k: FakeClient(responses))
    with pytest.raises(HTTPException) as exc:
        share_resolver.resolve_share_url("https://xhslink.com/m/expired")
    assert exc.value.status_code == 422
    assert "no longer resolves" in str(exc.value.detail)


def test_douyin_caption_short_link_resolution(monkeypatch):
    responses = [
        FakeResponse(302, "https://www.douyin.com/video/1234567890123456789"),
        FakeResponse(200),
    ]
    monkeypatch.setattr(share_resolver.httpx, "Client", lambda *a, **k: FakeClient(responses))
    raw = "复制打开抖音 https://v.douyin.com/AbCdEf/ 看看视频"
    assert share_resolver.resolve_share_url(raw) == "https://www.douyin.com/video/1234567890123456789"


def test_share_wrapper_rejects_cross_platform_or_external_redirect(monkeypatch):
    responses = [FakeResponse(302, "http://127.0.0.1:8080/private")]
    monkeypatch.setattr(share_resolver.httpx, "Client", lambda *a, **k: FakeClient(responses))
    with pytest.raises(HTTPException) as exc:
        share_resolver.resolve_share_url("https://xhslink.com/m/abc")
    assert exc.value.status_code == 422


def test_direct_youtube_short_url_does_not_need_pre_resolution():
    assert share_resolver.needs_resolution("https://youtu.be/abc", "youtube") is False
