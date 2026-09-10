from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import HTTPException


@dataclass(frozen=True)
class PlatformRoute:
    platform: str
    canonical_host: str


_HOSTS: dict[str, PlatformRoute] = {
    # YouTube share/watch/shorts/live URLs
    "youtube.com": PlatformRoute("youtube", "youtube.com"),
    "www.youtube.com": PlatformRoute("youtube", "youtube.com"),
    "m.youtube.com": PlatformRoute("youtube", "youtube.com"),
    "music.youtube.com": PlatformRoute("youtube", "youtube.com"),
    "youtu.be": PlatformRoute("youtube", "youtube.com"),
    # Instagram web/mobile and legacy short host
    "instagram.com": PlatformRoute("instagram", "instagram.com"),
    "www.instagram.com": PlatformRoute("instagram", "instagram.com"),
    "m.instagram.com": PlatformRoute("instagram", "instagram.com"),
    "instagr.am": PlatformRoute("instagram", "instagram.com"),
    "www.instagr.am": PlatformRoute("instagram", "instagram.com"),
    # Xiaohongshu / RedNote long and short share hosts
    "xiaohongshu.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.xiaohongshu.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "m.xiaohongshu.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "xhslink.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.xhslink.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "xhslink.cn": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.xhslink.cn": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    # Threads old/new domains and share wrappers
    "threads.net": PlatformRoute("threads", "threads.com"),
    "www.threads.net": PlatformRoute("threads", "threads.com"),
    "threads.com": PlatformRoute("threads", "threads.com"),
    "www.threads.com": PlatformRoute("threads", "threads.com"),
    # Douyin long, short, mobile and legacy share domains
    "douyin.com": PlatformRoute("douyin", "douyin.com"),
    "www.douyin.com": PlatformRoute("douyin", "douyin.com"),
    "m.douyin.com": PlatformRoute("douyin", "douyin.com"),
    "v.douyin.com": PlatformRoute("douyin", "douyin.com"),
    "iesdouyin.com": PlatformRoute("douyin", "douyin.com"),
    "www.iesdouyin.com": PlatformRoute("douyin", "douyin.com"),
}

# Copy-link actions often place a URL inside a title/caption, e.g. Douyin or
# Xiaohongshu Chinese share text. Keep query strings intact (including xsec_token)
# but trim punctuation that belongs to the surrounding sentence.
_HTTP_URL_RE = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
_BARE_HOST_RE = re.compile(
    r"(?<![\w@])(?:www\.|m\.|music\.)?(?:youtube\.com|instagram\.com|instagr\.am|"
    r"xiaohongshu\.com|xhslink\.com|xhslink\.cn|threads\.com|threads\.net|"
    r"douyin\.com|iesdouyin\.com)/[^\s<>\"'`]+",
    re.IGNORECASE,
)
_TRAILING_SHARE_PUNCTUATION = ".,;:!?，。；：！？、)]}>】》」』）”’"
_ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"
_XHS_NOTE_ID_RE = re.compile(r"^[0-9a-fA-F]{24}$")


def _clean_candidate(candidate: str) -> str:
    candidate = candidate.strip().lstrip("([<{【《「『“‘")
    candidate = candidate.rstrip(_TRAILING_SHARE_PUNCTUATION)
    return candidate


def _route_for_url(candidate: str) -> tuple[str, PlatformRoute] | None:
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return None
    if parsed.username or parsed.password:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    route = _HOSTS.get(host)
    if not route:
        return None
    return candidate, route


def extract_supported_url(value: str) -> str:
    """Extract one supported public-media URL from a pasted URL or share message.

    This intentionally does not follow redirects. Platform adapters do that with
    their own allowlists, so short-link handling remains SSRF constrained.
    """
    if not isinstance(value, str):
        raise HTTPException(status_code=400, detail="A URL is required")
    text = html.unescape(value).strip()
    for char in _ZERO_WIDTH:
        text = text.replace(char, "")
    if not text:
        raise HTTPException(status_code=400, detail="A URL is required")

    # Prefer explicit http(s) URLs and only accept an exact supported host.
    for match in _HTTP_URL_RE.finditer(text):
        candidate = _clean_candidate(match.group(0))
        routed = _route_for_url(candidate)
        if routed:
            return routed[0]

    # Also accept links copied without a scheme.
    for match in _BARE_HOST_RE.finditer(text):
        candidate = _clean_candidate(match.group(0))
        routed = _route_for_url("https://" + candidate)
        if routed:
            return routed[0]

    # Xiaohongshu note IDs are 24 hex characters and some downloader/share tools
    # expose them without a URL. Treat only an entire input as an ID to avoid
    # misclassifying arbitrary text.
    if _XHS_NOTE_ID_RE.fullmatch(text):
        return f"https://www.xiaohongshu.com/explore/{text.lower()}"

    raise HTTPException(status_code=400, detail="No supported media URL was found in the pasted text")


def detect_platform(value: str) -> PlatformRoute:
    candidate = extract_supported_url(value)
    routed = _route_for_url(candidate)
    if not routed:  # defensive; extract_supported_url already enforces this
        raise HTTPException(status_code=400, detail="Unsupported platform or domain")
    return routed[1]
