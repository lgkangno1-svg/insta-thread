from app.platforms import douyin_adapter


def _router_page(aweme_id: str) -> str:
    return f'''<html><body><script>
    window._ROUTER_DATA = {{"loaderData":{{"video_({aweme_id})/page":{{"videoInfoRes":{{"item_list":[{{
      "aweme_id":"{aweme_id}",
      "desc":"public test video",
      "author":{{"nickname":"tester"}},
      "video":{{
        "width":1080,
        "height":1920,
        "play_addr":{{"url_list":["http://v.example.com/video.mp4"]}},
        "cover":{{"url_list":["https://img.example.com/cover.webp"]}}
      }}
    }}]}}}}}}}};
    </script></body></html>'''


def test_extract_router_data_and_find_item():
    aweme_id = "7683794436208121033"
    data = douyin_adapter._extract_router_data(_router_page(aweme_id))
    item = douyin_adapter._find_item(data, aweme_id)
    assert item is not None
    assert item["desc"] == "public test video"
    assert douyin_adapter._video_urls(item) == ["https://v.example.com/video.mp4"]
    assert douyin_adapter._cover_urls(item) == ["https://img.example.com/cover.webp"]


def test_analyze_uses_public_ssr_media(monkeypatch):
    aweme_id = "7683794436208121033"
    page = _router_page(aweme_id)

    class Response:
        text = page
        def raise_for_status(self):
            return None

    class Client:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return None
        def get(self, url):
            assert url == f"https://www.iesdouyin.com/share/video/{aweme_id}/?from_ssr=1"
            return Response()

    monkeypatch.setattr(douyin_adapter.httpx, "Client", Client)
    result = douyin_adapter.analyze(f"https://www.douyin.com/video/{aweme_id}")
    assert result.platform == "douyin"
    assert result.title == "public test video"
    assert result.author == "tester"
    assert [asset.id for asset in result.assets] == ["video:best", "thumbnail:0"]
    assert result.assets[0].width == 1080
    assert result.assets[0].height == 1920


def test_resolve_asset_uses_public_video_url(monkeypatch):
    aweme_id = "7683794436208121033"
    item = {
        "aweme_id": aweme_id,
        "video": {
            "play_addr": {"url_list": ["https://v.example.com/video.mp4"]},
            "cover": {"url_list": ["https://img.example.com/cover.webp"]},
        },
    }
    monkeypatch.setattr(douyin_adapter, "_fetch_item", lambda _url: (item, aweme_id))
    assert douyin_adapter.resolve_asset(f"https://www.douyin.com/video/{aweme_id}", "video:best") == (
        "https://v.example.com/video.mp4",
        "mp4",
    )
    assert douyin_adapter.resolve_asset(f"https://www.douyin.com/video/{aweme_id}", "thumbnail:0") == (
        "https://img.example.com/cover.webp",
        "webp",
    )
