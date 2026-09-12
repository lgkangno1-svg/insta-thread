from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from fastapi import HTTPException

from ..models import AnalyzeResponse, MediaAsset
from .cookie_support import httpx_guest_cookies

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)
_NOTE_ID_RE = re.compile(r"/(?:explore|discovery/item)/([0-9a-fA-F]{24})(?:[/?#]|$)")
_ALLOWED_PAGE_HOSTS = {
    "xiaohongshu.com",
    "www.xiaohongshu.com",
    "m.xiaohongshu.com",
    "rednote.com",
    "www.rednote.com",
    "m.rednote.com",
    "xhslink.com",
    "www.xhslink.com",
    "xhslink.cn",
    "www.xhslink.cn",
}


def _headers() -> dict[str, str]:
    return {
        "User-Agent": _USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://www.xiaohongshu.com/",
        "Cache-Control": "no-cache",
    }


def _assert_page_url(url: str) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or host not in _ALLOWED_PAGE_HOSTS:
        raise HTTPException(status_code=400, detail="Unsupported Xiaohongshu URL")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Credentials in URLs are not allowed")


def _extract_note_id(url: str) -> str | None:
    match = _NOTE_ID_RE.search(url)
    return match.group(1).lower() if match else None


def _login_redirect(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.path != "/login":
        return None
    raw = parse_qs(parsed.query).get("redirectPath", [""])[0]
    if not raw:
        return None
    candidate = unquote(raw)
    try:
        _assert_page_url(candidate)
    except HTTPException:
        return None
    return candidate


def _candidate_note_pages(url: str, note_id: str) -> list[str]:
    """Return official page variants while preserving raw share query parameters."""
    parsed = urlparse(url)
    suffix = f"?{parsed.query}" if parsed.query else ""
    candidates = [
        url,
        f"https://www.xiaohongshu.com/explore/{note_id}{suffix}",
        f"https://www.xiaohongshu.com/discovery/item/{note_id}{suffix}",
    ]
    out: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out


def _extract_balanced_object(text: str, start: int) -> str | None:
    depth = 0
    quote: str | None = None
    escaped = False
    for idx in range(start, len(text)):
        char = text[idx]
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _normalize_js_literals(raw: str) -> str:
    out: list[str] = []
    idx = 0
    quote: str | None = None
    escaped = False
    literals = ("undefined", "NaN", "Infinity")
    while idx < len(raw):
        char = raw[idx]
        if quote is not None:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            idx += 1
            continue
        if char in {'"', "'"}:
            quote = char
            out.append(char)
            idx += 1
            continue
        replaced = False
        for literal in literals:
            if raw.startswith(literal, idx):
                before = raw[idx - 1] if idx else ""
                end = idx + len(literal)
                after = raw[end] if end < len(raw) else ""
                if (not before or not (before.isalnum() or before in "_$")) and (
                    not after or not (after.isalnum() or after in "_$")
                ):
                    out.append("null")
                    idx = end
                    replaced = True
                    break
        if replaced:
            continue
        out.append(char)
        idx += 1
    return "".join(out)


def _extract_initial_state(html: str) -> dict[str, Any]:
    marker = "__INITIAL_STATE__"
    pos = html.find(marker)
    while pos >= 0:
        eq = html.find("=", pos + len(marker))
        if eq < 0:
            break
        start = html.find("{", eq + 1)
        if start < 0:
            break
        raw = _extract_balanced_object(html, start)
        if raw:
            try:
                value = json.loads(_normalize_js_literals(raw))
                if isinstance(value, dict):
                    return value
            except json.JSONDecodeError:
                pass
        pos = html.find(marker, pos + len(marker))
    raise HTTPException(status_code=422, detail="Could not read the public Xiaohongshu note data")


def _note_from_state(state: dict[str, Any], note_id: str) -> dict[str, Any]:
    note_store = state.get("note") or {}
    detail_map = note_store.get("noteDetailMap") or (note_store.get("data") or {}).get("noteDetailMap") or {}
    entry = detail_map.get(note_id) if isinstance(detail_map, dict) else None
    if not isinstance(entry, dict):
        for candidate in detail_map.values() if isinstance(detail_map, dict) else []:
            if not isinstance(candidate, dict):
                continue
            nested = candidate.get("note") if isinstance(candidate.get("note"), dict) else candidate
            embedded = nested.get("noteId") or nested.get("note_id") or nested.get("id")
            if str(embedded).lower() == note_id:
                entry = candidate
                break
    if not isinstance(entry, dict):
        raise HTTPException(status_code=422, detail="The public Xiaohongshu page did not contain the requested note")
    note = entry.get("note") if isinstance(entry.get("note"), dict) else entry
    if not isinstance(note, dict):
        raise HTTPException(status_code=422, detail="The Xiaohongshu note data was incomplete")
    return note


def _https_xhs_cdn(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    if url.startswith("http://"):
        url = "https://" + url[7:]
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (host == "xhscdn.com" or host.endswith(".xhscdn.com")):
        return None
    return url


def _best_image_url(image: dict[str, Any]) -> str | None:
    for info in image.get("infoList") or []:
        if isinstance(info, dict) and info.get("imageScene") == "WB_DFT":
            found = _https_xhs_cdn(info.get("url"))
            if found:
                return found
    for key in ("urlDefault", "urlPre", "url"):
        found = _https_xhs_cdn(image.get(key))
        if found:
            return found
    for info in image.get("infoList") or []:
        if isinstance(info, dict):
            found = _https_xhs_cdn(info.get("url"))
            if found:
                return found
    return None


def _image_ext(url: str) -> str:
    lower = url.lower()
    if "webp" in lower:
        return "webp"
    match = re.search(r"\.(jpe?g|png|webp|gif)(?:[?#]|$)", lower)
    return match.group(1).replace("jpeg", "jpg") if match else "jpg"


def _image_assets(note: dict[str, Any]) -> list[MediaAsset]:
    assets: list[MediaAsset] = []
    seen: set[str] = set()
    for image in note.get("imageList") or []:
        if not isinstance(image, dict):
            continue
        source = _best_image_url(image)
        if not source or source in seen:
            continue
        seen.add(source)
        idx = len(assets)
        width = image.get("width") if isinstance(image.get("width"), int) else None
        height = image.get("height") if isinstance(image.get("height"), int) else None
        dims = f" · {width}×{height}" if width and height else ""
        assets.append(MediaAsset(
            id=f"image:{idx}", kind="image", label=f"Image {idx + 1}{dims}",
            width=width, height=height, ext=_image_ext(source), preview_url=source,
        ))
    return assets


def _video_candidate_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    url = _https_xhs_cdn(value)
    if not url:
        return None
    lower = url.lower()
    if "m3u8" in lower or "/hls" in lower or re.search(r"\.(?:ts|m2ts)(?:[?#]|$)", lower):
        return None
    if "sns-video" not in lower and ".mp4" not in lower:
        return None
    return url


def _collect_video_candidates(note: dict[str, Any]) -> list[tuple[str, int, int, int, int]]:
    video = note.get("video") if isinstance(note.get("video"), dict) else {}
    collected: dict[str, tuple[str, int, int, int, int]] = {}

    def add(url: Any, width: Any = 0, height: Any = 0, bitrate: Any = 0, size: Any = 0) -> None:
        source = _video_candidate_url(url)
        if not source:
            return
        candidate = (
            source,
            int(width or 0) if str(width or "").isdigit() else 0,
            int(height or 0) if str(height or "").isdigit() else 0,
            int(bitrate or 0) if str(bitrate or "").isdigit() else 0,
            int(size or 0) if str(size or "").isdigit() else 0,
        )
        previous = collected.get(source)
        if previous is None or candidate[1:] > previous[1:]:
            collected[source] = candidate

    stream = ((video.get("media") or {}).get("stream") if isinstance(video.get("media"), dict) else {}) or {}
    if isinstance(stream, dict):
        for codec in ("h264", "h265", "av1", "h266"):
            for item in stream.get(codec) or []:
                if not isinstance(item, dict):
                    continue
                for key in ("masterUrl", "url"):
                    add(item.get(key), item.get("width"), item.get("height"), item.get("avgBitrate") or item.get("bitrate"), item.get("size"))
                for backup in item.get("backupUrls") or []:
                    add(backup, item.get("width"), item.get("height"), item.get("avgBitrate") or item.get("bitrate"), item.get("size"))

    consumer = video.get("consumer") if isinstance(video.get("consumer"), dict) else {}
    origin_key = consumer.get("originVideoKey") or video.get("originVideoKey")
    if isinstance(origin_key, str) and origin_key:
        add(origin_key if origin_key.startswith("http") else f"https://sns-video-bd.xhscdn.com/{origin_key.lstrip('/')}")

    for key in ("url", "downloadUrl", "masterUrl"):
        add(video.get(key))

    def walk(obj: Any, depth: int = 0) -> None:
        if depth > 8:
            return
        if isinstance(obj, dict):
            width = obj.get("width") or 0
            height = obj.get("height") or 0
            bitrate = obj.get("avgBitrate") or obj.get("videoBitrate") or obj.get("bitrate") or 0
            size = obj.get("size") or obj.get("fileSize") or 0
            for key, child in obj.items():
                if key in {"masterUrl", "url", "downloadUrl"}:
                    add(child, width, height, bitrate, size)
                elif key in {"backupUrls", "backup_urls"} and isinstance(child, list):
                    for value in child:
                        add(value, width, height, bitrate, size)
                else:
                    walk(child, depth + 1)
        elif isinstance(obj, list):
            for child in obj:
                walk(child, depth + 1)

    walk(video)
    return sorted(collected.values(), key=lambda x: (x[1] * x[2], x[3], x[4]), reverse=True)


def _fetch_note(url: str) -> tuple[dict[str, Any], str, str]:
    _assert_page_url(url)
    note_id = _extract_note_id(url)
    if not note_id:
        raise HTTPException(status_code=422, detail="Could not determine the Xiaohongshu note ID")

    last_error: Exception | None = None
    try:
        with httpx.Client(timeout=35, follow_redirects=True, headers=_headers(), cookies=httpx_guest_cookies()) as client:
            for candidate in _candidate_note_pages(url, note_id):
                try:
                    response = client.get(candidate)
                    response.raise_for_status()
                    final_url = str(response.url)
                    redirect = _login_redirect(final_url)
                    if redirect:
                        response = client.get(redirect)
                        response.raise_for_status()
                        final_url = str(response.url)
                    resolved_id = _extract_note_id(final_url) or _extract_note_id(redirect or "") or note_id
                    state = _extract_initial_state(response.text)
                    note = _note_from_state(state, resolved_id)
                    return note, resolved_id, final_url
                except (HTTPException, httpx.HTTPError) as exc:
                    last_error = exc
                    continue
    except httpx.HTTPError as exc:
        last_error = exc

    detail = "Could not load the public Xiaohongshu note from its share page"
    if isinstance(last_error, HTTPException):
        detail = str(last_error.detail)
    elif last_error:
        detail = f"{detail}: {last_error}"
    raise HTTPException(status_code=422, detail=detail)


def analyze(url: str) -> AnalyzeResponse:
    note, note_id, webpage_url = _fetch_note(url)
    images = _image_assets(note)
    videos = _collect_video_candidates(note)
    assets: list[MediaAsset] = []
    if videos:
        best = videos[0]
        width = best[1] or None
        height = best[2] or None
        dims = f" · {width}×{height}" if width and height else ""
        assets.append(MediaAsset(
            id="video:best", kind="video", label=f"Best available{dims}",
            width=width, height=height, ext="mp4",
            preview_url=images[0].preview_url if images else None,
        ))
    if len(images) > 1:
        assets.append(MediaAsset(
            id="images:zip", kind="archive", label=f"Download all {len(images)} images (.ZIP)",
            ext="zip", preview_url=images[0].preview_url,
        ))
    assets.extend(images)
    if not assets:
        note_type = str(note.get("type") or "unknown")
        raise HTTPException(status_code=422, detail=f"This Xiaohongshu note has no downloadable public media (type: {note_type})")
    user = note.get("user") if isinstance(note.get("user"), dict) else {}
    return AnalyzeResponse(
        platform="xiaohongshu",
        title=note.get("title") or note.get("desc") or f"Xiaohongshu {note_id}",
        author=user.get("nickname") or user.get("nickName") or user.get("name"),
        webpage_url=webpage_url,
        preview_url=images[0].preview_url if images else None,
        assets=assets,
    )


def resolve_all_images(url: str) -> list[tuple[str, str]]:
    note, _note_id, _webpage_url = _fetch_note(url)
    assets = _image_assets(note)
    if len(assets) < 2:
        raise HTTPException(status_code=404, detail="This Xiaohongshu note does not contain multiple public images")
    return [(asset.preview_url, asset.ext or "jpg") for asset in assets if asset.preview_url]


def resolve_asset(url: str, asset_id: str) -> tuple[str, str]:
    note, _note_id, _webpage_url = _fetch_note(url)
    if asset_id == "video:best":
        videos = _collect_video_candidates(note)
        if not videos:
            raise HTTPException(status_code=404, detail="This Xiaohongshu note does not contain a public video")
        return videos[0][0], "mp4"
    match = re.fullmatch(r"image:(\d+)", asset_id)
    if match:
        assets = _image_assets(note)
        idx = int(match.group(1))
        if idx >= len(assets) or not assets[idx].preview_url:
            raise HTTPException(status_code=404, detail="This Xiaohongshu image is no longer available")
        return assets[idx].preview_url, assets[idx].ext or "jpg"
    raise HTTPException(status_code=400, detail="Invalid Xiaohongshu asset selection")
