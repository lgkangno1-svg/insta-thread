#!/usr/bin/env bash
set -Eeuo pipefail
trap 'rc=$?; echo "Production update failed at line $LINENO: $BASH_COMMAND (exit $rc)" >&2; exit $rc' ERR

cd "$(dirname "$0")/.."
exec 9>"${TMPDIR:-/tmp}/insta-thread-update.lock"
flock -n 9 || { echo 'Another insta-thread update is already running.' >&2; exit 1; }

for cmd in git docker curl flock; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "$cmd is required." >&2; exit 1; }
done
docker compose version >/dev/null 2>&1 || { echo 'Docker Compose plugin is required.' >&2; exit 1; }
docker ps >/dev/null 2>&1 || { echo 'Current user cannot access the Docker daemon.' >&2; exit 1; }

read_bind_port() {
  local port='8080'
  if [[ -f .env ]]; then
    local configured
    configured="$(sed -n 's/^WEB_BIND_PORT=//p' .env | tail -n 1 | tr -d '[:space:]')"
    [[ -n "$configured" ]] && port="$configured"
  fi
  [[ "$port" =~ ^[0-9]+$ ]] && (( port >= 1024 && port <= 65535 )) || {
    echo "Invalid WEB_BIND_PORT: $port" >&2
    return 1
  }
  printf '%s' "$port"
}

health_url() {
  printf 'http://127.0.0.1:%s/health' "$(read_bind_port)"
}

ensure_local_health() {
  local url
  url="$(health_url)"
  if curl -fsS --max-time 3 "$url" >/dev/null 2>&1; then
    return 0
  fi
  docker compose up -d web api bgutil-provider
  for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then
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

refresh_systemd_units_if_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo 'Non-root deployment: system-level unit refresh skipped.'
    return 0
  fi
  install -m 0644 ops/systemd/insta-thread-stack.service /etc/systemd/system/insta-thread-stack.service
  install -m 0644 ops/systemd/insta-thread-tunnel.service /etc/systemd/system/insta-thread-tunnel.service
  install -m 0644 ops/systemd/insta-thread-update.service /etc/systemd/system/insta-thread-update.service
  install -m 0644 ops/systemd/insta-thread-update.timer /etc/systemd/system/insta-thread-update.timer
  systemctl daemon-reload
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
refresh_systemd_units_if_root
ensure_tunnel_if_configured
mkdir -p data
printf '%s\n' "$target" > data/deployed-sha
trap - ERR

echo "Production update healthy: $target"
