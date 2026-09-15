import tempfile
import unittest
from pathlib import Path

from core import (
    RELEASE_ASSET_NAME,
    RELEASE_CHECKSUM_NAME,
    assets_from_response,
    detect_platform,
    extract_supported_url,
    is_newer_version,
    sanitize_filename,
    select_release_info,
    unique_path,
)


class CoreTests(unittest.TestCase):
    def test_detects_supported_platforms(self):
        cases = {
            "https://www.youtube.com/watch?v=abc": "youtube",
            "https://www.instagram.com/reel/ABC/": "instagram",
            "https://www.threads.net/@user/post/ABC": "threads",
            "https://v.douyin.com/ABC/": "douyin",
            "https://www.xiaohongshu.com/explore/0123456789abcdef01234567": "xiaohongshu",
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(detect_platform(url), expected)

    def test_extracts_url_from_share_text(self):
        text = "이 영상 봐봐 https://www.instagram.com/reel/ABC/?igsh=123 감사합니다!"
        self.assertEqual(extract_supported_url(text), "https://www.instagram.com/reel/ABC/?igsh=123")

    def test_extracts_bare_url(self):
        self.assertEqual(
            extract_supported_url("threads.net/@user/post/ABC"),
            "https://threads.net/@user/post/ABC",
        )

    def test_xiaohongshu_note_id(self):
        note = "0123456789ABCDEF01234567"
        self.assertEqual(
            extract_supported_url(note),
            "https://www.xiaohongshu.com/explore/0123456789abcdef01234567",
        )

    def test_filename_sanitizing_and_collision(self):
        self.assertEqual(sanitize_filename('bad:name?.mp4'), 'bad_name_.mp4')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            first = unique_path(folder, "clip.mp4")
            first.write_bytes(b"x")
            self.assertEqual(unique_path(folder, "clip.mp4").name, "clip (2).mp4")

    def test_partial_file_also_reserves_name(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / "clip.mp4.part").write_bytes(b"partial")
            self.assertEqual(unique_path(folder, "clip.mp4").name, "clip (2).mp4")

    def test_asset_mapping(self):
        assets = assets_from_response({"assets": [{"id": "v720", "kind": "video", "label": "720p", "ext": "mp4", "width": 1280, "height": 720}]})
        self.assertEqual(len(assets), 1)
        self.assertIn("720p", assets[0].display)
        self.assertIn("1280×720", assets[0].display)

    def test_semantic_version_comparison(self):
        self.assertTrue(is_newer_version("1.1.0", "1.0.9"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.0"))
        self.assertFalse(is_newer_version("bad", "1.0.0"))

    def test_release_selection_requires_official_assets(self):
        tag = "desktop-v1.1.0"
        base = f"https://github.com/lgkangno1-svg/insta-thread/releases/download/{tag}"
        releases = [{
            "tag_name": tag,
            "draft": False,
            "prerelease": False,
            "html_url": "https://github.com/lgkangno1-svg/insta-thread/releases/tag/desktop-v1.1.0",
            "assets": [
                {"name": RELEASE_ASSET_NAME, "browser_download_url": f"{base}/{RELEASE_ASSET_NAME}"},
                {"name": RELEASE_CHECKSUM_NAME, "browser_download_url": f"{base}/{RELEASE_CHECKSUM_NAME}"},
            ],
        }]
        info = select_release_info(releases, "1.0.0")
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "1.1.0")

    def test_release_selection_rejects_untrusted_download_host(self):
        releases = [{
            "tag_name": "desktop-v9.9.9",
            "draft": False,
            "prerelease": False,
            "assets": [
                {"name": RELEASE_ASSET_NAME, "browser_download_url": "https://evil.example/AVOCADOSS-Downloader.exe"},
                {"name": RELEASE_CHECKSUM_NAME, "browser_download_url": "https://evil.example/AVOCADOSS-Downloader.exe.sha256"},
            ],
        }]
        self.assertIsNone(select_release_info(releases, "1.0.0"))


if __name__ == "__main__":
    unittest.main()
