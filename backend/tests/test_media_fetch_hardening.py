from app.services.media_fetch import _content_length


def test_content_length_parser_tolerates_cdn_variants():
    assert _content_length("877722") == 877722
    assert _content_length(" 877722 ") == 877722
    assert _content_length(None) == 0
    assert _content_length("") == 0
    assert _content_length("chunked") == 0
    assert _content_length("-1") == 0



def test_stale_default_tempdir_recovers_on_linux(monkeypatch, tmp_path):
    import os
    import shutil
    import tempfile
    import pytest
    from app.services.media_fetch import _make_job_tempdir

    if os.name != "posix":
        pytest.skip("/tmp fallback is specific to POSIX production")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "removed-by-cleanup"))
    created = _make_job_tempdir("insta-thread-asset-", None)
    try:
        assert os.path.isdir(created)
        assert created.startswith("/tmp/")
    finally:
        shutil.rmtree(created)


def test_explicit_tmp_root_is_recreated_if_missing(tmp_path):
    import shutil
    from app.services.media_fetch import _make_job_tempdir

    root = tmp_path / "media-scratch"
    created = _make_job_tempdir("insta-thread-asset-", str(root))
    try:
        assert root.is_dir()
        assert (root / created.split("/")[-1]).is_dir()
    finally:
        shutil.rmtree(created)


def test_unusable_tmp_root_returns_service_error(tmp_path):
    import pytest
    from fastapi import HTTPException
    from app.services.media_fetch import _make_job_tempdir

    parent_file = tmp_path / "occupied"
    parent_file.write_text("no child directories", encoding="utf-8")
    with pytest.raises(HTTPException) as exc:
        _make_job_tempdir("insta-thread-asset-", str(parent_file / "scratch"))
    assert exc.value.status_code == 503
