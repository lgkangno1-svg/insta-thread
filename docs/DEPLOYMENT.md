# Production deployment: rootless miniPC + Cloudflare Tunnel

The live service uses one isolated rootless runtime on the miniPC and one dedicated Cloudflare Tunnel. Do **not** restart or reconfigure unrelated AVOCADOSS tunnels.

## Production flow

```text
main push
  -> GitHub Actions CI
     -> backend tests
     -> frontend/SEO/static checks
     -> Docker reference build
  -> Promote production
     -> production branch points at the tested SHA only
  -> self-hosted miniPC watchdog (lgkangno1-svg/korea-concierge-ci)
     -> fetch production into services/insta-thread/repo
     -> reset services/insta-thread/app to the same production SHA
     -> keep isolated config/cookies/runtime data outside the app clone
     -> restart/recover the app only when necessary
     -> verify local health + public health + design assets
  -> dedicated Cloudflare Tunnel
  -> Live Browser QA waits for exact /build.txt SHA and tests the public site
```

The Docker Compose/systemd files in this repository are retained as a reproducible reference deployment and CI build target. They are **not the current live miniPC runtime**.

## Hostnames

Canonical:

- `download.avocadoss.co.kr`

Aliases redirect to canonical platform pages:

- `youtube.avocadoss.co.kr` -> `/youtube-downloader`
- `insta.avocadoss.co.kr` -> `/instagram-reels-downloader`
- `thread.avocadoss.co.kr` -> `/threads-downloader`
- `douyin.avocadoss.co.kr` -> `/douyin-downloader`
- `xiaohongshu.avocadoss.co.kr` -> `/xiaohongshu-downloader`

FastAPI performs the alias redirects in rootless mode. Nginx performs equivalent redirects in the Docker reference deployment.

## miniPC runtime layout

The self-hosted runner service home contains an isolated downloader directory:

```text
$HOME/services/insta-thread/
  repo/      # production source mirror used by the watchdog
  app/       # actual rootless runtime clone; kept at the same production SHA
  config/    # owner-controlled runtime config/cookie material; never committed
  ...        # PID/log/runtime files managed by the watchdog scripts
```

`repo` and `app` must always converge to the same promoted `production` SHA. A Git pull into `repo` alone is **not** a completed deployment.

The live application serves API + static web from FastAPI with `SERVE_WEB=true`. The current rootless origin is loopback-only; Cloudflare Tunnel is the intended public ingress.

## Deployment observability

`GET /build.txt` is the deployment contract.

- Docker/Nginx mode returns the updater's deployed SHA marker.
- Rootless FastAPI mode returns `BUILD_SHA` when configured, otherwise the runtime Git HEAD.
- Responses are `no-store` and `noindex`.

Live Browser QA waits until `/build.txt` exactly matches the promoted production SHA before testing the UI. A healthy page on the wrong SHA must not count as a successful deployment.

## Watchdog responsibilities

The miniPC watchdog must:

1. fetch the `production` branch;
2. reset both `repo` and the actual `app` clone to the same production SHA;
3. preserve external config, cookies, logs and temporary runtime state;
4. ensure the rootless app process is alive;
5. ensure the dedicated Cloudflare Tunnel process is alive;
6. verify local `/health`;
7. verify public HTTP 200 responses and required design assets;
8. fail instead of silently claiming success when any required check fails.

The watchdog is intentionally separate from this application's GitHub-hosted CI because it executes on the miniPC self-hosted runner.

## Public verification

Minimum release checks:

```text
/health        -> HTTP 200
/build.txt     -> exact promoted production SHA
/              -> canonical homepage
/styles.css    -> HTTP 200
/stitch.css    -> HTTP 200
```

Live Browser QA additionally verifies:

- desktop and mobile rendering;
- canonical homepage title and primary input/button;
- unsupported-URL error handling;
- all five platform pages;
- all five alias redirects;
- Stitch stylesheet network loading;
- browser console/page errors;
- screenshot/evidence artifact upload.

Periodic real-link E2E verification should separately exercise `Analyze -> background job -> temporary file delivery` for currently available public samples. Real platform URLs are not hard-coded as permanent correctness fixtures because providers can remove, expire, region-gate or change them independently of this service.

## Runtime secrets and config

Never commit:

- `DOWNLOAD_TOKEN_SECRET`;
- Cloudflare Tunnel/API credentials;
- cookies or browser/session data;
- payout/affiliate credentials.

Important application defaults:

```dotenv
DOWNLOAD_TOKEN_SECRET=<long-random-secret>
ANALYSIS_TOKEN_TTL_SECONDS=900
SPONSOR_GATE_ENABLED=false
SPONSOR_GATE_SECONDS=4
MAX_JOBS=100
MAX_MEDIA_MB=750
MIN_FREE_GB=5
JOB_TTL_SECONDS=1800
READY_JOB_TTL_SECONDS=600
ERROR_JOB_TTL_SECONDS=120
```

The public download flow has one supported execution path: signed analysis ticket -> background job -> temporary file response. There is no separate synchronous debug download endpoint.

## Docker reference deployment

For local/recovery testing on a host with Docker:

```bash
cp .env.example .env
mkdir -p data/tmp data/metrics
docker compose build
docker compose up -d web api bgutil-provider
curl -fsS http://127.0.0.1:8080/health
```

Enable the Compose Cloudflare Tunnel profile only with a dedicated valid token. Do not use broad process-kill or Docker cleanup commands on a multi-service miniPC.

## Rollback rule

Rollback is SHA-based. If a promoted revision fails local/public health, restore the last known-good promoted SHA and restart only this service. Do not modify unrelated Cloudflare connectors or AVOCADOSS services while diagnosing this downloader.
