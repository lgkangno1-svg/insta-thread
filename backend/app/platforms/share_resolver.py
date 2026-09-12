from __future__ import annotations

import html as html_lib
import re
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException

from .router import detect_platform, extract_supported_url


_ALLOWED_REDIRECT_HOSTS: dict[str, set[str]] = {
    "youtube": {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"},
    "instagram": {"instagram.com", "www.instagram.com", "m.instagram.com", "instagr.am", "www.instagr.am"},
    "xiaohongshu": {
        "xiaohongshu.com", "www.xiaohongshu.com", "m.xiaohongshu.com",
        "rednote.com", "www.rednote.com", "m.rednote.com",
        "xhslink.com", "www.xhslink.com", "xhslink.cn", "www.xhslink.cn",
    },
    "threads": {"threads.com", "www.threads.com", "threads.net", "www.threads.net"},
    "douyin": {
        "douyin.com", "www.douyin.com", "m.douyin.com", "v.douyin.com",
        "iesdouyin.com", "www.iesdouyin.com",
    },
}

# yt-dlp natively handles youtu.be well; resolving it in advance can hit a regional
# consent redirect, so leave it untouched. Resolve wrappers where the platform adapter
# needs the canonical post URL or where a short link carries required share context.
_RESOLVE_HOSTS = {
    "instagr.am", "www.instagr.am",
    "xhslink.com", "www.xhslink.com", "xhslink.cn", "www.xhslink.cn",
    "v.douyin.com", "iesdouyin.com", "www.iesdouyin.com",
}
_RESOLVE_PATH_PREFIXES = {
    "instagram": ("/share/",),
    "threads": ("/share/", "/t/"),
}

_MEDIA_PATHS: dict[str, tuple[re.Pattern[str], ...]] = {
    "instagram": (
        re.compile(r"^/(?:reel|p|tv)/[^/?#]+/?$", re.I),
    ),
    "threads": (
        re.compile(r"^/@[^/]+/post/[\w-]+/?$", re.I),
        re.compile(r"^/t/[\w-]+/?$", re.I),
    ),
    "xiaohongshu": (
        re.compile(r"^/(?:explore|discovery/item)/[0-9a-f]{24}/?$", re.I),
        re.compile(r"^/user/profile/[^/]+/[0-9a-f]{24}/?$", re.I),
    ),
    "douyin": (
        re.compile(r"^/(?:video|note)/\d{15,22}/?$", re.I),
        re.compile(r"^/share/video/\d{15,22}/?$", re.I),
    ),
}


def needs_resolution(url: str, platform: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if host in _RESOLVE_HOSTS:
        return True
    return any(parsed.path.startswith(prefix) for prefix in _RESOLVE_PATH_PREFIXES.get(platform, ()))


def _is_media_path(url: str, platform: str) -> bool:
    path = urlparse(url).path
    return any(pattern.fullmatch(path) for pattern in _MEDIA_PATHS.get(platform, ()))


def _attribute(tag: str, name: str) -> str | None:
    match = re.search(rf"\b{re.escape(name)}\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
    return html_lib.unescape(match.group(2).strip()) if match else None


def _document_media_target(page: str, platform: str) -> str | None:
    """Read a canonical public-media URL from a 200 share-wrapper document.

    Instagram and Threads increasingly serve share-sheet wrappers as HTTP 200 pages
    whose canonical link points at the real post, rather than issuing a 30x redirect.
    Only same-platform media paths are accepted; profile/login/home canonicals are
    deliberately ignored.
    """
    for tag in re.findall(r"<link\b[^>]*>", page, re.I | re.S):
        rel = (_attribute(tag, "rel") or "").lower().split()
        href = _attribute(tag, "href")
        if "canonical" in rel and href and _is_media_path(href, platform):
            return href

    for tag in re.findall(r"<meta\b[^>]*>", page, re.I | re.S):
        prop = (_attribute(tag, "property") or _attribute(tag, "name") or "").lower()
        content = _attribute(tag, "content")
        if prop == "og:url" and content and _is_media_path(content, platform):
            return content
    return None


def _validate_target(target: str, platform: str, allowed: set[str]) -> str:
    parsed = urlparse(target)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or host not in allowed:
        raise HTTPException(status_code=422, detail="Share link redirected outside the supported platform")
    routed = detect_platform(target)
    if routed.platform != platform:
        raise HTTPException(status_code=422, detail="Share link redirected to a different platform")
    return target


def resolve_share_url(value: str) -> str:
    """Resolve official short/share wrappers while rejecting cross-platform redirects."""
    start = extract_supported_url(value)
    route = detect_platform(start)
    if not needs_resolution(start, route.platform):
        return start

    allowed = _ALLOWED_REDIRECT_HOSTS[route.platform]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8,zh-CN;q=0.7",
    }
    current = start
    try:
        with httpx.Client(timeout=20, follow_redirects=False, headers=headers) as client:
            for _ in range(7):
                response = client.get(current)
                if response.status_code not in {301, 302, 303, 307, 308}:
                    response.raise_for_status()
                    document_target = _document_media_target(response.text, route.platform)
                    if document_target:
                        target = urljoin(current, document_target)
                        _validate_target(target, route.platform, allowed)
                        return extract_supported_url(target)

                    # Direct media paths need no further document-level resolution.
                    if _is_media_path(current, route.platform):
                        return extract_supported_url(current)

                    # A short/share wrapper that lands on a profile, login page or home
                    # page is not the requested post. Do not pass that unrelated page to
                    # an extractor because it can produce misleading media or errors.
                    raise HTTPException(
                        status_code=422,
                        detail="This share link no longer resolves to a public media post. Copy the link again from the original post.",
                    )
                location = response.headers.get("location")
                if not location:
                    raise HTTPException(status_code=422, detail="Share link redirect did not provide a destination")
                target = urljoin(current, location)
                _validate_target(target, route.platform, allowed)
                current = target
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve this public share link: {exc}") from exc

    raise HTTPException(status_code=422, detail="Share link used too many redirects")
