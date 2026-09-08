from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from fastapi import HTTPException


@dataclass(frozen=True)
class PlatformRoute:
    platform: str
    canonical_host: str


_HOSTS: dict[str, PlatformRoute] = {
    "youtube.com": PlatformRoute("youtube", "youtube.com"),
    "www.youtube.com": PlatformRoute("youtube", "youtube.com"),
    "m.youtube.com": PlatformRoute("youtube", "youtube.com"),
    "youtu.be": PlatformRoute("youtube", "youtube.com"),
    "instagram.com": PlatformRoute("instagram", "instagram.com"),
    "www.instagram.com": PlatformRoute("instagram", "instagram.com"),
    "xiaohongshu.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.xiaohongshu.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "xhslink.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "www.xhslink.com": PlatformRoute("xiaohongshu", "xiaohongshu.com"),
    "threads.net": PlatformRoute("threads", "threads.com"),
    "www.threads.net": PlatformRoute("threads", "threads.com"),
    "threads.com": PlatformRoute("threads", "threads.com"),
    "www.threads.com": PlatformRoute("threads", "threads.com"),
    "douyin.com": PlatformRoute("douyin", "douyin.com"),
    "www.douyin.com": PlatformRoute("douyin", "douyin.com"),
    "v.douyin.com": PlatformRoute("douyin", "douyin.com"),
}


def detect_platform(url: str) -> PlatformRoute:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="Only http/https URLs are supported")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Credentials in URLs are not allowed")
    host = (parsed.hostname or "").lower().rstrip(".")
    route = _HOSTS.get(host)
    if not route:
        raise HTTPException(status_code=400, detail="Unsupported platform or domain")
    return route
