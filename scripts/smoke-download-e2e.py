#!/usr/bin/env python3
"""Read-only-public-post E2E: analyze -> signed job -> bytes, without retaining media."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def signature_ok(head: bytes) -> bool:
    return (
        head[4:8] == b"ftyp"
        or head.startswith(b"\xff\xd8\xff")
        or head.startswith(b"\x89PNG\r\n\x1a\n")
        or head.startswith(b"GIF87a")
        or head.startswith(b"GIF89a")
        or (head.startswith(b"RIFF") and head[8:12] == b"WEBP")
        or head.startswith(b"\x1a\x45\xdf\xa3")
        or head.startswith(b"PK\x03\x04")
    )


def probe(base: str, post_url: str, asset_id: str | None, max_bytes: int) -> dict:
    base = base.rstrip("/")
    def call(path: str, payload: dict | None = None):
        body = json.dumps(payload).encode() if payload is not None else None
        headers = {"User-Agent": "Mozilla/5.0", "Origin": base, "Referer": base + "/", "Content-Type": "application/json"}
        return urlopen(Request(urljoin(base + "/", path.lstrip("/")), data=body,
                               method="POST" if body is not None else "GET", headers=headers), timeout=60)

    with call("/api/v1/analyze", {"url": post_url}) as r:
        analysis = json.load(r)
    assets = analysis.get("assets") or []
    preferred = asset_id or next((x["id"] for x in assets if x["id"] == "video:360"), None)
    preferred = preferred or next((x["id"] for x in assets if x.get("kind") == "video"), None)
    preferred = preferred or next((x["id"] for x in assets if x.get("kind") in ("image", "thumbnail")), None)
    if not preferred or preferred not in [x["id"] for x in assets]:
        raise ValueError(f"Requested file not available: {preferred}")
    with call("/api/v1/jobs", {"url": post_url, "asset_id": preferred, "analysis_token": analysis["analysis_token"]}) as r:
        job = json.load(r)
    status = "queued"
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        time.sleep(0.8)
        with call("/api/v1/jobs/" + job["id"]) as r:
            result = json.load(r)
        status = result.get("status")
        if status in ("ready", "error"):
            break
    if status != "ready":
        raise ValueError("Download job " + str(status) + ": " + str(result.get("error", ""))[:180])
    h = hashlib.sha256()
    size = 0
    head = b""
    with call(result["download_url"]) as response:
        while True:
            chunk = response.read(262144)
            if not chunk:
                break
            if len(head) < 16:
                head = (head + chunk)[:16]
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("Download exceeds smoke-test byte ceiling")
            h.update(chunk)
    if size < 1024 or not signature_ok(head):
        raise ValueError("File empty or media signature invalid")
    return {"platform": analysis.get("platform"), "asset_id": preferred,
            "analyzed_assets": len(assets), "bytes": size, "sha256": h.hexdigest(), "valid": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://download.avocadoss.co.kr")
    parser.add_argument("--url", required=True)
    parser.add_argument("--asset-id")
    parser.add_argument("--max-mb", type=int, default=100)
    args = parser.parse_args()
    try:
        result = probe(args.base, args.url, args.asset_id, args.max_mb * 1024**2)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (HTTPError, OSError, TimeoutError, ValueError, KeyError) as exc:
        print(json.dumps({"valid": False, "error_type": type(exc).__name__, "error": str(exc)[:300]}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
