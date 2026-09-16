import json
import unittest
import urllib.parse

from xhs_search import XhsSearchItem, _parse_google_translation, build_search_url


class XiaohongshuSearchTests(unittest.TestCase):
    def test_build_search_url_uses_xiaohongshu_search_result(self):
        url = build_search_url("서울 맛집")
        parsed = urllib.parse.urlsplit(url)
        params = urllib.parse.parse_qs(parsed.query)
        self.assertEqual(parsed.scheme, "https")
        self.assertEqual(parsed.netloc, "www.xiaohongshu.com")
        self.assertEqual(parsed.path, "/search_result")
        self.assertEqual(params["keyword"], ["서울 맛집"])
        self.assertEqual(params["source"], ["web_explore_feed"])

    def test_parse_google_translation_joins_segments(self):
        payload = [
            [["首尔", "서울", None, None], ["美食", "맛집", None, None]],
            None,
            "ko",
        ]
        self.assertEqual(_parse_google_translation(payload), "首尔美食")

    def test_parse_google_translation_rejects_unexpected_payload(self):
        self.assertEqual(_parse_google_translation({"bad": True}), "")
        self.assertEqual(_parse_google_translation([]), "")

    def test_search_item_contract(self):
        item = XhsSearchItem(
            note_id="abc",
            title="标题",
            author="作者",
            url="https://www.xiaohongshu.com/explore/abc?xsec_token=t&xsec_source=pc_search",
            thumbnail_url="https://sns-img.example/test.jpg",
            likes="120",
            collects="45",
            comments="8",
            note_type="normal",
        )
        self.assertEqual(item.note_id, "abc")
        self.assertIn("xsec_source=pc_search", item.url)
        self.assertEqual(item.likes, "120")


if __name__ == "__main__":
    unittest.main()
