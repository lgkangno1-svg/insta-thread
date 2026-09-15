import tempfile
import unittest
from pathlib import Path

from core import assets_from_response, detect_platform, extract_supported_url, sanitize_filename, unique_path


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

    def test_asset_mapping(self):
        assets = assets_from_response({"assets": [{"id": "v720", "kind": "video", "label": "720p", "ext": "mp4", "width": 1280, "height": 720}]})
        self.assertEqual(len(assets), 1)
        self.assertIn("720p", assets[0].display)
        self.assertIn("1280×720", assets[0].display)


if __name__ == "__main__":
    unittest.main()
