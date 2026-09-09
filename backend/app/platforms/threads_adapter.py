from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from ..models import AnalyzeResponse, MediaAsset

THREADS_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
_MEDIA_KEYS = {"video_versions", "video_dash_manifest", "image_versions2", "carousel_media"}
_URL_RE = re.compile(
    r"https?://(?:www\.)?threads\.(?:net|com)/(?:@(?P<user>[^/?#]+)/post/(?P<post>[\w-]+)|t/(?P<t>[\w-]+)|share/(?P<share>[\w-]+))",
    re.IGNORECASE,
)


def _collect_posts(obj: Any, out: list[dict[str, Any]]) -> None:
    if isinstance(obj, dict):
        if obj.get("code") and (set(obj) & _MEDIA_KEYS):
            out.append(obj)
        for value in obj.values():
            _collect_posts(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _collect_posts(value, out)


def _extract_posts(html: str) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    for block in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            payload = json.loads(block)
        except Exception:
            continue
        _collect_posts(payload, posts)
    # Preserve order, de-dupe repeated serialized copies by shortcode.
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for post in posts:
        code = str(post.get("code") or "")
        if not code or code in seen:
            continue
        seen.add(code)
        result.append(post)
    return result


def _canonical_target(url: str, html: str) -> str | None:
    match = _URL_RE.search(url)
    if match and (match.group("post") or match.group("t")):
        return match.group("post") or match.group("t")
    # Share links reveal the canonical post shortcode in og:url/canonical markup.
    for pattern in (
        r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\'][^"\']*/post/([\w-]+)',
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'][^"\']*/post/([\w-]+)',
        r'/post/([\w-]+)',
    ):
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1)
    return None


def _unique_by_path(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for url in urls:
        key = urlsplit(url).path
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


def _images(media: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = (((media.get("image_versions2") or {}).get("candidates")) or [])
    valid = [x for x in candidates if isinstance(x, dict) and x.get("url")]
    valid.sort(key=lambda x: (x.get("width") or 0) * (x.get("height") or 0), reverse=True)
    return valid


def _videos(media: dict[str, Any]) -> list[str]:
    urls = [x.get("url") for x in (media.get("video_versions") or []) if isinstance(x, dict) and x.get("url")]
    return _unique_by_path(urls)


def _media_units(post: dict[str, Any]) -> list[dict[str, Any]]:
    carousel = post.get("carousel_media")
    if isinstance(carousel, list) and carousel:
        return [x for x in carousel if isinstance(x, dict)]
    return [post]


def _extract_target(url: str, html: str) -> tuple[dict[str, Any], str]:
    target = _canonical_target(url, html)
    posts = _extract_posts(html)
    if target:
        post = next((p for p in posts if p.get("code") == target), None)
        if post is None:
            raise HTTPException(
                status_code=422,
                detail="The target Threads post was not found in the public crawler payload. It may be private, deleted, login-gated, or Threads changed its layout.",
            )
        return post, target
    raise HTTPException(status_code=422, detail="Could not determine the target Threads post from this link")


def _fetch(url: str) -> tuple[str, dict[str, Any], str]:
    headers = {
        "User-Agent": THREADS_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        with httpx.Client(follow_redirects=True, timeout=30, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=422, detail=f"Could not fetch public Threads post: {exc}") from exc
    post, code = _extract_target(str(response.url), response.text)
    return str(response.url), post, code


def _flatten_assets(post: dict[str, Any]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for unit_index, unit in enumerate(_media_units(post)):
        video_urls = _videos(unit)
        if video_urls:
            # Each media unit represents one clip. Variants usually point to the same path;
            # keep the first unique progressive rendition for the simple download UI.
            flat.append({"kind": "video", "url": video_urls[0], "unit": unit_index})

        # image_versions2 is a cover/thumbnail for video units, but it is the actual
        # downloadable image for image-only units. Preserve that distinction in the UI.
        image_kind = "thumbnail" if video_urls else "image"
        for image_index, image in enumerate(_images(unit)[:4]):
            flat.append({
                "kind": image_kind,
                "image": image,
                "url": image["url"],
                "unit": unit_index,
                "image_index": image_index,
            })
    return flat


def analyze(url: str) -> AnalyzeResponse:
    final_url, post, code = _fetch(url)
    flat = _flatten_assets(post)
    if not flat:
        raise HTTPException(status_code=422, detail="No downloadable public media was found in this Threads post")

    assets: list[MediaAsset] = []
    preview = None
    video_no = 0
    thumbnail_no = 0
    image_no = 0
    for idx, item in enumerate(flat):
        kind = item["kind"]
        if kind == "video":
            video_no += 1
            assets.append(MediaAsset(id=f"asset:{idx}", kind="video", label=f"Video {video_no}", ext="mp4"))
            continue

        image = item["image"]
        w, h = image.get("width"), image.get("height")
        dims = f" · {w}×{h}" if w and h else ""
        if kind == "image":
            image_no += 1
            label = f"Image {image_no}{dims}"
        else:
            thumbnail_no += 1
            label = f"Thumbnail {thumbnail_no}{dims}"
        assets.append(MediaAsset(
            id=f"asset:{idx}",
            kind=kind,
            label=label,
            width=w,
            height=h,
            ext="jpg",
            preview_url=item["url"],
        ))
        preview = preview or item["url"]

    user = post.get("user") or {}
    caption_obj = post.get("caption") or {}
    caption = caption_obj.get("text") if isinstance(caption_obj, dict) else None
    author = user.get("username") if isinstance(user, dict) else None
    return AnalyzeResponse(
        platform="threads",
        title=(caption or f"Threads post {code}")[:300],
        author=f"@{author}" if author else None,
        webpage_url=final_url,
        preview_url=preview,
        assets=assets,
    )


def resolve_asset(url: str, asset_id: str) -> tuple[str, str]:
    match = re.fullmatch(r"asset:(\d+)", asset_id)
    if not match:
        raise HTTPException(status_code=400, detail="Invalid Threads asset id")
    _, post, _ = _fetch(url)
    flat = _flatten_assets(post)
    index = int(match.group(1))
    if index >= len(flat):
        raise HTTPException(status_code=404, detail="Threads media is no longer available")
    item = flat[index]
    return item["url"], "mp4" if item["kind"] == "video" else "jpg"
