#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose build --pull
docker compose up -d web api bgutil-provider
if [[ -f .env ]] && grep -q '^CLOUDFLARE_TUNNEL_TOKEN=..' .env && ! grep -q 'replace-with-cloudflare' .env; then
  docker compose --profile tunnel up -d cloudflared
fi
docker compose ps
