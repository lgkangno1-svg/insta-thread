from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException

from ..platforms import threads_adapter, ytdlp_adapter
from ..platforms.router import detect_platform
from .media_fetch import download_resolved_media, prepare_resolved_media


def analyze(url: str):
    route = detect_platform(url)
    if route.platform == "threads":
        return threads_adapter.analyze(url)
    # Final product scope requests cover/thumbnail choices for Instagram and Douyin.
    include_thumbnails = route.platform in {"instagram", "douyin"}
    return ytdlp_adapter.analyze(url, route.platform, include_thumbnails=include_thumbnails)


def validate_asset_id(url: str, asset_id: str) -> None:
    route = detect_platform(url)
    if route.platform == "threads":
        if not re.fullmatch(r"asset:\d+", asset_id):
            raise HTTPException(status_code=400, detail="Invalid Threads asset selection")
        return
    if re.fullmatch(r"video:(?:best|\d{3,4})", asset_id):
        return
    if route.platform in {"instagram", "douyin"} and re.fullmatch(r"thumbnail:\d+", asset_id):
        return
    raise HTTPException(status_code=400, detail="Invalid asset selection for this platform")


def prepare(url: str, asset_id: str, tmp_root: str | None = None) -> tuple[Path, str]:
    route = detect_platform(url)
    validate_asset_id(url, asset_id)
    if route.platform == "threads":
        source, ext = threads_adapter.resolve_asset(url, asset_id)
        return prepare_resolved_media(source, ext, tmp_root=tmp_root, referer="https://www.threads.com/")
    if asset_id.startswith("thumbnail:"):
        source, ext = ytdlp_adapter.resolve_thumbnail(url, asset_id)
        referer = "https://www.instagram.com/" if route.platform == "instagram" else "https://www.douyin.com/"
        return prepare_resolved_media(source, ext, tmp_root=tmp_root, referer=referer)
    return ytdlp_adapter.prepare_video(url, asset_id, tmp_root=tmp_root)


def download(url: str, asset_id: str):
    route = detect_platform(url)
    validate_asset_id(url, asset_id)
    if route.platform == "threads":
        source, ext = threads_adapter.resolve_asset(url, asset_id)
        return download_resolved_media(source, ext, referer="https://www.threads.com/")
    if asset_id.startswith("thumbnail:"):
        source, ext = ytdlp_adapter.resolve_thumbnail(url, asset_id)
        referer = "https://www.instagram.com/" if route.platform == "instagram" else "https://www.douyin.com/"
        return download_resolved_media(source, ext, referer=referer)
    if asset_id.startswith("video:"):
        return ytdlp_adapter.download_video(url, asset_id)
    raise HTTPException(status_code=400, detail="Unsupported asset selection")
