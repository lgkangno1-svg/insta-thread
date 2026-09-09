#!/usr/bin/env bash
set -euo pipefail

HOST="${INDEXNOW_HOST:-download.avocadoss.co.kr}"
KEY="${INDEXNOW_KEY:-082e02e43563db3a3e7e29e6bcf04aa3}"
KEY_LOCATION="https://${HOST}/${KEY}.txt"
ENDPOINT="${INDEXNOW_ENDPOINT:-https://api.indexnow.org/indexnow}"

urls=(
  "https://${HOST}/"
  "https://${HOST}/youtube-downloader"
  "https://${HOST}/instagram-reels-downloader"
  "https://${HOST}/threads-downloader"
  "https://${HOST}/douyin-downloader"
  "https://${HOST}/xiaohongshu-downloader"
  "https://${HOST}/faq"
  "https://${HOST}/privacy"
  "https://${HOST}/terms"
  "https://${HOST}/copyright"
)

printf -v url_json '"%s",' "${urls[@]}"
url_json="[${url_json%,}]"
payload=$(printf '{"host":"%s","key":"%s","keyLocation":"%s","urlList":%s}' "$HOST" "$KEY" "$KEY_LOCATION" "$url_json")

status=$(curl --silent --show-error --output /tmp/indexnow-response.txt --write-out '%{http_code}' \
  --request POST "$ENDPOINT" \
  --header 'Content-Type: application/json; charset=utf-8' \
  --data "$payload")

case "$status" in
  200|202) echo "IndexNow submission accepted (HTTP $status)." ;;
  *)
    echo "IndexNow submission failed (HTTP $status)." >&2
    cat /tmp/indexnow-response.txt >&2 || true
    exit 1
    ;;
esac
