#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
echo "[MiniPC CI] Static SEO, AEO, GEO, sitemap and FAQ parity"
"$PYTHON" scripts/check-seo.py
echo "[MiniPC CI] Python modules"
"$PYTHON" -m compileall -q backend/app
"$PYTHON" -m py_compile scripts/smoke-download-e2e.py
echo "[MiniPC CI] Full backend and HEAD-route tests"
"$PYTHON" -m pytest -q backend/tests
echo "[MiniPC CI] Client-side JS and shell syntax"
node --check web/public/app.js
node --check web/public/monetization.js
for script in scripts/*.sh; do bash -n "$script"; done
echo "[MiniPC CI] SEO/design checks completed successfully"
