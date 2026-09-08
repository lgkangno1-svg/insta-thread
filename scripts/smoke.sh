#!/usr/bin/env bash
set -euo pipefail

LOCAL_BASE="${LOCAL_BASE:-http://127.0.0.1:8080}"
PUBLIC_BASE="${PUBLIC_BASE:-https://download.avocadoss.co.kr}"
PUBLIC_SAMPLES="${PUBLIC_SAMPLES:-5}"

probe() {
  local url="$1" expected="$2" code
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 --max-redirs 0 "$url" || true)"
  printf '%-72s %s\n' "$url" "$code"
  [[ "$code" == "$expected" ]]
}

echo '== local origin =='
probe "$LOCAL_BASE/health" 200
probe "$LOCAL_BASE/" 200
probe "$LOCAL_BASE/instagram-reels-downloader" 200
probe "$LOCAL_BASE/threads-downloader" 200
probe "$LOCAL_BASE/douyin-downloader" 200
probe "$LOCAL_BASE/xiaohongshu-downloader" 200
probe "$LOCAL_BASE/youtube-downloader" 200

echo '== public, no-retry samples =='
for i in $(seq 1 "$PUBLIC_SAMPLES"); do
  echo "sample $i/$PUBLIC_SAMPLES"
  probe "$PUBLIC_BASE/health" 200
  probe "$PUBLIC_BASE/" 200
  sleep 1
done

echo 'Smoke checks passed.'
