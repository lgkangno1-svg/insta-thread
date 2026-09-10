from __future__ import annotations

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


def needs_resolution(url: str, platform: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if host in _RESOLVE_HOSTS:
        return True
    return any(parsed.path.startswith(prefix) for prefix in _RESOLVE_PATH_PREFIXES.get(platform, ()))


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
                    # Run the final URL through the common canonicalizer. This converts
                    # RedNote/profile-note targets to the Xiaohongshu note form while
                    # preserving xsec_token and other query parameters.
                    return extract_supported_url(current)
                location = response.headers.get("location")
                if not location:
                    raise HTTPException(status_code=422, detail="Share link redirect did not provide a destination")
                target = urljoin(current, location)
                parsed = urlparse(target)
                host = (parsed.hostname or "").lower().rstrip(".")
                if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password or host not in allowed:
                    raise HTTPException(status_code=422, detail="Share link redirected outside the supported platform")
                current = target
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=422, detail=f"Could not resolve this public share link: {exc}") from exc

    raise HTTPException(status_code=422, detail="Share link used too many redirects")
