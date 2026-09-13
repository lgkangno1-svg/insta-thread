from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from ..models import AnalyzeResponse, MediaAsset

_IPHONE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1"
)
_AWEME_RE = re.compile(r"/(?:video|note|share/video)/(\d{15,22})(?:[/?#]|$)")
_ROUTER_MARKER = "_ROUTER_DATA"


def _aweme_id(url: str) -> str:
    match = _AWEME_RE.search(url)
    if not match:
        raise HTTPException(status_code=400, detail="Could not determine the Douyin media id")
    return match.group(1)


def _share_page_url(aweme_id: str) -> str:
    return f"https://www.iesdouyin.com/share/video/{aweme_id}/?from_ssr=1"


def _scan_balanced(text: str, start: int, opening: str = "{", closing: str = "}") -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _scan_json_string(text: str, start: int) -> str | None:
    escaped = False
    for idx in range(start + 1, len(text)):
        char = text[idx]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            return text[start : idx + 1]
    return None


def _extract_router_data(page: str) -> dict[str, Any]:
    marker = page.find(_ROUTER_MARKER)
    if marker < 0:
        raise HTTPException(status_code=422, detail="Douyin public share data was not present on the page")
    equals = page.find("=", marker)
    if equals < 0:
        raise HTTPException(status_code=422, detail="Douyin public share data was malformed")
    cursor = equals + 1
    while cursor < len(page) and page[cursor].isspace():
        cursor += 1
    if cursor >= len(page):
        raise HTTPException(status_code=422, detail="Douyin public share data was empty")

    try:
        if page[cursor] == "{":
            raw = _scan_balanced(page, cursor)
            if not raw:
                raise ValueError("unterminated object")
            data = json.loads(raw)
        elif page[cursor] == '"':
            literal = _scan_json_string(page, cursor)
            if not literal:
                raise ValueError("unterminated string")
            inner = json.loads(literal)
            data = json.loads(inner)
        else:
            raise ValueError("unsupported router data literal")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Could not parse Douyin public share data") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Douyin public share data was not an object")
    return data


def _find_item(value: Any, aweme_id: str) -> dict[str, Any] | None:
    if isinstance(value, dict):
        candidate_id = str(value.get("aweme_id") or value.get("awemeId") or "")
        if candidate_id == aweme_id and (isinstance(value.get("video"), dict) or isinstance(value.get("images"), list)):
            return value
        for child in value.values():
            found = _find_item(child, aweme_id)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_item(child, aweme_id)
            if found:
                return found
    return None


def _https_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if value.startswith("http://"):
        value = "https://" + value[len("http://") :]
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    return value


def _urls(node: Any) -> list[str]:
    if not isinstance(node, dict):
        return []
    raw = node.get("url_list") or node.get("urlList") or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for value in raw:
        url = _https_url(value)
        if url and url not in out:
            out.append(url)
    return out


def _video_urls(item: dict[str, Any]) -> list[str]:
    video = item.get("video") if isinstance(item.get("video"), dict) else {}
    for key in ("play_addr", "playAddr", "download_addr", "downloadAddr"):
        values = _urls(video.get(key))
        if values:
            return values
    return []


def _cover_urls(item: dict[str, Any]) -> list[str]:
    video = item.get("video") if isinstance(item.get("video"), dict) else {}
    out: list[str] = []
    for key in ("origin_cover", "originCover", "cover", "dynamic_cover", "dynamicCover"):
        for url in _urls(video.get(key)):
            if url not in out:
                out.append(url)
    return out


def _extension(url: str, default: str) -> str:
    suffix = PurePosixPath(urlparse(url).path).suffix.lower().lstrip(".")
    return suffix if suffix in {"jpg", "jpeg", "png", "webp", "mp4"} else default


def _fetch_item(url: str) -> tuple[dict[str, Any], str]:
    aweme_id = _aweme_id(url)
    headers = {
        "User-Agent": _IPHONE_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "Referer": "https://www.douyin.com/",
        "Cache-Control": "no-cache",
    }
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
            response = client.get(_share_page_url(aweme_id))
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=422, detail=f"Could not read the public Douyin share page: {exc}") from exc

    data = _extract_router_data(response.text)
    item = _find_item(data, aweme_id)
    if not item:
        raise HTTPException(status_code=422, detail="The public Douyin page did not expose downloadable media")
    return item, aweme_id


def analyze(url: str) -> AnalyzeResponse:
    item, aweme_id = _fetch_item(url)
    videos = _video_urls(item)
    covers = _cover_urls(item)
    assets: list[MediaAsset] = []
    if videos:
        video = item.get("video") if isinstance(item.get("video"), dict) else {}
        assets.append(MediaAsset(
            id="video:best",
            kind="video",
            label="Public video",
            width=video.get("width") if isinstance(video.get("width"), int) else None,
            height=video.get("height") if isinstance(video.get("height"), int) else None,
            ext="mp4",
            preview_url=covers[0] if covers else None,
        ))
    for idx, cover in enumerate(covers[:4]):
        assets.append(MediaAsset(
            id=f"thumbnail:{idx}",
            kind="thumbnail",
            label=f"Cover {idx + 1}",
            ext=_extension(cover, "jpg"),
            preview_url=cover,
        ))
    if not assets:
        raise HTTPException(status_code=422, detail="No downloadable public media was found on this Douyin post")

    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    return AnalyzeResponse(
        platform="douyin",
        title=str(item.get("desc") or "Douyin video")[:300],
        author=str(author.get("nickname") or "") or None,
        webpage_url=f"https://www.douyin.com/video/{aweme_id}",
        preview_url=covers[0] if covers else None,
        assets=assets,
    )


def resolve_asset(url: str, asset_id: str) -> tuple[str, str]:
    item, _aweme_id_value = _fetch_item(url)
    if asset_id == "video:best":
        videos = _video_urls(item)
        if not videos:
            raise HTTPException(status_code=404, detail="Douyin video source is no longer available")
        return videos[0], "mp4"
    match = re.fullmatch(r"thumbnail:(\d+)", asset_id)
    if match:
        covers = _cover_urls(item)
        index = int(match.group(1))
        if index >= len(covers):
            raise HTTPException(status_code=404, detail="Douyin cover is no longer available")
        return covers[index], _extension(covers[index], "jpg")
    raise HTTPException(status_code=400, detail="Invalid Douyin asset selection")
