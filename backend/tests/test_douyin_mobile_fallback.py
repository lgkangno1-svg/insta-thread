"""Douyin fallback must accept only exact public media, without fake success."""
from fastapi import HTTPException
import pytest

from app.platforms import douyin_adapter


AWEME = "7699487756020750335"
OTHER = "7694152397853930383"


def _media(aweme_id=AWEME):
    return {
        "aweme_id": aweme_id,
        "desc": "Public October sample",
        "video": {
            "play_addr": {"url_list": ["https://v3-dy-o.zjcdn.com/sample.mp4"]},
            "cover": {"url_list": ["https://p5-sign.douyinpic.com/cover.jpg"]},
        },
    }


class FakeResult:
    def __init__(self, payload):
        self.status_code = 200
        self.payload = payload

    def json(self):
        return self.payload


class FakeMobileClient:
    seen = []
    payloads = []

    def __init__(self, *args, **kwargs):
        assert kwargs["follow_redirects"] is False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def get(self, url, params):
        self.seen.append((url, params))
        return FakeResult(self.payloads.pop(0))


def test_mobile_feed_returns_matching_public_video(monkeypatch):
    FakeMobileClient.seen = []
    FakeMobileClient.payloads = [{"aweme_list": [_media(OTHER), _media()]}]
    monkeypatch.setattr(douyin_adapter.httpx, "Client", FakeMobileClient)
    item = douyin_adapter._fetch_mobile_feed_item(AWEME)
    assert item["aweme_id"] == AWEME
    assert len(FakeMobileClient.seen) == 1
    assert FakeMobileClient.seen[0][1] == {"aweme_id": AWEME, "aid": "1128"}


def test_mobile_feed_uses_second_node_and_refuses_unrelated_items(monkeypatch):
    FakeMobileClient.seen = []
    FakeMobileClient.payloads = [
        {"aweme_list": [_media(OTHER)]},
        {"aweme_list": [_media()]},
    ]
    monkeypatch.setattr(douyin_adapter.httpx, "Client", FakeMobileClient)
    assert douyin_adapter._fetch_mobile_feed_item(AWEME)["aweme_id"] == AWEME
    assert len(FakeMobileClient.seen) == 2


def test_mobile_feed_no_matching_media_is_not_success(monkeypatch):
    FakeMobileClient.seen = []
    FakeMobileClient.payloads = [
        {"aweme_list": [_media(OTHER)]},
        {"aweme_list": [{"aweme_id": AWEME, "video": {}}]},
    ]
    monkeypatch.setattr(douyin_adapter.httpx, "Client", FakeMobileClient)
    assert douyin_adapter._fetch_mobile_feed_item(AWEME) is None


def test_share_without_media_falls_back_to_mobile(monkeypatch):
    class EmptySSR:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, url):
            class Page:
                text = '<script>window._ROUTER_DATA={"loaderData":{}};</script>'
                def raise_for_status(self):
                    pass
            return Page()

    monkeypatch.setattr(douyin_adapter.httpx, "Client", EmptySSR)
    monkeypatch.setattr(douyin_adapter, "_fetch_mobile_feed_item", lambda _id: _media())
    a = douyin_adapter.analyze("https://www.douyin.com/video/" + AWEME)
    assert a.platform == "douyin"
    assert a.assets[0].id == "video:best"
    assert a.assets[0].kind == "video"


def test_non_public_unresolved_media_returns_422(monkeypatch):
    class EmptySSR:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def get(self, url):
            class Page:
                text = "<html></html>"
                def raise_for_status(self):
                    pass
            return Page()
    monkeypatch.setattr(douyin_adapter.httpx, "Client", EmptySSR)
    monkeypatch.setattr(douyin_adapter, "_fetch_mobile_feed_item", lambda _id: None)
    with pytest.raises(HTTPException) as exc:
        douyin_adapter.analyze("https://www.douyin.com/video/" + AWEME)
    assert exc.value.status_code == 422
