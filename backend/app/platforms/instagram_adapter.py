from __future__ import annotations

import re
from typing import Any

import httpx
from fastapi import HTTPException

from ..models import AnalyzeResponse, MediaAsset

_GRAPHQL_URL = "https://www.instagram.com/graphql/query"
_HOME_URL = "https://www.instagram.com/"
_DOC_ID = "27128499623469141"
_APP_ID = "936619743392459"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)
_SHORTCODE_RE = re.compile(r"/(?:reel|reels|p|tv)/(?P<code>[A-Za-z0-9_-]+)", re.IGNORECASE)


def _shortcode(url: str) -> str:
    match = _SHORTCODE_RE.search(url)
    if not match:
        raise HTTPException(status_code=400, detail="Unsupported Instagram post URL")
    return match.group("code")


def _canonical_url(url: str, shortcode: str) -> str:
    lowered = url.lower()
    if "/p/" in lowered:
        return f"https://www.instagram.com/p/{shortcode}/"
    if "/tv/" in lowered:
        return f"https://www.instagram.com/tv/{shortcode}/"
    return f"https://www.instagram.com/reel/{shortcode}/"


def _query(shortcode: str) -> dict[str, Any]:
    headers = {
        "User-Agent": _UA,
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        with httpx.Client(follow_redirects=True, timeout=35, headers=headers) as client:
            home = client.get(_HOME_URL)
            home.raise_for_status()
            csrf = client.cookies.get("csrftoken") or ""
            response = client.post(
                _GRAPHQL_URL,
                data={
                    "variables": (
                        '{"shortcode":"%s","__relay_internal__pv__PolarisAIGMMediaWebLabelEnabledrelayprovider":false}'
                        % shortcode
                    ),
                    "doc_id": _DOC_ID,
                    "server_timestamps": "true",
                },
                headers={
                    "Accept": "*/*",
                    "Origin": "https://www.instagram.com",
                    "Referer": f"https://www.instagram.com/p/{shortcode}/",
                    "X-CSRFToken": csrf,
                    "X-IG-App-ID": _APP_ID,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not fetch public Instagram media: {exc}") from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    web_info = (data or {}).get("xdt_api__v1__media__shortcode__web_info") if isinstance(data, dict) else None
    items = (web_info or {}).get("items") if isinstance(web_info, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise HTTPException(
            status_code=422,
            detail="Instagram did not expose this public post through its anonymous media API. It may be private, removed, login-gated, rate-limited, or temporarily unavailable.",
        )
    return items[0]


def _video_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [x for x in (item.get("video_versions") or []) if isinstance(x, dict) and x.get("url")]
    candidates.sort(
        key=lambda x: ((x.get("width") or 0) * (x.get("height") or 0), x.get("width") or 0),
        reverse=True,
    )
    return candidates


def _image_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        x
        for x in (((item.get("image_versions2") or {}).get("candidates")) or [])
        if isinstance(x, dict) and x.get("url")
    ]
    candidates.sort(
        key=lambda x: ((x.get("width") or 0) * (x.get("height") or 0), x.get("width") or 0),
        reverse=True,
    )
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_url = candidate["url"]
        if candidate_url in seen:
            continue
        seen.add(candidate_url)
        out.append(candidate)
    return out


def _media_items(item: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    carousel = [x for x in (item.get("carousel_media") or []) if isinstance(x, dict)]
    return (carousel, True) if carousel else ([item], False)


def _caption(item: dict[str, Any]) -> str | None:
    caption = item.get("caption")
    if isinstance(caption, dict):
        text = caption.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def analyze(url: str) -> AnalyzeResponse:
    shortcode = _shortcode(url)
    item = _query(shortcode)
    media_items, is_carousel = _media_items(item)
    assets: list[MediaAsset] = []
    preview: str | None = None

    if is_carousel:
        for idx, media in enumerate(media_items):
            videos = _video_candidates(media)
            images = _image_candidates(media)
            best_image = images[0] if images else None
            if preview is None and best_image:
                preview = best_image["url"]

            if videos:
                best = videos[0]
                assets.append(
                    MediaAsset(
                        id=f"video:{idx}",
                        kind="video",
                        label=f"Video {idx + 1}",
                        width=best.get("width") if isinstance(best.get("width"), int) else None,
                        height=best.get("height") if isinstance(best.get("height"), int) else None,
                        ext="mp4",
                        preview_url=best_image["url"] if best_image else None,
                    )
                )
            elif best_image:
                assets.append(
                    MediaAsset(
                        id=f"image:{idx}",
                        kind="image",
                        label=f"Image {idx + 1}",
                        width=best_image.get("width") if isinstance(best_image.get("width"), int) else None,
                        height=best_image.get("height") if isinstance(best_image.get("height"), int) else None,
                        ext="jpg",
                        preview_url=best_image["url"],
                    )
                )
    else:
        videos = _video_candidates(item)
        images = _image_candidates(item)
        best_image = images[0] if images else None
        preview = best_image["url"] if best_image else None

        if videos:
            best = videos[0]
            assets.append(
                MediaAsset(
                    id="video:best",
                    kind="video",
                    label="Best available video",
                    width=best.get("width") if isinstance(best.get("width"), int) else None,
                    height=best.get("height") if isinstance(best.get("height"), int) else None,
                    ext="mp4",
                    preview_url=preview,
                )
            )
            for idx, image in enumerate(images[:4]):
                width, height = image.get("width"), image.get("height")
                dims = f"{width}×{height}" if width and height else "cover"
                assets.append(
                    MediaAsset(
                        id=f"thumbnail:{idx}",
                        kind="thumbnail",
                        label=f"Cover {dims}",
                        width=width if isinstance(width, int) else None,
                        height=height if isinstance(height, int) else None,
                        ext="jpg",
                        preview_url=image["url"],
                    )
                )
        elif best_image:
            assets.append(
                MediaAsset(
                    id="image:0",
                    kind="image",
                    label="Original image",
                    width=best_image.get("width") if isinstance(best_image.get("width"), int) else None,
                    height=best_image.get("height") if isinstance(best_image.get("height"), int) else None,
                    ext="jpg",
                    preview_url=best_image["url"],
                )
            )

    if not assets:
        raise HTTPException(status_code=422, detail="No downloadable public media was found in this Instagram post")

    user = item.get("user") or {}
    username = user.get("username") if isinstance(user, dict) else None
    title = _caption(item) or f"Instagram post {shortcode}"
    return AnalyzeResponse(
        platform="instagram",
        title=title[:300],
        author=f"@{username}" if username else None,
        webpage_url=_canonical_url(url, shortcode),
        preview_url=preview,
        assets=assets,
    )


def resolve_asset(url: str, asset_id: str) -> tuple[str, str]:
    shortcode = _shortcode(url)
    item = _query(shortcode)
    media_items, is_carousel = _media_items(item)

    if asset_id == "video:best":
        videos = _video_candidates(item)
        if not videos:
            raise HTTPException(status_code=404, detail="Instagram video is no longer available")
        return videos[0]["url"], "mp4"

    media_match = re.fullmatch(r"(video|image):(\d+)", asset_id)
    if media_match:
        kind = media_match.group(1)
        index = int(media_match.group(2))
        if index >= len(media_items):
            raise HTTPException(status_code=404, detail="Instagram media item is no longer available")
        media = media_items[index]
        if kind == "video":
            videos = _video_candidates(media)
            if not videos:
                raise HTTPException(status_code=404, detail="Instagram video is no longer available")
            return videos[0]["url"], "mp4"
        images = _image_candidates(media)
        if not images:
            raise HTTPException(status_code=404, detail="Instagram image is no longer available")
        return images[0]["url"], "jpg"

    match = re.fullmatch(r"thumbnail:(\d+)", asset_id)
    if not match or is_carousel:
        raise HTTPException(status_code=400, detail="Invalid Instagram asset id")
    images = _image_candidates(item)[:4]
    index = int(match.group(1))
    if index >= len(images):
        raise HTTPException(status_code=404, detail="Instagram cover image is no longer available")
    return images[index]["url"], "jpg"
