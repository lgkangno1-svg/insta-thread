# Threads download failure / LoveThreads REA comparison (2026-10-25)

## Target and scope
- User's failing public link: https://www.threads.com/@moabattem_aa/post/De5wP_IAd2_
- User-facing aliases: `insta.avocadoss.co.kr` redirects to `download.avocadoss.co.kr/instagram-reels-downloader`; the Threads tab runs on the same FastAPI service.
- Live `/build.txt` observed: `0e3b5b910190f055956b431f9c7294b003de3509` (2026-10-25 UTC). This release does NOT include the scratch-directory recovery patch.

## External site, factual evidence and limits
- Used official `rea-agents@6.8.0 analyze-javascript-application` against one publicly served LoveThreads script (`/lovethreads/js/app.min.js?v=2`, 92,085 bytes), not the vendor's server source. REA exited 0; parsed 1/1 scripts, 32,484 AST nodes, 254 static findings and no parse failures.
- Public JavaScript `ksearchvideo()` sends a jQuery AJAX `POST` to `k_url_search` with `{q, t, lang, html}`, then renders response `n.data` in `#search-result`.
- Public HTML declares `k_url_search=https://lovethreads.net/api/ajaxSearch`, and `k_url_convert=https://download.ig-12-data.xyz/api/json/convert`. The presence of a URL in source does not establish whether/when conversion runs; no vendor backend code or private API was accessed.
- Site's public copy describes server-side processing of Threads links. The user's report that LoveThreads downloads this post is accepted as the observed comparator; we did not independently verify its final media bytes.

## AVOCADOSS implementation
- `POST /api/v1/analyze` identifies media and issues a scoped token. `POST /api/v1/jobs` creates an asynchronous job. `GET /api/v1/jobs/{id}/file` serves a locally prepared asset.
- UI screenshot shows `Media ready`, 9 assets, but `Download preparation failed (FileNotFoundError)`, placing the observed failure after metadata extraction.
- On the live baseline, the asset preparation helper uses `tempfile.mkdtemp` directly. If the process's cached default temporary directory was removed, an uncaught `FileNotFoundError` can occur.
- The isolated fix (`backend/app/services/media_fetch.py`) recreates an explicitly configured scratch root; if the cached POSIX default disappeared, it retries in `/tmp`. It converts remaining storage failures into an actionable 503 rather than an opaque worker exception.
- Added unit and actual stream/ZIP archive regression tests against deleted cached scratch directory; this is an independent implementation, not copied LoveThreads code.

## Verification and deployment constraint
- MiniPC isolated CI: `PYTHON=<existing project venv>/bin/python bash scripts/ci-minipc-seo.sh`: **84 passed**, 1 Starlette deprecation warning. Python compile, JS checks, shell syntax, SEO/AEO/GEO checks all passed.
- The attempted live test against the user post returned HTTP 403 to the remote Python client before an analyzed payload could be confirmed. Do not present it as an end-to-end success or a confirmed backend stack trace.
- The running rootless application directory under `/opt/github-runners/lgkangno1-svg__korea-concierge-ci/home/services/insta-thread` is owned by `ghr-korea-concierge--c49acd`. The official remote account `tnfwod` receives Permission denied, and noninteractive sudo requires a password. No live files or processes were altered.
- **NOT DEPLOYED**. Owner-approved rollout must check active MiniPC CI/deployment state and uncommitted work, integrate only these commits, manually run MiniPC CI (no GitHub Actions), promote the tested SHA to `production`, let the authorized watchdog deploy, compare `/build.txt`, and verify that this specific post yields a downloadable MP4 and image files from the public domain.

## Notes
- Do not depend on, scrape beyond the publicly served code of, or reuse the undocumented LoveThreads conversion API in production. Own the extraction, temporary-file and delivery pipeline.
- REA's static relationships are not proof of network execution; public request details above derive from visible static scripts and HTML.
