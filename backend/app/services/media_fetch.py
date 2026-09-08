from __future__ import annotations

import ipaddress
import re
import shutil
import socket
import tempfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

_ALLOWED_SCHEMES = {"http", "https"}


def cleanup_dir(path: str) -> None:
    shutil.rmtree(path, ignore_errors=True)


def _assert_public_host(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in _ALLOWED_SCHEMES or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Resolved media URL is invalid")
    host = parsed.hostname
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise HTTPException(status_code=422, detail="Resolved media host is not public")
        return
    except ValueError:
        pass
    try:
        addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(status_code=422, detail="Resolved media host could not be resolved") from exc
    for entry in addresses:
        ip = ipaddress.ip_address(entry[4][0])
        if not ip.is_global:
            raise HTTPException(status_code=422, detail="Resolved media host points to a private/local address")


def _referer_for(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "douyin" in host or "byte" in host:
        return "https://www.douyin.com/"
    if "xhscdn" in host:
        return "https://www.xiaohongshu.com/"
    if "instagram" in host or "fbcdn" in host:
        return "https://www.instagram.com/"
    return "https://www.threads.com/"


def prepare_resolved_media(source_url: str, ext: str, max_size_mb: int = 500, tmp_root: str | None = None, referer: str | None = None) -> tuple[Path, str]:
    _assert_public_host(source_url)
    root = tmp_root or None
    tmpdir = tempfile.mkdtemp(prefix="insta-thread-asset-", dir=root)
    safe_ext = re.sub(r"[^a-zA-Z0-9]", "", ext or "bin")[:8] or "bin"
    path = Path(tmpdir) / f"download.{safe_ext}"
    max_bytes = max_size_mb * 1024 * 1024
    current = source_url

    try:
        with httpx.Client(timeout=60, follow_redirects=False, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = None
            for _ in range(6):
                _assert_public_host(current)
                request = client.build_request("GET", current, headers={"Referer": referer or _referer_for(current)})
                response = client.send(request, stream=True)
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    response.close()
                    if not location:
                        raise HTTPException(status_code=422, detail="Resolved media redirect was invalid")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                break
            else:
                raise HTTPException(status_code=422, detail="Too many media redirects")

            assert response is not None
            length = int(response.headers.get("content-length") or 0)
            if length and length > max_bytes:
                raise HTTPException(status_code=413, detail="Asset exceeds server file-size limit")
            total = 0
            with path.open("wb") as fh:
                for chunk in response.iter_bytes(256 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise HTTPException(status_code=413, detail="Asset exceeds server file-size limit")
                    fh.write(chunk)
            response.close()
    except HTTPException:
        cleanup_dir(tmpdir)
        raise
    except httpx.HTTPError as exc:
        cleanup_dir(tmpdir)
        raise HTTPException(status_code=422, detail=f"Could not fetch resolved media: {exc}") from exc

    return path, tmpdir


def download_resolved_media(source_url: str, ext: str, max_size_mb: int = 500, referer: str | None = None) -> FileResponse:
    path, tmpdir = prepare_resolved_media(source_url, ext, max_size_mb=max_size_mb, referer=referer)
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",
        background=BackgroundTask(cleanup_dir, tmpdir),
    )
