from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
from starlette.responses import FileResponse

from .jobs import store
from .models import AnalyzeRequest, AnalyzeResponse, DownloadRequest, HealthResponse
from .services import downloader

app = FastAPI(
    title="insta-thread API",
    version="0.3.0",
    description="Unified analyzer/downloader for public media from five supported platforms.",
)

origins = [x.strip() for x in os.getenv(
    "CORS_ORIGINS",
    "http://localhost,http://localhost:8080,https://download.avocadoss.co.kr",
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze_media(payload: AnalyzeRequest) -> AnalyzeResponse:
    return downloader.analyze(payload.url)


@app.post("/api/v1/jobs")
def create_job(payload: DownloadRequest):
    job = store.create(payload.url, payload.asset_id)
    return {"id": job.id, "status": job.status}


@app.get("/api/v1/jobs/{job_id}")
def get_job(job_id: str):
    job = store.get(job_id)
    result = {"id": job.id, "status": job.status}
    if job.status == "ready":
        result["download_url"] = f"/api/v1/jobs/{job.id}/file"
    if job.status == "error":
        result["error"] = job.error or "Download preparation failed"
    return result


@app.get("/api/v1/jobs/{job_id}/file")
def get_job_file(job_id: str):
    job = store.get(job_id)
    if job.status != "ready" or not job.path or not job.path.is_file():
        raise HTTPException(status_code=409, detail="Download file is not ready")
    return FileResponse(
        job.path,
        filename=job.path.name,
        media_type="application/octet-stream",
        background=BackgroundTask(store.consume, job.id),
    )


# Direct API endpoint remains useful for local/debug clients. Public browser UI uses
# background jobs so Cloudflare never waits >125 seconds for the first response byte.
@app.post("/api/v1/download")
def download_media(payload: DownloadRequest):
    return downloader.download(payload.url, payload.asset_id)
