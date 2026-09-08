#!/usr/bin/env bash
set -Eeuo pipefail
trap 'rc=$?; echo "Production update failed at line $LINENO: $BASH_COMMAND (exit $rc)" >&2; exit $rc' ERR

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo 'Run with sudo/root.' >&2
  exit 1
fi

cd "$(dirname "$0")/.."
exec 9>"${TMPDIR:-/tmp}/insta-thread-update.lock"
flock -n 9 || { echo 'Another insta-thread update is already running.' >&2; exit 1; }

for cmd in git docker curl flock; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "$cmd is required." >&2; exit 1; }
done
docker compose version >/dev/null 2>&1 || { echo 'Docker Compose plugin is required.' >&2; exit 1; }

ensure_local_health() {
  if curl -fsS --max-time 3 http://127.0.0.1:8080/health >/dev/null 2>&1; then
    return 0
  fi
  docker compose up -d web api bgutil-provider
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 http://127.0.0.1:8080/health >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

ensure_tunnel_if_configured() {
  if [[ -f .env ]] && grep -q '^CLOUDFLARE_TUNNEL_TOKEN=..' .env && ! grep -q 'replace-with-cloudflare' .env; then
    if ! docker compose ps --status running cloudflared 2>/dev/null | grep -q cloudflared; then
      docker compose --profile tunnel up -d cloudflared
    fi
  fi
}

previous="$(git rev-parse HEAD)"
git fetch --prune origin production
target="$(git rev-parse origin/production)"

if [[ "$previous" == "$target" ]]; then
  ensure_local_health
  ensure_tunnel_if_configured
  echo "Already on tested production SHA $target; local services are healthy."
  exit 0
fi

echo "Updating $previous -> tested production $target"
git checkout --detach "$target"

rollback() {
  trap - ERR
  echo "Rolling back source and containers to $previous" >&2
  git checkout --detach "$previous" || true
  docker compose build web api || true
  docker compose up -d web api bgutil-provider || true
}
trap rollback ERR

docker compose build --pull web api
docker compose up -d web api bgutil-provider
ensure_local_health

# Refresh only this project's unit files; do not touch unrelated Cloudflare services.
install -m 0644 ops/systemd/insta-thread-stack.service /etc/systemd/system/insta-thread-stack.service
install -m 0644 ops/systemd/insta-thread-tunnel.service /etc/systemd/system/insta-thread-tunnel.service
install -m 0644 ops/systemd/insta-thread-update.service /etc/systemd/system/insta-thread-update.service
install -m 0644 ops/systemd/insta-thread-update.timer /etc/systemd/system/insta-thread-update.timer
systemctl daemon-reload

ensure_tunnel_if_configured
mkdir -p data
printf '%s\n' "$target" > data/deployed-sha
trap - ERR

echo "Production update healthy: $target"
