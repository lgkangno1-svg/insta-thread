from __future__ import annotations

import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any

from core import Asset, sanitize_filename, unique_path

_APP_DIR = "AVOCADOSS Downloader"
_SETTINGS_FILE = "settings.json"
_GENERIC_STEMS = {
    "download",
    "downloaded",
    "file",
    "media",
    "output",
    "video",
    "image",
    "avocadoss-download",
}
_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9._-]+")


def default_download_folder() -> Path:
    return Path.home() / "Downloads"


def settings_path() -> Path:
    appdata = os.getenv("APPDATA")
    if appdata:
        return Path(appdata) / _APP_DIR / _SETTINGS_FILE
    return Path.home() / ".config" / "avocadoss-downloader" / _SETTINGS_FILE


def load_preferences(path: Path | None = None) -> dict[str, str]:
    target = path or settings_path()
    default = {"download_folder": str(default_download_folder())}
    try:
        if not target.is_file() or target.stat().st_size > 64 * 1024:
            return default
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return default
    if not isinstance(raw, dict):
        return default
    folder = raw.get("download_folder")
    if not isinstance(folder, str) or not folder.strip() or "\x00" in folder or len(folder) > 1000:
        return default
    return {"download_folder": folder.strip()}


def save_preferences(download_folder: str, path: Path | None = None) -> None:
    folder = str(download_folder or "").strip()
    if not folder or "\x00" in folder or len(folder) > 1000:
        return
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    payload = json.dumps({"download_folder": folder}, ensure_ascii=False, indent=2)
    temp.write_text(payload + "\n", encoding="utf-8")
    os.replace(temp, target)


def primary_asset_indices(assets: list[Asset]) -> list[int]:
    primary = [index for index, asset in enumerate(assets) if asset.kind in {"video", "image", "archive"}]
    return primary or list(range(len(assets)))


def collapse_redundant_thumbnails(assets: list[Asset]) -> list[Asset]:
    """Keep all real media but expose only the best thumbnail variant.

    Platforms commonly return several cover/thumbnail sizes for the same frame.
    Showing every size as a separate download choice adds clutter, so the desktop
    client keeps the highest-resolution thumbnail (filesize as a tie-breaker).
    """
    thumbnail_indices = [index for index, asset in enumerate(assets) if asset.kind == "thumbnail"]
    if len(thumbnail_indices) <= 1:
        return list(assets)

    def score(index: int) -> tuple[int, int, int]:
        asset = assets[index]
        area = (asset.width or 0) * (asset.height or 0)
        filesize = asset.filesize or 0
        return (area, filesize, -index)

    best_index = max(thumbnail_indices, key=score)
    return [
        asset
        for index, asset in enumerate(assets)
        if asset.kind != "thumbnail" or index == best_index
    ]


def _component(value: str, limit: int = 48) -> str:
    cleaned = _SAFE_COMPONENT.sub("-", value.strip().lstrip("@")).strip("-._")
    return cleaned[:limit].strip("-._")


def source_identifier(url: str, platform: str = "") -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return ""
    platform = platform.lower()
    if platform == "youtube":
        if parsed.hostname and parsed.hostname.lower().endswith("youtu.be"):
            return _component(parsed.path.strip("/").split("/")[0])
        query = urllib.parse.parse_qs(parsed.query)
        if query.get("v"):
            return _component(str(query["v"][0]))
    parts = [urllib.parse.unquote(part) for part in parsed.path.split("/") if part]
    markers = {"p", "reel", "reels", "tv", "post", "video", "note", "explore"}
    for index, part in enumerate(parts[:-1]):
        if part.lower() in markers:
            candidate = _component(parts[index + 1])
            if candidate:
                return candidate
    for part in reversed(parts):
        candidate = _component(part)
        if candidate and not candidate.startswith("@"):
            return candidate
    return ""


def preferred_filename(analysis: dict[str, Any], asset: Asset, index: int) -> str:
    platform = _component(str(analysis.get("platform") or "media"), 24).lower() or "media"
    author = _component(str(analysis.get("author") or ""), 32)
    source_url = str(analysis.get("source_url") or analysis.get("webpage_url") or "")
    source = source_identifier(source_url, platform)
    kind = {"thumbnail": "cover"}.get(asset.kind, _component(asset.kind or "media", 16).lower() or "media")
    parts = [platform]
    if author:
        parts.append(author)
    if source:
        parts.append(source)
    parts.extend([kind, f"{index + 1:02d}"])
    ext = _component(asset.ext.lower().lstrip("."), 8) or "bin"
    return sanitize_filename("-".join(parts) + "." + ext)


def _looks_generic(path: Path) -> bool:
    stem = path.stem.lower().strip()
    compact = re.sub(r"[^a-z0-9-]+", "", stem)
    return compact in _GENERIC_STEMS or any(
        compact.startswith(prefix)
        for prefix in ("download-", "download_", "output-", "output_", "avocadoss-download-")
    )


def improve_download_name(path: Path, analysis: dict[str, Any], asset: Asset, index: int) -> Path:
    if not path.is_file() or not _looks_generic(path):
        return path
    desired = unique_path(path.parent, preferred_filename(analysis, asset, index))
    if desired == path:
        return path
    os.replace(path, desired)
    return desired
