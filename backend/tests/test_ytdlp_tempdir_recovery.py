"""YouTube worker must survive a removed/stale tempfile directory without network calls."""
import os
import shutil
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.platforms import ytdlp_adapter


class FakeYouTubeDL:
    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def extract_info(self, _url, download=False):
        assert download
        target = Path(self.opts["outtmpl"]).parent / "proof.mp4"
        target.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"0" * 8192)
        return {"id": "fixture"}


@pytest.fixture
def fake_ytdlp(monkeypatch):
    monkeypatch.setattr(ytdlp_adapter, "yt_dlp", SimpleNamespace(YoutubeDL=FakeYouTubeDL))


def test_youtube_download_recovers_stale_tempdir(monkeypatch, tmp_path, fake_ytdlp):
    if os.name != "posix":
        pytest.skip("POSIX fallback is platform-specific")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "deleted-runner-private-tmp"))
    path, scratch = ytdlp_adapter.prepare_video(
        "https://www.youtube.com/watch?v=aqz-KE-bpKQ", "video:360"
    )
    try:
        assert path.is_file()
        assert path.read_bytes()[4:8] == b"ftyp"
        assert scratch.startswith("/tmp/")
    finally:
        shutil.rmtree(scratch)


def test_youtube_download_creates_explicit_scratch_root(tmp_path, fake_ytdlp):
    root = tmp_path / "private-download-storage"
    path, scratch = ytdlp_adapter.prepare_video(
        "https://www.youtube.com/watch?v=aqz-KE-bpKQ", "video:360", tmp_root=str(root)
    )
    try:
        assert path.is_file()
        assert root.is_dir()
        assert Path(scratch).parent == root
    finally:
        shutil.rmtree(scratch)


def test_youtube_invalid_scratch_root_is_actionable(tmp_path, fake_ytdlp):
    occupied = tmp_path / "not-a-directory"
    occupied.write_text("keep", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        ytdlp_adapter.prepare_video(
            "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
            "video:360",
            tmp_root=str(occupied / "downloads"),
        )
    assert exc.value.status_code == 503
