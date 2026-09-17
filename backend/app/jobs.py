from __future__ import annotations

import logging
import os
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import HTTPException

from .platforms.router import extract_supported_url
from .security import verify_analysis_token
from .services import downloader


logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass
class Job:
    id: str
    url: str
    asset_id: str
    status: str = "queued"
    updated_at: float = field(default_factory=time.time)
    path: Path | None = None
    tmpdir: str | None = None
    error: str | None = None


class JobStore:
    def __init__(self) -> None:
        workers = max(1, min(_env_int("DOWNLOAD_WORKERS", 2), 4))
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="media-job")
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self.ttl = max(300, _env_int("JOB_TTL_SECONDS", 1800))
        self.ready_ttl = max(60, min(_env_int("READY_JOB_TTL_SECONDS", 600), self.ttl))
        self.error_ttl = max(30, min(_env_int("ERROR_JOB_TTL_SECONDS", 120), self.ttl))
        self.max_jobs = max(10, min(_env_int("MAX_JOBS", 100), 500))
        min_free_gb = _env_float("MIN_FREE_GB", 5.0)
        self.min_free_bytes = int(max(1.0, min(min_free_gb, 100.0)) * 1024**3)
        self.tmp_root = os.getenv("MEDIA_TMP_DIR") or None
        if self.tmp_root:
            Path(self.tmp_root).mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._sweep_loop, name="media-job-sweeper", daemon=True).start()

    def _sweep_loop(self) -> None:
        while True:
            time.sleep(60)
            try:
                self.cleanup()
            except Exception:
                logger.exception("Background job cleanup failed")

    def _job_ttl(self, job: Job) -> int:
        if job.status == "ready":
            return self.ready_ttl
        if job.status == "error":
            return self.error_ttl
        return self.ttl

    def cleanup(self) -> None:
        now = time.time()
        stale: list[Job] = []
        with self.lock:
            for key, job in list(self.jobs.items()):
                if job.updated_at < now - self._job_ttl(job):
                    stale.append(job)
                    self.jobs.pop(key, None)
        for job in stale:
            if job.tmpdir:
                shutil.rmtree(job.tmpdir, ignore_errors=True)

    def _assert_disk_capacity(self) -> None:
        root = self.tmp_root or "/tmp"
        try:
            free = shutil.disk_usage(root).free
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Download storage is unavailable") from exc
        if free < self.min_free_bytes:
            raise HTTPException(status_code=507, detail="Download storage is temporarily full")

    def create(self, url: str, asset_id: str, analysis_token: str) -> Job:
        self.cleanup()
        normalized_url = extract_supported_url(url)
        downloader.validate_asset_id(normalized_url, asset_id)
        verify_analysis_token(analysis_token, normalized_url, asset_id)
        self._assert_disk_capacity()
        with self.lock:
            if len(self.jobs) >= self.max_jobs:
                raise HTTPException(status_code=503, detail="Download queue is full; try again shortly")
            job = Job(id=uuid.uuid4().hex, url=normalized_url, asset_id=asset_id)
            self.jobs[job.id] = job
        self.executor.submit(self._run, job.id)
        return job

    def _run(self, job_id: str) -> None:
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return
            job.status = "processing"
            job.updated_at = time.time()
        try:
            self._assert_disk_capacity()
            path, tmpdir = downloader.prepare(job.url, job.asset_id, tmp_root=self.tmp_root)
            with self.lock:
                current = self.jobs.get(job_id)
                if not current:
                    shutil.rmtree(tmpdir, ignore_errors=True)
                    return
                current.path = path
                current.tmpdir = tmpdir
                current.status = "ready"
                current.updated_at = time.time()
        except HTTPException as exc:
            detail = str(exc.detail)[:1000]
            with self.lock:
                current = self.jobs.get(job_id)
                if current:
                    current.error = detail
                    current.status = "error"
                    current.updated_at = time.time()
        except Exception:
            logger.exception("Unexpected download job failure", extra={"job_id": job_id})
            with self.lock:
                current = self.jobs.get(job_id)
                if current:
                    current.error = "Download preparation failed"
                    current.status = "error"
                    current.updated_at = time.time()

    def get(self, job_id: str) -> Job:
        self.cleanup()
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Download job not found or expired")
            return job

    def consume(self, job_id: str) -> None:
        with self.lock:
            job = self.jobs.pop(job_id, None)
        if job and job.tmpdir:
            shutil.rmtree(job.tmpdir, ignore_errors=True)


store = JobStore()
