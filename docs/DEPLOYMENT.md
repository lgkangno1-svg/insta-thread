# Production deployment: miniPC + Cloudflare Tunnel

Production is designed around one dedicated miniPC stack and one dedicated remotely managed Cloudflare Tunnel. Do **not** reuse or restart unrelated tunnels from other AVOCADOSS services.

## Production flow

```text
main push
  -> GitHub Actions CI
     -> backend tests
     -> frontend/SEO/static checks
     -> Docker production build
  -> Promote production workflow
     -> production branch points at the tested SHA only
  -> miniPC systemd timer
     -> fetch production
     -> build + deploy
     -> local health check
     -> rollback on failure
  -> dedicated avocadoss-download Cloudflare Tunnel
```

## Hostnames

Canonical:

- `download.avocadoss.co.kr`

Aliases, all served by the same Tunnel and redirected by Nginx to canonical platform paths:

- `youtube.avocadoss.co.kr`
- `insta.avocadoss.co.kr`
- `thread.avocadoss.co.kr`
- `douyin.avocadoss.co.kr`
- `xiaohongshu.avocadoss.co.kr`

The Tunnel ingress target is `http://web:80` because cloudflared runs inside this project's Docker Compose network.

## 1. miniPC prerequisites

Required:

- Linux + systemd
- Git
- rsync
- curl
- Docker Engine
- Docker Compose plugin (`docker compose`)
- outbound Internet access

No public inbound port is required. Nginx is bound only to `127.0.0.1:8080` on the host.

## 2. Install the tested production checkout

Use any temporary checkout of the repository to invoke the installer:

```bash
git clone https://github.com/lgkangno1-svg/insta-thread.git ~/insta-thread-bootstrap
cd ~/insta-thread-bootstrap
sudo bash scripts/install-minipc-systemd.sh
```

The installer:

1. clones/resets `/opt/insta-thread` to the CI-promoted `production` branch;
2. preserves `/opt/insta-thread/.env` and `data/`;
3. generates `DOWNLOAD_TOKEN_SECRET` once if it is blank;
4. installs only the `insta-thread-*` systemd units;
5. starts the local Docker stack;
6. requires `http://127.0.0.1:8080/health` to pass;
7. enables the production update timer.

The public Tunnel remains disabled until a real Tunnel token is configured.

## 3. Provision Cloudflare automatically with the API

The repository includes `scripts/provision-cloudflare.py`. It is intentionally conservative: it only creates/reuses a Tunnel named `avocadoss-download`, refuses unrelated ingress rules by default, and refuses to overwrite non-CNAME DNS records unless an explicit force variable is set.

Create a scoped Cloudflare API token with:

- Account -> Cloudflare Tunnel -> Edit
- Zone (`avocadoss.co.kr`) -> DNS -> Edit
- Zone (`avocadoss.co.kr`) -> Zone -> Read, for automatic zone/account discovery

Then on the miniPC:

```bash
cd /opt/insta-thread
read -rsp 'Cloudflare API token: ' CLOUDFLARE_API_TOKEN; echo
export CLOUDFLARE_API_TOKEN
sudo --preserve-env=CLOUDFLARE_API_TOKEN python3 scripts/provision-cloudflare.py
unset CLOUDFLARE_API_TOKEN
```

The provisioner will:

1. discover the active `avocadoss.co.kr` zone and account;
2. create or reuse only the `avocadoss-download` Tunnel;
3. set all six ingress hostnames to `http://web:80` plus a final `http_status:404` catch-all;
4. create/update proxied CNAME records to `<TUNNEL_UUID>.cfargotunnel.com`;
5. retrieve the remotely managed Tunnel token;
6. write the Tunnel token into `/opt/insta-thread/.env` without printing it.

## 4. Start only this project's Tunnel

```bash
sudo systemctl enable --now insta-thread-tunnel.service
```

Do not use commands such as `pkill cloudflared`, `systemctl restart cloudflared*`, or bulk Docker cleanup. Other AVOCADOSS services may have unrelated Tunnel connectors.

## 5. Verify local and public health

Local first:

```bash
curl -fsS --max-time 5 http://127.0.0.1:8080/health
```

Then public samples:

```bash
cd /opt/insta-thread
sudo PUBLIC_SAMPLES=12 bash scripts/smoke.sh
```

Treat sampled Cloudflare `1033`, `530`, and origin `502` responses as a deployment failure. Diagnose local origin health before touching the Tunnel.

## 6. Automatic tested updates

`insta-thread-update.timer` checks every ~10 minutes. It fetches **only** the `production` branch, which is moved only after GitHub CI succeeds.

Manual update/check:

```bash
sudo systemctl start insta-thread-update.service
sudo journalctl -u insta-thread-update.service -n 100 --no-pager
```

The updater:

- serializes deployments with `flock`;
- builds before switching traffic;
- checks local health for up to 60 seconds;
- rolls source + containers back to the previous SHA on failure;
- does not restart a healthy Tunnel for ordinary app deploys;
- refreshes only `insta-thread-*` systemd unit files.

## 7. Production `.env`

Important defaults:

```dotenv
DOWNLOAD_TOKEN_SECRET=<generated-once-by-installer>
ANALYSIS_TOKEN_TTL_SECONDS=900
SPONSOR_GATE_ENABLED=false
SPONSOR_GATE_SECONDS=4
MAX_JOBS=100
MAX_MEDIA_MB=750
MIN_FREE_GB=5
JOB_TTL_SECONDS=1800
READY_JOB_TTL_SECONDS=600
ERROR_JOB_TTL_SECONDS=120
ENABLE_DIRECT_DOWNLOAD=false
```

`DOWNLOAD_TOKEN_SECRET`, the Cloudflare API token, Tunnel token, cookies, and session data must never be committed.

## 8. Public-download architecture notes

- Long yt-dlp/FFmpeg work runs in background jobs; Cloudflare does not wait for the full extraction request.
- Prepared files expire quickly and are removed after delivery.
- New jobs stop when disk free space falls below the configured reserve.
- Download jobs require a signed analysis ticket bound to the exact URL and asset choice.
- The synchronous debug download endpoint is disabled by default.
- Cloudflare is the only intended public ingress; the origin HTTP port stays loopback-only.
