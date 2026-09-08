# Cloudflare / mini-PC production runbook

## Isolation rule

This service must use its own Cloudflare Tunnel (suggested name `avocadoss-download`). Never reuse, stop, restart, or edit the existing Korea Concierge or n8n tunnel as part of this deployment.

The user's existing mini-PC history showed why this matters: a healthy unrelated Docker tunnel can coexist with a failed application tunnel, and treating them as the same connector can cause destructive repair attempts.

## Expected local origin

- web origin: `127.0.0.1:8080`
- health: `http://127.0.0.1:8080/health` -> HTTP 200
- API stays inside the Docker network on port 8000
- no router/NAT inbound port forwarding is required

## Dedicated public hostnames

All hostnames point through the same dedicated tunnel to `http://web:80`:

- `download.avocadoss.co.kr`
- `youtube.avocadoss.co.kr`
- `insta.avocadoss.co.kr`
- `thread.avocadoss.co.kr`
- `douyin.avocadoss.co.kr`
- `xiaohongshu.avocadoss.co.kr`

Nginx performs 301 redirects from alias hostnames to canonical platform paths on `download.avocadoss.co.kr`.

## Production verification

Run:

```bash
PUBLIC_SAMPLES=12 ./scripts/smoke.sh
```

Treat every sample as authoritative; do not retry until a request happens to succeed. Any sampled 1033, 530, 502 or non-200 canonical response is a production reliability failure.

Interpretation:

- Cloudflare 1033: no healthy `cloudflared` connector is available for this tunnel.
- Tunnel 502: connector is up but cannot reach the configured origin.
- local 200 + public failure: investigate the dedicated tunnel / Cloudflare route, not the app first.
- local failure: repair `insta-thread-stack.service` / Docker origin before touching Cloudflare.

## Safe restart order

```bash
sudo systemctl restart insta-thread-stack.service
curl -fsS http://127.0.0.1:8080/health
sudo systemctl restart insta-thread-tunnel.service
PUBLIC_SAMPLES=12 ./scripts/smoke.sh
```

Never use broad commands that stop all `cloudflared` or all Docker containers on the mini PC.

## Secrets

Keep `CLOUDFLARE_TUNNEL_TOKEN`, cookies and any future sponsor/API credentials only in `/opt/insta-thread/.env` or an equivalent secret store. Never commit them or print complete token-bearing process commands in CI logs.
