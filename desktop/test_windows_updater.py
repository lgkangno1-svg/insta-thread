import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import windows_updater


class WindowsUpdaterTests(unittest.TestCase):
    def test_powershell_round_trip_preserves_unicode_and_quotes(self):
        source = Path("C:/Users/test/다운로드/new 'version'.exe")
        target = Path("C:/Users/test/바탕 화면/AVOCADOSS-Downloader.exe")
        log = Path("C:/Users/test/AppData/Local/Temp/업데이트.log")
        script = windows_updater.build_update_script(source, target, 4321, log)
        encoded = windows_updater.encode_powershell(script)
        decoded = base64.b64decode(encoded).decode("utf-16le")
        self.assertEqual(decoded, script)
        self.assertIn("다운로드", decoded)
        self.assertIn("new ''version''.exe", decoded)
        self.assertIn("post-copy SHA-256 mismatch", decoded)
        self.assertIn("replacement attempt", decoded)
        self.assertIn("launching verified update from temp as fallback", decoded)

    @unittest.skipUnless(os.name == "nt", "Windows-only process handoff test")
    def test_schedule_uses_hidden_encoded_powershell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "한글 폴더"
            root.mkdir()
            source = root / "new.exe"
            target = root / "AVOCADOSS-Downloader.exe"
            source.write_bytes(b"new")
            target.write_bytes(b"old")
            with mock.patch.object(windows_updater.subprocess, "Popen") as popen:
                log = windows_updater.schedule_windows_self_update(source, target, 9876)
            popen.assert_called_once()
            args = popen.call_args.args[0]
            self.assertEqual(args[0].lower(), "powershell.exe")
            self.assertIn("-EncodedCommand", args)
            encoded = args[args.index("-EncodedCommand") + 1]
            script = base64.b64decode(encoded).decode("utf-16le")
            self.assertIn(str(source.resolve()).replace("'", "''"), script)
            self.assertIn(str(target.resolve()).replace("'", "''"), script)
            self.assertEqual(log.suffix, ".log")

    def test_patch_replaces_core_entrypoint(self):
        class FakeApiError(RuntimeError):
            pass

        class FakeCore:
            ApiError = FakeApiError

            @staticmethod
            def schedule_windows_self_update(*_args):
                raise AssertionError("old updater should be replaced")

        old = FakeCore.schedule_windows_self_update
        windows_updater.patch_windows_updater(FakeCore)
        self.assertIsNot(FakeCore.schedule_windows_self_update, old)


if __name__ == "__main__":
    unittest.main()
