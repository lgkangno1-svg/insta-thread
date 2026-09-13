# insta-thread

Unified public-media utility for **YouTube, Instagram Reels, Xiaohongshu (小红书), Threads, and Douyin (抖音)**.

## Product scope

| Platform | Video | Images / cover | Engine |
|---|---:|---:|---|
| YouTube | ✅ | — | yt-dlp + Node EJS + FFmpeg + optional PO-token provider |
| Instagram Reels | ✅ | ✅ | dedicated anonymous public-media adapter |
| Xiaohongshu | ✅ | ✅ | dedicated public-note parser + CDN resolver |
| Threads | ✅ | ✅ | dedicated public target-post parser |
| Douyin | ✅ | ✅ | yt-dlp Douyin/TikTok extractor family |

Only supported **public, non-DRM** media is in scope. The service does not implement private-account, paywall, login, or DRM bypasses.

## Production

Canonical host:

- `https://download.avocadoss.co.kr`

SEO/platform pages:

- `/youtube-downloader`
- `/instagram-reels-downloader`
- `/threads-downloader`
- `/douyin-downloader`
- `/xiaohongshu-downloader`

Alias hosts redirect with HTTP 301 to the matching canonical platform page:

- `youtube.avocadoss.co.kr`
- `insta.avocadoss.co.kr`
- `thread.avocadoss.co.kr`
- `douyin.avocadoss.co.kr`
- `xiaohongshu.avocadoss.co.kr`

## Current production architecture

Production currently runs as an isolated **rootless miniPC runtime** managed by the self-hosted GitHub runner in `lgkangno1-svg/korea-concierge-ci`.

```text
Browser
  -> Cloudflare DNS / SSL / Tunnel
  -> miniPC rootless service
       -> FastAPI
          -> static SEO frontend (SERVE_WEB)
          -> background job queue
          -> yt-dlp / FFmpeg
          -> dedicated Instagram / Threads / Xiaohongshu adapters

main push
  -> GitHub Actions CI
  -> Promote production
  -> production branch = tested SHA
  -> miniPC watchdog
       -> sync repo + runtime app clone to production SHA
       -> restart app if needed
       -> local/public health checks
  -> Live Browser QA
       -> exact /build.txt SHA check
       -> desktop/mobile UI + aliases + platform pages
```

The repository also retains a Docker Compose reference deployment for reproducible CI/build validation and alternate hosts. Docker is **not** the current live miniPC runtime.

Large media preparation always runs as a background job. The browser polls the job and fetches the temporary file only after it is ready, avoiding long Cloudflare origin waits.

## Repository layout

- `web/` — static responsive SEO frontend + Nginx Docker reference config
- `backend/` — FastAPI extraction, job queue and temporary download delivery
- `cloudflare/` — tunnel configuration examples
- `scripts/` — Docker/systemd reference deployment and provisioning utilities
- `docs/DEPLOYMENT.md` — current production topology and operations notes
- `docs/MONETIZATION.md` — policy-aware monetization plan
- `docs/LEGAL.md` — launch/legal checklist
- `BUILD_SPEC.md` — functional acceptance scope

## Local development

### API tests

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

### Docker reference stack

```bash
cp .env.example .env
mkdir -p data/tmp
docker compose build
docker compose up -d web api bgutil-provider
```

Open:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/health`

### Rootless web mode

FastAPI can serve the static frontend directly when `SERVE_WEB=true`; production uses this mode. `/build.txt` exposes the exact runtime Git SHA so deployment QA can fail closed on stale code.

## Monetization

The sponsor/affiliate presentation layer exists but is **disabled by default**. Advertising must remain separate from the download action; users are never required to click an ad to unlock a file. See `docs/MONETIZATION.md`.

## Reliability

- Social platform extractors change frequently; keep yt-dlp and platform adapters regression-tested.
- YouTube's EJS flow requires a supported JavaScript runtime.
- Threads/Instagram/Xiaohongshu anonymous public endpoints can change without notice.
- An owner-controlled `YTDLP_COOKIE_FILE` may be used only for an isolated permitted public-session workflow; never commit cookies or credentials.
- `main` is validated by backend tests, static/SEO checks and Docker build before promotion.
- `production` is the only SHA the miniPC watchdog deploys.
- scheduled Live Browser QA verifies the exact production SHA, desktop/mobile UI, platform pages, aliases and basic form behavior.

## Release status

V1 is production-ready when all of the following are green:

1. CI backend/static/Docker jobs.
2. `main` and `production` point to the promoted tested SHA.
3. miniPC watchdog reports healthy runtime and tunnel.
4. public `/health` and `/build.txt` respond correctly.
5. Live Browser QA passes.
6. periodic real-link E2E samples continue to analyze and deliver a temporary file without bypassing access controls.
