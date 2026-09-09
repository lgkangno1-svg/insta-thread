from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.background import BackgroundTask
from starlette.responses import FileResponse, JSONResponse, RedirectResponse
from starlette.staticfiles import StaticFiles

from .jobs import store
from .models import AnalyzeRequest, AnalyzeResponse, DownloadRequest, HealthResponse
from .security import verify_analysis_token
from .services import downloader

app = FastAPI(
    title="insta-thread API",
    version="0.5.0",
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

# Nginx applies the same limits in the Docker deployment. Keep an application-level
# ceiling as well so the rootless host fallback is not an unthrottled public API.
_rate_lock = threading.Lock()
_rate_windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _rate_class(request: Request) -> tuple[str, int] | None:
    path = request.url.path
    if request.method == "POST" and path == "/api/v1/analyze":
        return "analyze", 20
    if request.method == "POST" and path == "/api/v1/jobs":
        return "job", 12
    if request.method == "GET" and path.startswith("/api/v1/jobs/") and not path.endswith("/file"):
        return "poll", 120
    return None


@app.middleware("http")
async def production_guards(request: Request, call_next):
    host = (request.headers.get("host") or "").split(":", 1)[0].lower()
    aliases = {
        "youtube.avocadoss.co.kr": "https://download.avocadoss.co.kr/youtube-downloader",
        "insta.avocadoss.co.kr": "https://download.avocadoss.co.kr/instagram-reels-downloader",
        "thread.avocadoss.co.kr": "https://download.avocadoss.co.kr/threads-downloader",
        "douyin.avocadoss.co.kr": "https://download.avocadoss.co.kr/douyin-downloader",
        "xiaohongshu.avocadoss.co.kr": "https://download.avocadoss.co.kr/xiaohongshu-downloader",
    }
    if host in aliases:
        return RedirectResponse(aliases[host], status_code=301)

    if os.getenv("APP_RATE_LIMIT", "true").strip().lower() in {"1", "true", "yes", "on"}:
        classified = _rate_class(request)
        if classified:
            bucket, limit = classified
            ip = (request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "unknown")).strip()
            now = time.monotonic()
            key = (bucket, ip[:128])
            with _rate_lock:
                window = _rate_windows[key]
                while window and window[0] <= now - 60:
                    window.popleft()
                if len(window) >= limit:
                    return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429, headers={"Retry-After": "60"})
                window.append(now)

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@app.post("/api/v1/analyze", response_model=AnalyzeResponse)
def analyze_media(payload: AnalyzeRequest) -> AnalyzeResponse:
    return downloader.analyze(payload.url)


@app.post("/api/v1/jobs")
def create_job(payload: DownloadRequest):
    job = store.create(payload.url, payload.asset_id, payload.analysis_token)
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


# Disabled in production by default. The public browser flow must use background jobs
# so Cloudflare never waits on a long extractor/FFmpeg request.
@app.post("/api/v1/download")
def download_media(payload: DownloadRequest):
    enabled = os.getenv("ENABLE_DIRECT_DOWNLOAD", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        raise HTTPException(status_code=404, detail="Direct download endpoint is disabled")
    verify_analysis_token(payload.analysis_token, payload.url, payload.asset_id)
    return downloader.download(payload.url, payload.asset_id)


def _register_rootless_web() -> None:
    if os.getenv("SERVE_WEB", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    default_root = Path(__file__).resolve().parents[2] / "web" / "public"
    web_root = Path(os.getenv("WEB_PUBLIC_DIR", str(default_root))).resolve()
    if not web_root.is_dir():
        raise RuntimeError(f"SERVE_WEB requested but web root does not exist: {web_root}")

    pages = {
        "/": "index.html",
        "/youtube-downloader": "youtube-downloader.html",
        "/instagram-reels-downloader": "instagram-reels-downloader.html",
        "/threads-downloader": "threads-downloader.html",
        "/douyin-downloader": "douyin-downloader.html",
        "/xiaohongshu-downloader": "xiaohongshu-downloader.html",
        "/privacy": "privacy.html",
        "/terms": "terms.html",
        "/copyright": "copyright.html",
        "/faq": "faq.html",
    }

    def make_page(filename: str):
        def serve_page():
            return FileResponse(web_root / filename)
        return serve_page

    for route, filename in pages.items():
        app.add_api_route(route, make_page(filename), methods=["GET"], include_in_schema=False)
    app.mount("/", StaticFiles(directory=str(web_root)), name="web-static")


_register_rootless_web()
