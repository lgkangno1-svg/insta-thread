from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web" / "public"
CANONICAL = "https://download.avocadoss.co.kr"
INDEXABLE = {
    "index.html": f"{CANONICAL}/",
    "youtube-downloader.html": f"{CANONICAL}/youtube-downloader",
    "instagram-reels-downloader.html": f"{CANONICAL}/instagram-reels-downloader",
    "threads-downloader.html": f"{CANONICAL}/threads-downloader",
    "douyin-downloader.html": f"{CANONICAL}/douyin-downloader",
    "xiaohongshu-downloader.html": f"{CANONICAL}/xiaohongshu-downloader",
    "faq.html": f"{CANONICAL}/faq",
}


def one(pattern: str, text: str, label: str, filename: str) -> str:
    match = re.search(pattern, text, re.I | re.S)
    if not match:
        raise AssertionError(f"{filename}: missing {label}")
    return re.sub(r"\s+", " ", match.group(1)).strip()


def main() -> int:
    titles: set[str] = set()
    descriptions: set[str] = set()
    for filename, canonical in INDEXABLE.items():
        text = (PUBLIC / filename).read_text(encoding="utf-8")
        title = one(r"<title>(.*?)</title>", text, "title", filename)
        desc = one(r'<meta\s+name="description"\s+content="([^"]+)"', text, "meta description", filename)
        href = one(r'<link\s+rel="canonical"\s+href="([^"]+)"', text, "canonical", filename)
        h1 = one(r"<h1[^>]*>(.*?)</h1>", text, "h1", filename)
        robots = one(r'<meta\s+name="robots"\s+content="([^"]+)"', text, "robots", filename)
        if href != canonical:
            raise AssertionError(f"{filename}: canonical {href!r} != {canonical!r}")
        if "index" not in robots or "follow" not in robots:
            raise AssertionError(f"{filename}: robots must allow index/follow")
        if not (15 <= len(title) <= 75):
            raise AssertionError(f"{filename}: title length {len(title)} is outside 15..75")
        if not (50 <= len(desc) <= 180):
            raise AssertionError(f"{filename}: description length {len(desc)} is outside 50..180")
        if len(re.sub(r"<[^>]+>", "", h1).strip()) < 8:
            raise AssertionError(f"{filename}: h1 is too short")
        if title in titles:
            raise AssertionError(f"{filename}: duplicate title")
        if desc in descriptions:
            raise AssertionError(f"{filename}: duplicate meta description")
        titles.add(title)
        descriptions.add(desc)
        for raw in re.findall(r'<script\s+type="application/ld\+json">(.*?)</script>', text, re.I | re.S):
            json.loads(raw)

    sitemap = ET.parse(PUBLIC / "sitemap.xml")
    namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_urls = {node.text for node in sitemap.findall("sm:url/sm:loc", namespace)}
    missing = set(INDEXABLE.values()) - sitemap_urls
    if missing:
        raise AssertionError(f"sitemap missing indexable URLs: {sorted(missing)}")

    robots = (PUBLIC / "robots.txt").read_text(encoding="utf-8")
    if f"Sitemap: {CANONICAL}/sitemap.xml" not in robots:
        raise AssertionError("robots.txt must advertise the canonical sitemap")
    if "Disallow: /api/" not in robots:
        raise AssertionError("robots.txt must keep API routes out of crawl space")

    print(f"SEO checks passed for {len(INDEXABLE)} indexable pages")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, ET.ParseError, json.JSONDecodeError) as exc:
        print(f"SEO check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
