from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse, urlunparse

from fastapi import HTTPException


@dataclass(frozen=True)
class PlatformRoute:
    platform: str
    canonical_host: str


_HOSTS: dict[str, PlatformRoute] = {
    "youtube.com": PlatformRoute("youtube", "youtube.com"),
    "www.youtube.com": PlatformRoute("youtube", "youtube.com"),
    "m.youtube.com": PlatformRoute("youtube", "youtube.com"),
    "music.youtube.com": PlatformRoute("youtube", "youtube.com"),
    "youtu.be": PlatformRoute("youtube", "youtube.com"),
    "instagram.com": PlatformRoute("instagram", "instagram.com"),
    "www.instagram.com": PlatformRoute("instagram", "instagram.com"),
    "m.instagram.com": PlatformRoute("instagram", "instagram.com"),
    "instagr.am": PlatformRoute("instagram", "instagram.com"),
    "www.instagr.am": PlatformRoute("instagram", "instagram.com"),
    "xiaohongshu.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.xiaohongshu.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "m.xiaohongshu.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "rednote.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.rednote.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "m.rednote.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "xhslink.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.xhslink.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "xhslink.cn": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.xhslink.cn": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "threads.net": PlatformRoute("threads", "threads.com"),
    "www.threads.net": PlatformRoute("threads", "threads.com"),
    "threads.com": PlatformRoute("threads", "threads.com"),
    "www.threads.com": PlatformRoute("threads", "threads.com"),
    "douyin.com": PlatformRoute("douyin", "douyin.com"),
    "www.douyin.com": PlatformRoute("douyin", "douyin.com"),
    "m.douyin.com": PlatformRoute("douyin", "douyin.com"),
    "v.douyin.com": PlatformRoute("douyin", "douyin.com"),
    "iesdouyin.com": PlatformRoute("douyin", "douyin.com"),
    "www.iesdouyin.com": PlatformRoute("douyin", "douyin.com"),
}

_HTTP_URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
_BARE_HOST_RE = re.compile(
    r"(?<![\w@])(?:www\.|m\.|music\.|v\.)?(?:youtube\.com|instagram\.com|instagr\.am|"
    r"xiaohongshu\.com|rednote\.com|xhslink\.com|xhslink\.cn|threads\.com|threads\.net|"
    r"douyin\.com|iesdouyin\.com)/[^\s<>\"'`]+",
    re.IGNORECASE,
)
_TRAILING_SHARE_PUNCTUATION = ".,;:!?，。；：！？、)]}>】》」』）”’"
_ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"
_XHS_NOTE_ID_RE = re.compile(r"^[0-9a-fA-F]{24}$")
_XHS_PROFILE_NOTE_RE = re.compile(r"^/user/profile/[^/]+/([0-9a-fA-F]{24})(?:/)?$")
_DOUYIN_AWEME_ID_RE = re.compile(r"^\d{15,22}$")
_DOUYIN_SHARE_VIDEO_RE = re.compile(r"^/share/video/(\d{15,22})(?:/)?$")
_DOUYIN_NOTE_RE = re.compile(r"^/note/(\d{15,22})(?:/)?$")


def _clean_candidate(candidate: str) -> str:
    candidate = candidate.strip().lstrip("([<{【《「『“‘")
    return candidate.rstrip(_TRAILING_SHARE_PUNCTUATION)


def _route_for_url(candidate: str) -> tuple[str, PlatformRoute] | None:
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    route = _HOSTS.get(host)
    if not route:
        return None
    return candidate, route


def _canonicalize(candidate: str, route: PlatformRoute) -> str:
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower().rstrip(".")
    if route.platform == "xiaohongshu":
        if host == "rednote.com" or host.endswith(".rednote.com"):
            parsed = parsed._replace(netloc="www.xiaohongshu.com")
            host = "www.xiaohongshu.com"
        if host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com"):
            profile_match = _XHS_PROFILE_NOTE_RE.match(parsed.path)
            if profile_match:
                note_id = profile_match.group(1).lower()
                parsed = parsed._replace(netloc="www.xiaohongshu.com", path=f"/explore/{note_id}")
        return urlunparse(parsed)

    if route.platform == "douyin":
        # Legacy web-share pages and desktop modal URLs identify the same aweme by
        # numeric id. Converting them to the canonical /video/ form gives yt-dlp a
        # stable input and avoids depending on page-shell JavaScript redirects.
        share_match = _DOUYIN_SHARE_VIDEO_RE.match(parsed.path)
        note_match = _DOUYIN_NOTE_RE.match(parsed.path)
        modal_id = parse_qs(parsed.query).get("modal_id", [""])[0]
        aweme_id = ""
        if share_match:
            aweme_id = share_match.group(1)
        elif note_match:
            aweme_id = note_match.group(1)
        elif parsed.path.rstrip("/") in {"/jingxuan", "/discover"} and _DOUYIN_AWEME_ID_RE.fullmatch(modal_id):
            aweme_id = modal_id
        if aweme_id:
            return f"https://www.douyin.com/video/{aweme_id}"
    return candidate


def extract_supported_url(value: str) -> str:
    """Extract a supported public-media URL from a URL, share text, or stable media id."""
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="A URL is required")
    text = html.unescape(value).strip()
    for char in _ZERO_WIDTH:
        text = text.replace(char, "")
    if not text:
        raise HTTPException(status_code=400, detail="A URL is required")

    for match in _HTTP_URL_RE.finditer(text):
        candidate = _clean_candidate(match.group(0))
        routed = _route_for_url(candidate)
        if routed:
            return _canonicalize(routed[0], routed[1])

    for match in _BARE_HOST_RE.finditer(text):
        candidate = _clean_candidate(match.group(0))
        routed = _route_for_url("https://" + candidate)
        if routed:
            return _canonicalize(routed[0], routed[1])

    if _XHS_NOTE_ID_RE.fullmatch(text):
        return f"https://www.xiaohongshu.com/explore/{text.lower()}"
    if _DOUYIN_AWEME_ID_RE.fullmatch(text):
        return f"https://www.douyin.com/video/{text}"

    raise HTTPException(status_code=400, detail="No supported media URL was found in the pasted text")


def detect_platform(value: str) -> PlatformRoute:
    candidate = extract_supported_url(value)
    routed = _route_for_url(candidate)
    if not routed:
        raise HTTPException(status_code=400, detail="Unsupported platform or domain")
    return routed[1]
