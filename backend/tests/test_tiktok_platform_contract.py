"""TikTok public-post support: isolated, offline contract regression."""
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.platforms.router import detect_platform, extract_supported_url
from app.platforms import share_resolver, ytdlp_adapter
from app.services import downloader


CANON = "https://www.tiktok.com/@scout2015/video/6718335390845095173"


@pytest.mark.parametrize("raw", [
    CANON,
    "https://m.tiktok.com/@scout2015/video/6718335390845095173",
    "https://vm.tiktok.com/ZMxxxxxxxx/",
    "https://vt.tiktok.com/ZMxxxxxxxx/",
    "Copy this TikTok video: https://www.tiktok.com/@scout2015/video/6718335390845095173?is_from_webapp=1!",
])
def test_public_tiktok_links_are_routed(raw):
    assert detect_platform(raw).platform == "tiktok"
    assert "tiktok.com/" in extract_supported_url(raw)


@pytest.mark.parametrize("raw", [
    "https://www.tiktok.com.evil.test/@user/video/6718335390845095173",
    "https://private.tiktok.com/@user/video/6718335390845095173",
    "file:///etc/passwd",
    "https://user:pass@tiktok.com/@user/video/6718335390845095173",
])
def test_tiktok_unsafe_hosts_or_credentials_rejected(raw):
    with pytest.raises(HTTPException) as exc:
        detect_platform(raw)
    assert exc.value.status_code == 400


def test_tiktok_shortlink_requires_official_redirect_resolution():
    assert share_resolver.needs_resolution("https://vm.tiktok.com/ZMxxxxxxxx/", "tiktok")
    assert share_resolver.needs_resolution("https://vt.tiktok.com/ZMxxxxxxxx/", "tiktok")
    assert not share_resolver.needs_resolution(CANON, "tiktok")
    assert share_resolver._is_media_path(CANON, "tiktok")
    allowed=share_resolver._ALLOWED_REDIRECT_HOSTS["tiktok"]
    assert share_resolver._validate_target(CANON, "tiktok", allowed)==CANON
    with pytest.raises(HTTPException):
        share_resolver._validate_target("https://evil.example/video/1234", "tiktok", allowed)
    with pytest.raises(HTTPException):
        share_resolver._validate_target("https://www.douyin.com/video/7534679152504376595", "tiktok", allowed)


def test_public_tiktok_analysis_reuses_existing_ytdlp(monkeypatch):
    seen=[]
    def fake_extract(url):
        seen.append(url)
        return {
            "id":"6718335390845095173",
            "title":"Public video test fixture",
            "uploader":"fixture-creator",
            "webpage_url":CANON,
            "thumbnail":"https://cdn.example.test/cover.webp",
            "thumbnails":[{"url":"https://cdn.example.test/cover.webp","width":400,"height":720,"ext":"webp"}],
            "formats":[{"height":720, "ext":"mp4"}],
        }
    monkeypatch.setattr(ytdlp_adapter, "_extract", fake_extract)
    result=downloader.analyze(CANON)
    assert result.platform=="tiktok"
    assert any(a.kind=="video" and a.id=="video:best" for a in result.assets)
    assert any(a.kind=="thumbnail" and a.id=="thumbnail:0" for a in result.assets)
    assert result.analysis_token
    assert result.source_url==CANON
    assert seen==[CANON]
    downloader.validate_asset_id(CANON,"video:best")
    downloader.validate_asset_id(CANON,"thumbnail:0")
    with pytest.raises(HTTPException) as exc:
        downloader.validate_asset_id(CANON,"video:9999")
    assert exc.value.status_code==400


def test_tiktok_download_job_uses_ytdlp_without_custom_scraper(monkeypatch,tmp_path):
    called=[]
    def fake_prepare(url,asset_id,**kwargs):
        called.append((url,asset_id,kwargs))
        return tmp_path/"test.mp4",str(tmp_path)
    monkeypatch.setattr(ytdlp_adapter,"prepare_video",fake_prepare)
    path,tmp=downloader.prepare(CANON,"video:best",tmp_root=str(tmp_path))
    assert path==tmp_path/"test.mp4"
    assert tmp==str(tmp_path)
    assert called[0][0]==CANON and called[0][1]=="video:best"


def test_tiktok_thumbnail_routes_into_generic_safe_fetch(monkeypatch,tmp_path):
    called=[]
    monkeypatch.setattr(ytdlp_adapter,"resolve_thumbnail",lambda url,asset_id:("https://cdn.example.test/thumb.webp","webp"))
    monkeypatch.setattr(downloader,"prepare_resolved_media",
        lambda source,ext,**kw:(called.append((source,ext,kw)) or (tmp_path/"thumb.webp",str(tmp_path))))
    path,_=downloader.prepare(CANON,"thumbnail:0",tmp_root=str(tmp_path))
    assert path.name=="thumb.webp"
    assert called[0][0]=="https://cdn.example.test/thumb.webp"


def test_public_tiktok_never_inherits_unrelated_login_cookies(monkeypatch,tmp_path):
    monkeypatch.setattr(ytdlp_adapter,"cookie_file_path",lambda:tmp_path/"private-cookie.txt")
    assert "cookiefile" not in ytdlp_adapter._base_opts(CANON)
    assert "Chrome/140.0.0.0" in ytdlp_adapter._base_opts(CANON)["http_headers"]["User-Agent"]
    assert "http_headers" not in ytdlp_adapter._base_opts("https://www.youtube.com/watch?v=abc")
    # Legacy YouTube behavior is retained without exposing any cookie material.
    assert ytdlp_adapter._base_opts("https://www.youtube.com/watch?v=abc")["cookiefile"].endswith("private-cookie.txt")


def test_tiktok_shortlink_does_not_load_any_login_cookies(monkeypatch):
    captured={}
    class FakeClient:
        def __init__(self,**kwargs):
            captured.update(kwargs)
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def get(self,url):
            from httpx import Response,Request
            if url == CANON:
                return Response(200,request=Request("GET",url),text="<html></html>")
            return Response(302,request=Request("GET",url),headers={"location":CANON})
    monkeypatch.setattr(share_resolver.httpx,"Client",FakeClient)
    monkeypatch.setattr(share_resolver,"httpx_guest_cookies",lambda:{"session":"not-for-tiktok"})
    assert share_resolver.resolve_share_url("https://vm.tiktok.com/ZMxxxxxx/")==CANON
    assert captured["cookies"]=={}
