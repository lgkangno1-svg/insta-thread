from pathlib import Path

import pytest
from fastapi import HTTPException

from app.services import downloader


YOUTUBE = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"


def test_youtube_thumbnail_is_valid_asset():
    downloader.validate_asset_id(YOUTUBE, "thumbnail:0")
    downloader.validate_asset_id(YOUTUBE, "thumbnail:7")
    downloader.validate_asset_id(YOUTUBE, "video:best")


@pytest.mark.parametrize("asset", ["thumbnail:-1", "thumbnail:x", "image:0"])
def test_youtube_thumbnail_rejects_invalid_asset_ids(asset):
    with pytest.raises(HTTPException) as exc:
        downloader.validate_asset_id(YOUTUBE, asset)
    assert exc.value.status_code == 400


def test_youtube_thumbnail_dispatches_to_existing_safe_media_fetch(monkeypatch):
    expected_url = "https://i.ytimg.com/vi/example/maxresdefault.jpg"
    monkeypatch.setattr(downloader, "_urls", lambda value: (value, value))
    monkeypatch.setattr(downloader.ytdlp_adapter, "resolve_thumbnail", lambda url, asset: (expected_url, "jpg"))
    calls = []
    def fake_fetch(url, ext, **kwargs):
        calls.append((url, ext, kwargs))
        return Path("/tmp/thumbnail.jpg"), "/tmp/thumbnail-dir"
    monkeypatch.setattr(downloader, "prepare_resolved_media", fake_fetch)
    path, tempdir = downloader.prepare(YOUTUBE, "thumbnail:0")
    assert path.name == "thumbnail.jpg"
    assert tempdir == "/tmp/thumbnail-dir"
    assert calls[0][0:2] == (expected_url, "jpg")
