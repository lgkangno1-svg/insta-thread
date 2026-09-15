from __future__ import annotations

import unittest
from unittest.mock import patch

from app.platforms import instagram_adapter


class InstagramAdapterTests(unittest.TestCase):
    def test_single_photo_post_is_downloadable(self):
        item = {
            "caption": {"text": "photo caption"},
            "user": {"username": "tester"},
            "image_versions2": {
                "candidates": [
                    {"url": "https://cdn.example/full.jpg", "width": 1440, "height": 1800},
                    {"url": "https://cdn.example/small.jpg", "width": 640, "height": 800},
                ]
            },
        }
        with patch.object(instagram_adapter, "_query", return_value=item):
            result = instagram_adapter.analyze("https://www.instagram.com/p/ABC123/")
            self.assertEqual(result.platform, "instagram")
            self.assertEqual(result.assets[0].id, "image:0")
            self.assertEqual(result.assets[0].kind, "image")
            self.assertEqual(result.assets[0].preview_url, "https://cdn.example/full.jpg")

    def test_carousel_returns_each_media_item(self):
        item = {
            "caption": {"text": "carousel"},
            "user": {"username": "tester"},
            "carousel_media": [
                {
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/one.jpg", "width": 1080, "height": 1350}
                        ]
                    }
                },
                {
                    "video_versions": [
                        {"url": "https://cdn.example/two.mp4", "width": 720, "height": 1280}
                    ],
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/two-cover.jpg", "width": 720, "height": 1280}
                        ]
                    },
                },
                {
                    "image_versions2": {
                        "candidates": [
                            {"url": "https://cdn.example/three.jpg", "width": 1080, "height": 1080}
                        ]
                    }
                },
            ],
        }
        with patch.object(instagram_adapter, "_query", return_value=item):
            result = instagram_adapter.analyze("https://www.instagram.com/p/ABC123/?img_index=1")
            self.assertEqual([asset.id for asset in result.assets], ["image:0", "video:1", "image:2"])
            self.assertEqual(result.assets[1].kind, "video")
            self.assertEqual(result.assets[1].preview_url, "https://cdn.example/two-cover.jpg")

    def test_resolve_carousel_assets(self):
        item = {
            "carousel_media": [
                {"image_versions2": {"candidates": [{"url": "https://cdn.example/one.jpg", "width": 1080, "height": 1350}]}},
                {
                    "video_versions": [{"url": "https://cdn.example/two.mp4", "width": 720, "height": 1280}],
                    "image_versions2": {"candidates": [{"url": "https://cdn.example/two-cover.jpg", "width": 720, "height": 1280}]},
                },
            ]
        }
        with patch.object(instagram_adapter, "_query", return_value=item):
            self.assertEqual(
                instagram_adapter.resolve_asset("https://www.instagram.com/p/ABC123/", "image:0"),
                ("https://cdn.example/one.jpg", "jpg"),
            )
            self.assertEqual(
                instagram_adapter.resolve_asset("https://www.instagram.com/p/ABC123/", "video:1"),
                ("https://cdn.example/two.mp4", "mp4"),
            )


if __name__ == "__main__":
    unittest.main()
