import json
import tempfile
import unittest
from pathlib import Path

from core import Asset
from desktop_extras import (
    improve_download_name,
    load_preferences,
    preferred_filename,
    primary_asset_indices,
    save_preferences,
    source_identifier,
)


class DesktopExtrasTests(unittest.TestCase):
    def test_preferences_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            save_preferences(r"C:\Users\tester\Downloads", path)
            self.assertEqual(load_preferences(path)["download_folder"], r"C:\Users\tester\Downloads")

    def test_invalid_preferences_fall_back(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("[]", encoding="utf-8")
            loaded = load_preferences(path)
            self.assertIn("download_folder", loaded)
            self.assertTrue(loaded["download_folder"])

    def test_primary_assets_exclude_video_covers(self):
        assets = [
            Asset(id="video:best", kind="video", label="Video", ext="mp4"),
            Asset(id="thumbnail:0", kind="thumbnail", label="Cover", ext="jpg"),
            Asset(id="thumbnail:1", kind="thumbnail", label="Cover 2", ext="jpg"),
        ]
        self.assertEqual(primary_asset_indices(assets), [0])

    def test_primary_assets_include_entire_carousel(self):
        assets = [
            Asset(id="image:0", kind="image", label="Image 1", ext="jpg"),
            Asset(id="video:1", kind="video", label="Video 2", ext="mp4"),
            Asset(id="image:2", kind="image", label="Image 3", ext="jpg"),
        ]
        self.assertEqual(primary_asset_indices(assets), [0, 1, 2])

    def test_source_identifier(self):
        self.assertEqual(source_identifier("https://www.instagram.com/p/ABC_123/", "instagram"), "ABC_123")
        self.assertEqual(source_identifier("https://www.threads.net/@user/post/XYZ", "threads"), "XYZ")
        self.assertEqual(source_identifier("https://www.youtube.com/watch?v=abc123", "youtube"), "abc123")

    def test_preferred_filename_is_human_readable(self):
        asset = Asset(id="image:0", kind="image", label="Image 1", ext="jpg")
        name = preferred_filename(
            {
                "platform": "instagram",
                "author": "@hello.world",
                "source_url": "https://www.instagram.com/p/ABC_123/",
            },
            asset,
            0,
        )
        self.assertEqual(name, "instagram-hello.world-ABC_123-image-01.jpg")

    def test_generic_download_filename_is_improved(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "download.mp4"
            source.write_bytes(b"test")
            asset = Asset(id="video:best", kind="video", label="Video", ext="mp4")
            renamed = improve_download_name(
                source,
                {
                    "platform": "threads",
                    "author": "@fruit",
                    "source_url": "https://www.threads.net/@fruit/post/POST123",
                },
                asset,
                0,
            )
            self.assertTrue(renamed.is_file())
            self.assertEqual(renamed.name, "threads-fruit-POST123-video-01.mp4")
            self.assertFalse(source.exists())


if __name__ == "__main__":
    unittest.main()
