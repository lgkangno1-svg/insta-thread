from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from ..models import AnalyzeResponse, MediaAsset
from .cookie_support import cookie_file_path

try:
    import yt_dlp
except ImportError:  # pragma: no cover - startup/dev environment aid
    yt_dlp = None


VIDEO_HEIGHTS = (2160, 1440, 1080, 720, 480, 360)


def _base_opts() -> dict[str, Any]:
    # Keep extractor behavior deterministic and avoid playlists from accidental URLs.
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "cachedir": False,
        "socket_timeout": int(os.getenv("YTDLP_SOCKET_TIMEOUT", "30")),
        "retries": 2,
        "fragment_retries": 2,
        # yt-dlp's current YouTube EJS flow requires a supported JS runtime.
        "js_runtimes": {"node": {}},
    }
    pot_url = os.getenv("YTDLP_POT_PROVIDER_URL")
    if pot_url:
        opts["extractor_args"] = {
            "youtubepot-bgutilhttp": {"base_url": [pot_url]},
        }
    cookie_file = cookie_file_path()
    if cookie_file is not None:
        opts["cookiefile"] = str(cookie_file)
    return opts


def _ensure_ytdlp() -> None:
    if yt_dlp is None:
        raise HTTPException(status_code=503, detail="yt-dlp is not installed on the server")


def _extract(url: str) -> dict[str, Any]:
    _ensure_ytdlp()
    try:
        with yt_dlp.YoutubeDL(_base_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp has many extractor-specific subclasses
        raise HTTPException(status_code=422, detail=f"Could not analyze this media: {exc}") from exc
    if not info:
        raise HTTPException(status_code=422, detail="No media information returned")
    if info.get("_type") in {"playlist", "multi_video"} and info.get("entries"):
        entries = [x for x in info["entries"] if x]
        if len(entries) == 1:
            info = entries[0]
    return info


def _thumbnail_assets(info: dict[str, Any], limit: int = 8) -> list[MediaAsset]:
    candidates: list[dict[str, Any]] = []
    for thumb in info.get("thumbnails") or []:
        if not thumb.get("url"):
            continue
        candidates.append(thumb)
    if not candidates and info.get("thumbnail"):
        candidates.append({"url": info["thumbnail"]})

    # Prefer larger candidates while de-duplicating URLs.
    candidates.sort(key=lambda t: ((t.get("width") or 0) * (t.get("height") or 0), t.get("preference") or 0), reverse=True)
    seen: set[str] = set()
    assets: list[MediaAsset] = []
    for thumb in candidates:
        url = thumb.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        idx = len(assets)
        width = thumb.get("width")
        height = thumb.get("height")
        dims = f"{width}×{height}" if width and height else "thumbnail"
        ext = thumb.get("ext")
        assets.append(
            MediaAsset(
                id=f"thumbnail:{idx}",
                kind="thumbnail",
                label=f"Thumbnail {dims}",
                width=width,
                height=height,
                ext=ext,
                preview_url=url,
            )
        )
        if len(assets) >= limit:
            break
    return assets


def _available_heights(info: dict[str, Any]) -> set[int]:
    values: set[int] = set()
    for fmt in info.get("formats") or []:
        h = fmt.get("height")
        if isinstance(h, int) and h > 0:
            values.add(h)
    return values


def _video_assets(info: dict[str, Any], platform: str) -> list[MediaAsset]:
    heights = _available_heights(info)
    assets = [MediaAsset(id="video:best", kind="video", label="Best available", ext="mp4")]

    # YouTube benefits from explicit quality choices. Other short-form platforms
    # usually expose one practical progressive rendition, so keep the UI simple.
    if platform == "youtube":
        for h in VIDEO_HEIGHTS:
            if any(x >= h for x in heights):
                assets.append(MediaAsset(id=f"video:{h}", kind="video", label=f"Up to {h}p", height=h, ext="mp4"))
    return assets


def analyze(url: str, platform: str, include_thumbnails: bool = True) -> AnalyzeResponse:
    info = _extract(url)
    assets = _video_assets(info, platform)
    if include_thumbnails:
        assets.extend(_thumbnail_assets(info))
    return AnalyzeResponse(
        platform=platform,
        title=info.get("title") or info.get("description"),
        author=info.get("uploader") or info.get("channel") or info.get("creator"),
        webpage_url=info.get("webpage_url") or url,
        preview_url=info.get("thumbnail"),
        assets=assets,
    )


def _selector(asset_id: str) -> str:
    if asset_id == "video:best":
        return "bestvideo*+bestaudio/best"
    match = re.fullmatch(r"video:(\d{3,4})", asset_id)
    if match:
        h = int(match.group(1))
        return f"bestvideo*[height<={h}]+bestaudio/best[height<={h}]"
    raise HTTPException(status_code=400, detail="Invalid video asset id")


def _cleanup(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def prepare_video(url: str, asset_id: str, max_size_mb: int = 1000, tmp_root: str | None = None) -> tuple[Path, str]:
    _ensure_ytdlp()
    tmpdir = tempfile.mkdtemp(prefix="insta-thread-", dir=tmp_root or None)
    outtmpl = str(Path(tmpdir) / "%(title).120B [%(id)s].%(ext)s")
    opts = _base_opts()
    opts.update(
        {
            "skip_download": False,
            "format": _selector(asset_id),
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "max_filesize": max_size_mb * 1024 * 1024,
            "overwrites": True,
        }
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
        files = [p for p in Path(tmpdir).iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl"))]
        if not files:
            raise HTTPException(status_code=422, detail="Download completed without an output file")
        path = max(files, key=lambda p: p.stat().st_size)
        if path.stat().st_size > max_size_mb * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Output exceeds server file-size limit")
        return path, tmpdir
    except HTTPException:
        _cleanup(tmpdir)
        raise
    except Exception as exc:
        _cleanup(tmpdir)
        raise HTTPException(status_code=422, detail=f"Download failed: {exc}") from exc


def resolve_thumbnail(url: str, asset_id: str) -> tuple[str, str]:
    info = _extract(url)
    assets = _thumbnail_assets(info)
    wanted = next((a for a in assets if a.id == asset_id), None)
    if not wanted or not wanted.preview_url:
        raise HTTPException(status_code=404, detail="Thumbnail is no longer available")
    ext = wanted.ext or "jpg"
    return wanted.preview_url, ext
