from __future__ import annotations

import os
import re
from pathlib import Path

from fastapi import HTTPException

from ..platforms import instagram_adapter, threads_adapter, xiaohongshu_adapter, ytdlp_adapter
from ..platforms.router import detect_platform, extract_supported_url
from ..security import issue_analysis_token, sponsor_gate_enabled, sponsor_gate_seconds
from .media_fetch import (
    download_resolved_archive,
    download_resolved_media,
    prepare_resolved_archive,
    prepare_resolved_media,
)


def _max_media_mb() -> int:
    try:
        value = int(os.getenv("MAX_MEDIA_MB", "750"))
    except ValueError:
        value = 750
    return max(50, min(value, 2000))


def analyze(url: str):
    normalized_url = extract_supported_url(url)
    route = detect_platform(normalized_url)
    if route.platform == "threads":
        result = threads_adapter.analyze(normalized_url)
    elif route.platform == "instagram":
        result = instagram_adapter.analyze(normalized_url)
    elif route.platform == "xiaohongshu":
        result = xiaohongshu_adapter.analyze(normalized_url)
    else:
        include_thumbnails = route.platform == "douyin"
        result = ytdlp_adapter.analyze(normalized_url, route.platform, include_thumbnails=include_thumbnails)

    # Bind the ticket to the exact normalized URL returned by the common parser.
    # The browser normalizes before submitting, while direct API clients may paste
    # a full share message; in either case the job path reuses the same parser.
    token = issue_analysis_token(normalized_url, [asset.id for asset in result.assets])
    return result.model_copy(update={
        "analysis_token": token,
        "source_url": normalized_url,
        "sponsor_gate_enabled": sponsor_gate_enabled(),
        "gate_seconds": sponsor_gate_seconds(),
    })


def validate_asset_id(url: str, asset_id: str) -> None:
    route = detect_platform(url)
    if route.platform == "threads":
        if not re.fullmatch(r"asset:\d+", asset_id):
            raise HTTPException(status_code=400, detail="Invalid Threads asset selection")
        return
    if route.platform == "xiaohongshu":
        if asset_id in {"video:best", "images:zip"} or re.fullmatch(r"image:\d+", asset_id):
            return
        raise HTTPException(status_code=400, detail="Invalid Xiaohongshu asset selection")
    if re.fullmatch(r"video:(?:best|\d{3,4})", asset_id):
        return
    if route.platform in {"instagram", "douyin"} and re.fullmatch(r"thumbnail:\d+", asset_id):
        return
    raise HTTPException(status_code=400, detail="Invalid asset selection for this platform")


def prepare(url: str, asset_id: str, tmp_root: str | None = None) -> tuple[Path, str]:
    normalized_url = extract_supported_url(url)
    route = detect_platform(normalized_url)
    validate_asset_id(normalized_url, asset_id)
    max_size_mb = _max_media_mb()
    if route.platform == "threads":
        source, ext = threads_adapter.resolve_asset(normalized_url, asset_id)
        return prepare_resolved_media(source, ext, max_size_mb=max_size_mb, tmp_root=tmp_root, referer="https://www.threads.com/")
    if route.platform == "instagram":
        source, ext = instagram_adapter.resolve_asset(normalized_url, asset_id)
        return prepare_resolved_media(source, ext, max_size_mb=max_size_mb, tmp_root=tmp_root, referer="https://www.instagram.com/")
    if route.platform == "xiaohongshu":
        if asset_id == "images:zip":
            items = xiaohongshu_adapter.resolve_all_images(normalized_url)
            return prepare_resolved_archive(
                items,
                max_size_mb=max_size_mb,
                tmp_root=tmp_root,
                referer="https://www.xiaohongshu.com/",
                filename="xiaohongshu-images.zip",
            )
        source, ext = xiaohongshu_adapter.resolve_asset(normalized_url, asset_id)
        return prepare_resolved_media(source, ext, max_size_mb=max_size_mb, tmp_root=tmp_root, referer="https://www.xiaohongshu.com/")
    if asset_id.startswith("thumbnail:"):
        source, ext = ytdlp_adapter.resolve_thumbnail(normalized_url, asset_id)
        return prepare_resolved_media(source, ext, max_size_mb=max_size_mb, tmp_root=tmp_root, referer="https://www.douyin.com/")
    return ytdlp_adapter.prepare_video(normalized_url, asset_id, max_size_mb=max_size_mb, tmp_root=tmp_root)


def download(url: str, asset_id: str):
    normalized_url = extract_supported_url(url)
    route = detect_platform(normalized_url)
    validate_asset_id(normalized_url, asset_id)
    max_size_mb = _max_media_mb()
    if route.platform == "threads":
        source, ext = threads_adapter.resolve_asset(normalized_url, asset_id)
        return download_resolved_media(source, ext, max_size_mb=max_size_mb, referer="https://www.threads.com/")
    if route.platform == "instagram":
        source, ext = instagram_adapter.resolve_asset(normalized_url, asset_id)
        return download_resolved_media(source, ext, max_size_mb=max_size_mb, referer="https://www.instagram.com/")
    if route.platform == "xiaohongshu":
        if asset_id == "images:zip":
            items = xiaohongshu_adapter.resolve_all_images(normalized_url)
            return download_resolved_archive(
                items,
                max_size_mb=max_size_mb,
                referer="https://www.xiaohongshu.com/",
                filename="xiaohongshu-images.zip",
            )
        source, ext = xiaohongshu_adapter.resolve_asset(normalized_url, asset_id)
        return download_resolved_media(source, ext, max_size_mb=max_size_mb, referer="https://www.xiaohongshu.com/")
    if asset_id.startswith("thumbnail:"):
        source, ext = ytdlp_adapter.resolve_thumbnail(normalized_url, asset_id)
        return download_resolved_media(source, ext, max_size_mb=max_size_mb, referer="https://www.douyin.com/")
    if asset_id.startswith("video:"):
        return ytdlp_adapter.download_video(normalized_url, asset_id, max_size_mb=max_size_mb)
    raise HTTPException(status_code=400, detail="Unsupported asset selection")
