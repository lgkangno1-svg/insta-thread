from __future__ import annotations

import inspect
import unittest

from app_compact import CompactDownloaderApp


class CompactPostPanelContractTests(unittest.TestCase):
    def test_post_panel_is_fixed_height_scrollable_text(self) -> None:
        source = inspect.getsource(CompactDownloaderApp._build_ui)
        self.assertIn("tk.Text(", source)
        self.assertIn("height=self.POST_PREVIEW_ROWS", source)
        self.assertIn("yscrollcommand=post_scroll.set", source)
        self.assertIn("본문 전체 복사", source)

    def test_full_post_view_is_selectable_scrollable_window(self) -> None:
        source = inspect.getsource(CompactDownloaderApp._show_post_text)
        self.assertIn("tk.Toplevel", source)
        self.assertIn("tk.Text", source)
        self.assertIn("전체 복사", source)
        self.assertIn("vertical", source)

    def test_post_preview_row_budget_stays_compact(self) -> None:
        self.assertLessEqual(CompactDownloaderApp.POST_PREVIEW_ROWS, 4)
        self.assertGreaterEqual(CompactDownloaderApp.POST_PREVIEW_ROWS, 3)


if __name__ == "__main__":
    unittest.main()
