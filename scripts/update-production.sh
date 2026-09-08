#!/usr/bin/env bash
set -Eeuo pipefail
trap 'rc=$?; echo "Production update failed at line $LINENO: $BASH_COMMAND (exit $rc)" >&2; exit $rc' ERR

cd "$(dirname "$0")/.."
exec 9>"${TMPDIR:-/tmp}/insta-thread-update.lock"
flock -n 9 || { echo 'Another insta-thread update is already running.' >&2; exit 1; }

command -v git >/dev/null 2>&1 || { echo 'git is required.' >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo 'Docker is required.' >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo 'Docker Compose plugin is required.' >&2; exit 1; }

previous="$(git rev-parse HEAD)"
git fetch --prune origin production
target="$(git rev-parse origin/production)"

if [[ "$previous" == "$target" ]]; then
  echo "Already on tested production SHA $target"
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

healthy=0
for _ in $(seq 1 60); do
  if curl -fsS --max-time 2 http://127.0.0.1:8080/health >/dev/null 2>&1; then
    healthy=1
    break
  fi
  sleep 1
done
[[ "$healthy" -eq 1 ]] || { echo 'Local health check failed after update.' >&2; false; }

# A running dedicated tunnel does not need to be restarted for ordinary app deploys.
# If it is container-managed and stopped, start only this project's connector.
if [[ -f .env ]] && grep -q '^CLOUDFLARE_TUNNEL_TOKEN=..' .env && ! grep -q 'replace-with-cloudflare' .env; then
  if ! docker compose ps --status running cloudflared 2>/dev/null | grep -q cloudflared; then
    docker compose --profile tunnel up -d cloudflared
  fi
fi

mkdir -p data
printf '%s\n' "$target" > data/deployed-sha
trap - ERR

echo "Production update healthy: $target"
