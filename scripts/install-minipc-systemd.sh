#!/usr/bin/env bash
set -Eeuo pipefail
trap 'rc=$?; echo "Install failed at line $LINENO: $BASH_COMMAND (exit $rc)" >&2; exit $rc' ERR

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo 'Run with sudo/root.' >&2
  exit 1
fi

APP_ROOT='/opt/insta-thread'
SOURCE_DIR="$(cd "$(dirname "$0")/.." && pwd)"

command -v docker >/dev/null 2>&1 || { echo 'Docker is required.' >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo 'Docker Compose plugin is required.' >&2; exit 1; }

if [[ "$SOURCE_DIR" != "$APP_ROOT" ]]; then
  mkdir -p "$APP_ROOT"
  # Preserve production .env if it already exists.
  if [[ -f "$APP_ROOT/.env" ]]; then
    cp "$APP_ROOT/.env" /tmp/insta-thread.env.$$
  fi
  rsync -a --delete --exclude='.git' --exclude='.env' --exclude='data/tmp/*' "$SOURCE_DIR/" "$APP_ROOT/"
  if [[ -f /tmp/insta-thread.env.$$ ]]; then
    mv /tmp/insta-thread.env.$$ "$APP_ROOT/.env"
  fi
fi

cd "$APP_ROOT"
mkdir -p data/tmp
[[ -f .env ]] || cp .env.example .env

install -m 0644 ops/systemd/insta-thread-stack.service /etc/systemd/system/insta-thread-stack.service
install -m 0644 ops/systemd/insta-thread-tunnel.service /etc/systemd/system/insta-thread-tunnel.service
systemctl daemon-reload
systemctl enable insta-thread-stack.service

# Do not start a public tunnel unless a real token is configured.
if grep -q '^CLOUDFLARE_TUNNEL_TOKEN=..' .env && ! grep -q 'replace-with-cloudflare' .env; then
  systemctl enable insta-thread-tunnel.service
else
  systemctl disable insta-thread-tunnel.service >/dev/null 2>&1 || true
fi

systemctl restart insta-thread-stack.service
curl -fsS --max-time 10 http://127.0.0.1:8080/health >/dev/null

echo 'Local stack installed and healthy.'
if systemctl is-enabled --quiet insta-thread-tunnel.service; then
  systemctl restart insta-thread-tunnel.service
  echo 'Dedicated Cloudflare tunnel service started.'
else
  echo 'Tunnel remains disabled until CLOUDFLARE_TUNNEL_TOKEN is set in /opt/insta-thread/.env.'
fi
