#!/usr/bin/env python3
"""MiniPC-only live browser quality gate; does not download third-party media."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://download.avocadoss.co.kr"
CHROME = os.environ.get("CHROME_BIN", "/home/tnfwod/.local/bin/google-chrome")


def expected_production_sha() -> str:
    result = subprocess.run(
        ["git", "ls-remote", "origin", "refs/heads/production"],
        cwd=ROOT, check=True, capture_output=True, text=True, timeout=25,
    )
    sha = result.stdout.split()[0] if result.stdout.strip() else ""
    if len(sha) != 40 or any(ch not in "0123456789abcdef" for ch in sha):
        raise AssertionError("production Git SHA is unavailable")
    return sha


def main() -> None:
    expected = expected_production_sha()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=CHROME, headless=True, args=["--no-sandbox"],
        )
        try:
            context = browser.new_context(
                viewport={"width": 390, "height": 844}, locale="ko-KR",
            )
            page = context.new_page()
            build = page.goto(SITE + "/build.txt", wait_until="domcontentloaded", timeout=25000)
            if build is None or build.status != 200:
                raise AssertionError("live build.txt is unavailable")
            live_sha = page.locator("body").inner_text().strip()
            if live_sha != expected:
                raise AssertionError(f"live SHA mismatch: expected={expected} live={live_sha}")

            response = page.goto(SITE, wait_until="domcontentloaded", timeout=25000)
            if response is None or response.status != 200:
                raise AssertionError("live download home is unavailable")
            if "다운로더" not in page.title():
                raise AssertionError("the Korean download page title is missing")

            field = page.get_by_role("textbox", name="공개 SNS 영상 또는 게시물 주소")
            submit = page.get_by_role("button", name="링크 분석하기")
            if field.count() != 1 or submit.count() != 1:
                raise AssertionError("Korean accessible input/button are missing")

            field.fill("https://example.com/not-supported")
            submit.click()
            status = page.locator("[data-status]")
            status.wait_for(state="visible", timeout=10000)
            page.wait_for_function(
                "() => document.querySelector('[data-status]')?.textContent?.includes('지원하는 공개')",
                timeout=12000,
            )
            for path, platform in [
                ("/youtube-downloader", "youtube"),
                ("/instagram-reels-downloader", "instagram"),
                ("/threads-downloader", "threads"),
                ("/douyin-downloader", "douyin"),
                ("/xiaohongshu-downloader", "xiaohongshu"),
            ]:
                result = context.request.get(SITE + path, timeout=15000)
                if result.status != 200 or f'data-platform="{platform}"' not in result.text():
                    raise AssertionError(f"platform landing regression: {path} HTTP {result.status}")

            print(f"PASS minipc-download-live-browser-qa sha={live_sha} 5-platforms Korean UI")
        finally:
            browser.close()


if __name__ == "__main__":
    main()
