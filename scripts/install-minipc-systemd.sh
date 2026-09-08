#!/usr/bin/env bash
set -Eeuo pipefail
trap 'rc=$?; echo "Install failed at line $LINENO: $BASH_COMMAND (exit $rc)" >&2; exit $rc' ERR

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo 'Run with sudo/root.' >&2
  exit 1
fi

APP_ROOT='/opt/insta-thread'
REPO_URL='https://github.com/lgkangno1-svg/insta-thread.git'

for cmd in git rsync curl docker; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "$cmd is required." >&2; exit 1; }
done
docker compose version >/dev/null 2>&1 || { echo 'Docker Compose plugin is required.' >&2; exit 1; }

# Keep the production checkout itself under /opt so future updates can fast-forward
# to the CI-promoted production branch. Preserve local secrets and temporary data.
mkdir -p "$APP_ROOT"
env_backup=''
if [[ -f "$APP_ROOT/.env" ]]; then
  env_backup="$(mktemp)"
  cp "$APP_ROOT/.env" "$env_backup"
fi

if [[ ! -d "$APP_ROOT/.git" ]]; then
  stage="$(mktemp -d)"
  git clone --depth=1 --branch production "$REPO_URL" "$stage/repo"
  rsync -a --delete --exclude='.env' --exclude='data/' "$stage/repo/" "$APP_ROOT/"
  rm -rf "$stage"
else
  git -C "$APP_ROOT" remote set-url origin "$REPO_URL"
  git -C "$APP_ROOT" fetch --prune origin production
  git -C "$APP_ROOT" checkout -B production origin/production
  git -C "$APP_ROOT" reset --hard origin/production
fi

if [[ -n "$env_backup" && -f "$env_backup" ]]; then
  mv "$env_backup" "$APP_ROOT/.env"
fi

cd "$APP_ROOT"
mkdir -p data/tmp
[[ -f .env ]] || cp .env.example .env

# Create a stable HMAC secret once. Never print it to logs.
if grep -q '^DOWNLOAD_TOKEN_SECRET=$' .env; then
  if command -v openssl >/dev/null 2>&1; then
    generated_secret="$(openssl rand -hex 32)"
  elif command -v python3 >/dev/null 2>&1; then
    generated_secret="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  else
    echo 'openssl or python3 is required to generate DOWNLOAD_TOKEN_SECRET.' >&2
    exit 1
  fi
  sed -i "s/^DOWNLOAD_TOKEN_SECRET=$/DOWNLOAD_TOKEN_SECRET=$generated_secret/" .env
  unset generated_secret
fi
chmod 0600 .env

install -m 0644 ops/systemd/insta-thread-stack.service /etc/systemd/system/insta-thread-stack.service
install -m 0644 ops/systemd/insta-thread-tunnel.service /etc/systemd/system/insta-thread-tunnel.service
if [[ -f ops/systemd/insta-thread-update.service ]]; then
  install -m 0644 ops/systemd/insta-thread-update.service /etc/systemd/system/insta-thread-update.service
fi
if [[ -f ops/systemd/insta-thread-update.timer ]]; then
  install -m 0644 ops/systemd/insta-thread-update.timer /etc/systemd/system/insta-thread-update.timer
fi
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

echo 'Local stack installed from the CI-promoted production branch and is healthy.'
if systemctl is-enabled --quiet insta-thread-tunnel.service; then
  systemctl restart insta-thread-tunnel.service
  echo 'Dedicated Cloudflare tunnel service started.'
else
  echo 'Tunnel remains disabled until CLOUDFLARE_TUNNEL_TOKEN is set in /opt/insta-thread/.env.'
fi

if [[ -f /etc/systemd/system/insta-thread-update.timer ]]; then
  systemctl enable --now insta-thread-update.timer
  echo 'CI-gated production update timer enabled.'
fi
