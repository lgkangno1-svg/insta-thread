#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine + Compose plugin first." >&2
  exit 1
fi

mkdir -p data/tmp
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env. Add CLOUDFLARE_TUNNEL_TOKEN before enabling the public tunnel." >&2
fi

docker compose build --pull
docker compose up -d web api bgutil-provider

if grep -q '^CLOUDFLARE_TUNNEL_TOKEN=..' .env && ! grep -q 'replace-with-cloudflare' .env; then
  docker compose --profile tunnel up -d cloudflared
  echo "Cloudflare Tunnel container started."
else
  echo "Tunnel token not configured; local site: http://127.0.0.1:8080"
fi

docker compose ps
