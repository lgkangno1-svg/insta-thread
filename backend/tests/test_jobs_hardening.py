from app.jobs import Job, _env_float, _env_int, store
from app.services import downloader


def test_malformed_numeric_environment_falls_back(monkeypatch):
    monkeypatch.setenv("DOWNLOAD_WORKERS", "not-a-number")
    monkeypatch.setenv("MIN_FREE_GB", "not-a-number")

    assert _env_int("DOWNLOAD_WORKERS", 2) == 2
    assert _env_float("MIN_FREE_GB", 5.0) == 5.0


def test_unexpected_job_failure_does_not_leak_internal_error(monkeypatch):
    job = Job(id="hardening-test-job", url="https://www.youtube.com/watch?v=dQw4w9WgXcQ", asset_id="video:best")
    with store.lock:
        store.jobs[job.id] = job

    monkeypatch.setattr(store, "_assert_disk_capacity", lambda: None)

    def fail_prepare(*_args, **_kwargs):
        raise RuntimeError("internal path /tmp/private-token should not reach the client")

    monkeypatch.setattr(downloader, "prepare", fail_prepare)

    try:
        store._run(job.id)
        failed = store.get(job.id)
        assert failed.status == "error"
        assert failed.error == "Download preparation failed"
        assert "/tmp/private-token" not in failed.error
    finally:
        store.consume(job.id)
