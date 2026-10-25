"""Verify the actual downloaded output when the worker's cached TMPDIR vanished."""

import os
import tempfile
import zipfile
from pathlib import Path

import pytest

from app.services import media_fetch


class _Response:
    headers = {"content-length": "5"}

    def iter_bytes(self, _chunk_size):
        yield b"hello"

    def close(self):
        pass


@pytest.mark.skipif(os.name != "posix", reason="POSIX stale tempdir fallback")
@pytest.mark.parametrize("as_archive", [False, True])
def test_missing_cached_tempdir_produces_downloadable_file(monkeypatch, tmp_path, as_archive):
    # Exercise both public download paths, without making external requests.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "deleted-scratch"))
    monkeypatch.setattr(media_fetch, "_open_public_stream", lambda *a, **kw: _Response())
    url = "https://1.1.1.1/image.jpg"
    if as_archive:
        result, workdir = media_fetch.prepare_resolved_archive([(url, "jpg")])
    else:
        result, workdir = media_fetch.prepare_resolved_media(url, "jpg")
    try:
        assert result.is_file()
        assert result.parent == Path(workdir)
        if as_archive:
            with zipfile.ZipFile(result) as archive:
                assert archive.namelist() == ["image_01.jpg"]
                assert archive.read("image_01.jpg") == b"hello"
        else:
            assert result.read_bytes() == b"hello"
    finally:
        media_fetch.cleanup_dir(workdir)
    assert not Path(workdir).exists()
