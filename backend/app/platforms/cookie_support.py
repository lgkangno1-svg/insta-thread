from __future__ import annotations

import os
from http.cookiejar import MozillaCookieJar
from pathlib import Path

import httpx


def cookie_file_path() -> Path | None:
    """Return the owner-controlled Netscape cookie file when one is available.

    Docker deployments normally set YTDLP_COOKIE_FILE explicitly. The rootless
    miniPC service keeps the same file under its isolated service home; using that
    location as a fallback lets HTTP resolvers and yt-dlp share one guest session
    without embedding credentials in source code.
    """
    configured = os.getenv("YTDLP_COOKIE_FILE", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(Path.home() / "services" / "insta-thread" / "config" / "guest.cookies.txt")

    for path in candidates:
        try:
            if path.is_file() and path.stat().st_size > 20:
                return path
        except OSError:
            continue
    return None


def httpx_guest_cookies() -> httpx.Cookies:
    """Load the shared Netscape jar while preserving each cookie's domain/path."""
    cookies = httpx.Cookies()
    path = cookie_file_path()
    if path is None:
        return cookies

    jar = MozillaCookieJar(str(path))
    try:
        jar.load(ignore_discard=True, ignore_expires=False)
    except (OSError, ValueError, EOFError):
        return cookies

    for item in jar:
        if not item.name or item.value is None:
            continue
        domain = (item.domain or "").strip()
        if not domain:
            continue
        cookies.set(item.name, item.value, domain=domain, path=item.path or "/")
    return cookies
