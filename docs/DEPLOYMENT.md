# Production deployment: avocadoss.co.kr + mini PC + Cloudflare

## Canonical SEO structure

Primary site:

- `https://download.avocadoss.co.kr/`

Canonical platform pages:

- `/youtube-downloader`
- `/instagram-reels-downloader`
- `/threads-downloader`
- `/douyin-downloader`
- `/xiaohongshu-downloader`

Memorable alias hostnames:

- `youtube.avocadoss.co.kr` -> 301 to `/youtube-downloader`
- `insta.avocadoss.co.kr` -> 301 to `/instagram-reels-downloader`
- `thread.avocadoss.co.kr` -> 301 to `/threads-downloader`
- `douyin.avocadoss.co.kr` -> 301 to `/douyin-downloader`
- `xiaohongshu.avocadoss.co.kr` -> 301 to `/xiaohongshu-downloader`

Rationale: Google explicitly says it has no indexing/ranking preference for subdomains versus subdirectories. A single canonical hostname is easier to operate and consolidates internal linking/canonicalization, while the alias subdomains remain useful as memorable entry URLs.

## Origin architecture

`Browser -> Cloudflare -> Cloudflare Tunnel -> mini PC Docker -> Nginx -> FastAPI -> yt-dlp / FFmpeg`

The tunnel is outbound-only, so the mini PC does not need inbound ports exposed to the Internet.

## Cloudflare tunnel routes

Create one remotely-managed tunnel (suggested name: `avocadoss-download`) and publish all six hostnames to the same local service:

- `download.avocadoss.co.kr` -> `http://web:80`
- `youtube.avocadoss.co.kr` -> `http://web:80`
- `insta.avocadoss.co.kr` -> `http://web:80`
- `thread.avocadoss.co.kr` -> `http://web:80`
- `douyin.avocadoss.co.kr` -> `http://web:80`
- `xiaohongshu.avocadoss.co.kr` -> `http://web:80`

Cloudflare can publish multiple hostnames through one tunnel. The Nginx configuration performs the platform alias 301 redirects.

## First mini-PC deployment

```bash
git clone <repository-url> insta-thread
cd insta-thread
cp .env.example .env
# set CLOUDFLARE_TUNNEL_TOKEN in .env
./scripts/deploy-minipc.sh
```

Local health checks:

```bash
curl http://127.0.0.1:8080/health
curl -I http://127.0.0.1:8080/
```

## Why downloads use background jobs

Cloudflare's default origin Proxy Read Timeout is 125 seconds on non-Enterprise plans. Preparing a large YouTube file can exceed that before the first byte is returned. The site therefore creates a background download job, polls its status, and only requests the file after it is ready. This avoids holding a single long request open while yt-dlp and FFmpeg work.

## mini-PC sizing / operations

For an N100-class mini PC:

- start with `DOWNLOAD_WORKERS=2`
- avoid transcoding; use remux/merge paths
- use SSD-backed `./data/tmp`, not RAM tmpfs
- keep a file-size ceiling
- monitor disk free space and outbound bandwidth
- run Docker and cloudflared with restart policies

If traffic grows, move only the API/job workers to a VPS while keeping the same frontend/domain structure.

## Hardened mini-PC service install

The repository includes separate systemd wrappers so this stack and its Cloudflare connector can be managed without touching other services on the same mini PC:

```bash
sudo ./scripts/install-minipc-systemd.sh
```

After the dedicated Cloudflare public hostnames are configured, verify production with no-retry samples:

```bash
PUBLIC_SAMPLES=12 ./scripts/smoke.sh
```

See `docs/CLOUDFLARE_RUNBOOK.md` for failure interpretation and safe restart order.
