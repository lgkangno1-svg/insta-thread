import unittest

from instagram_fallback import _is_trusted_media_url, build_analysis_from_item


class InstagramFallbackTests(unittest.TestCase):
    def test_photo_post_builds_downloadable_image(self):
        item = {
            "caption": {"text": "photo post"},
            "user": {"username": "tester"},
            "image_versions2": {"candidates": [
                {"url": "https://scontent-test.cdninstagram.com/photo.jpg", "width": 1080, "height": 1350},
                {"url": "https://scontent-test.cdninstagram.com/small.jpg", "width": 320, "height": 400},
            ]},
        }
        data, direct = build_analysis_from_item("https://www.instagram.com/p/ABC123/", item)
        self.assertEqual(data["assets"][0]["id"], "image:0")
        self.assertEqual(data["assets"][0]["kind"], "image")
        self.assertEqual(data["assets"][0]["width"], 1080)
        self.assertIn("image:0", direct)
        self.assertEqual(direct["image:0"]["ext"], "jpg")

    def test_mixed_carousel_keeps_each_media_item(self):
        item = {
            "carousel_media": [
                {
                    "video_versions": [{"url": "https://scontent-test.cdninstagram.com/a.mp4", "width": 720, "height": 1280}],
                    "image_versions2": {"candidates": [{"url": "https://scontent-test.cdninstagram.com/a.jpg", "width": 720, "height": 1280}]},
                },
                {
                    "image_versions2": {"candidates": [{"url": "https://scontent-test.cdninstagram.com/b.jpg", "width": 1080, "height": 1080}]},
                },
            ],
            "user": {"username": "tester"},
        }
        data, direct = build_analysis_from_item("https://www.instagram.com/p/XYZ987/", item)
        self.assertEqual([x["id"] for x in data["assets"]], ["video:0", "image:1"])
        self.assertEqual(set(direct), {"video:0", "image:1"})
        self.assertEqual(data["assets"][0]["preview_url"], "https://scontent-test.cdninstagram.com/a.jpg")

    def test_media_host_allowlist(self):
        self.assertTrue(_is_trusted_media_url("https://scontent-sea1-1.cdninstagram.com/v/foo.jpg"))
        self.assertTrue(_is_trusted_media_url("https://instagram.fabc1-2.fna.fbcdn.net/v/foo.mp4"))
        self.assertFalse(_is_trusted_media_url("http://scontent-test.cdninstagram.com/foo.jpg"))
        self.assertFalse(_is_trusted_media_url("https://evil.example/foo.jpg"))
        self.assertFalse(_is_trusted_media_url("https://cdninstagram.com.evil.example/foo.jpg"))


if __name__ == "__main__":
    unittest.main()
