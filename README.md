# insta-thread

Unified public-media utility for **YouTube, Instagram Reels, Xiaohongshu (小红书), Threads, and Douyin (抖音)**.

## Final product scope

| Platform | Video | Selectable thumbnail / cover | Engine |
|---|---:|---:|---|
| YouTube | ✅ | — | yt-dlp + Node 22 EJS + FFmpeg + optional PO-token provider |
| Instagram Reels | ✅ | ✅ | yt-dlp |
| Xiaohongshu | ✅ | — | yt-dlp XiaoHongShu extractor |
| Threads | ✅ | ✅ | dedicated target-post parser using crawler-rendered public JSON |
| Douyin | ✅ | ✅ | yt-dlp Douyin/TikTok extractor family |

Only supported **public, non-DRM** media is in scope. The service does not implement private-account bypasses or DRM circumvention.

## Production URL plan

Canonical host:

- `https://download.avocadoss.co.kr`

SEO/platform pages:

- `/youtube-downloader`
- `/instagram-reels-downloader`
- `/threads-downloader`
- `/douyin-downloader`
- `/xiaohongshu-downloader`

Alias hostnames redirect with HTTP 301 to the canonical platform pages:

- `youtube.avocadoss.co.kr`
- `insta.avocadoss.co.kr`
- `thread.avocadoss.co.kr`
- `douyin.avocadoss.co.kr`
- `xiaohongshu.avocadoss.co.kr`

This avoids duplicating the same site across multiple independently indexed hostnames while still making the short subdomains usable for marketing/share links.

## Architecture

```text
Browser
  -> Cloudflare DNS / SSL / WAF
  -> Cloudflare Tunnel
  -> mini PC Docker network
       -> Nginx static SEO frontend
       -> FastAPI API
          -> background job queue (2 workers by default)
          -> yt-dlp / FFmpeg
          -> dedicated Threads parser
          -> bgutil YouTube PO-token provider (private Docker network)
```

Large media preparation runs as a background job. The browser polls status and requests the file only after it is ready. This avoids Cloudflare's normal origin first-byte timeout for long-running jobs.

## Repository layout

- `web/` — Nginx + static responsive SEO frontend
- `backend/` — FastAPI extraction, jobs and download delivery
- `cloudflare/` — tunnel configuration example
- `scripts/` — mini-PC deploy/update scripts
- `docs/RESEARCH.md` — GitHub/Hugging Face research
- `docs/MONETIZATION.md` — policy-aware monetization plan
- `docs/DEPLOYMENT.md` — Cloudflare + mini-PC production setup
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

### Full Docker stack

```bash
cp .env.example .env
mkdir -p data/tmp
docker compose build
docker compose up -d web api bgutil-provider
```

Open:

- `http://127.0.0.1:8080/`
- `http://127.0.0.1:8080/health`

## mini-PC deployment

```bash
cp .env.example .env
# Add a Cloudflare Tunnel token to .env
./scripts/deploy-minipc.sh
```

See `docs/DEPLOYMENT.md` for the six Cloudflare published hostnames.

## Monetization

The direct sponsor/affiliate gate is implemented but **disabled by default** in:

`web/public/monetization.js`

It supports a clearly labeled sponsor message and a 3–5 second view delay. The sponsor link is optional; users are never required to click an advertisement.

Do not automatically enable AdSense on the downloader flow. Google Publisher Policies specifically flag pages that enable downloading streaming video when prohibited by the provider, so this category needs a separate policy/legal assessment. See `docs/MONETIZATION.md`.

## Reliability notes

- yt-dlp must be updated regularly because social platform extractors change frequently.
- YouTube's current EJS flow requires a supported JavaScript runtime; the API image uses Node.js 22.
- The Docker stack keeps the bgutil PO-token provider on the private Docker network.
- Threads public crawler rendering is inherently fragile and should be regression-tested after Meta layout changes.
- An optional owner-controlled `YTDLP_COOKIE_FILE` hook exists for public content that later requires a dedicated logged-in service session. Do not commit cookies to Git.

## Current QA

`pytest`: **14 passed** in the build environment.

The build environment used for this project does not expose the user's Cloudflare account or a Docker daemon, so account-side Tunnel/DNS creation and a production container launch must be performed from the connected mini PC / Cloudflare account.
