# Multi-platform downloader evidence and resilience (2026-10-26 KST)

## Production sample verification (2026-10-25 15:58–16:14 UTC)

Public endpoint: https://download.avocadoss.co.kr

| Platform | Sample | Metadata | File bytes downloaded | File signature |
|---|---|---|---|---|
| Threads | `https://www.threads.com/@moabattem_aa/post/De5wP_IAd2_` | 9 assets | Earlier E2E: MP4 1,560,471 bytes and JPG 36,594 bytes | MP4/JPEG valid |
| Instagram | `https://www.instagram.com/reel/DH56yy7p3lZ/` | 5 assets | MP4 10,544,836 bytes | `ftyp` valid |
| YouTube | `https://www.youtube.com/watch?v=aqz-KE-bpKQ` | 15 assets | 360p MP4 25,581,751 bytes, thumbnail WebP 135,454 bytes | `ftyp`/RIFF WebP valid |
| Douyin | `https://www.douyin.com/video/7699106711789292201` | HTTP 422 | not available | public mobile share page returns metadata without matching video data |
| Xiaohongshu | `https://www.xiaohongshu.com/explore/6a8bfb930000000033020097` | HTTP 422 | not available | current page redirects to `/404`, so public source availability not established |

Independent `yt-dlp` probe of two Douyin posts returned fresh-guest-cookie-needed errors even with the owner-controlled guest-cookie jar. The observed Xiaohongshu sample also produced no media formats in a `yt-dlp` read-only probe. This is NOT evidence that all posts on those platforms are impossible to download; do not claim success without working public fixtures and real downloaded bytes.

## Reliability hardening

- Previously fixed Threads/Instagram/images scratch preparation uses `_make_job_tempdir`. The YouTube `yt-dlp` video path now uses the same helper; its deleted cached `tempfile.tempdir`, absent configured root, and unusable root scenarios have independent regression tests.
- The approved MiniPC rootless downloader runs in its own systemd unit rather than inheriting a GitHub Runner's removed `PrivateTmp` mount. Add a dedicated owner-only disk scratch root via the systemd service override: `MEDIA_TMP_DIR=$BASE/tmp/media`, `UMask=0077`, `ExecStartPre=/usr/bin/mkdir -p $BASE/tmp/media`. This remains outside the Git checkout and is created by the service account.
- `scripts/smoke-download-e2e.py` performs signed analysis, real job creation, actual file delivery and magic-signature verification, streams SHA-256 without retaining downloaded files, enforces a byte ceiling, and reports failures as failures.
- Manual MiniPC CI: `PYTHON=<project venv python> bash scripts/ci-minipc-seo.sh`. Full real-download checks are explicit/manual and should not be blindly scheduled against third-party websites to avoid rate limits, post removal, and content restrictions.

## Example

```bash
python3 scripts/smoke-download-e2e.py --url 'https://www.youtube.com/watch?v=aqz-KE-bpKQ' --asset-id video:360 --max-mb 75
python3 scripts/smoke-download-e2e.py --url 'https://www.instagram.com/reel/DH56yy7p3lZ/' --max-mb 60
```

A 200 /health or successful `analyze` response is not considered equivalent to a working download. A production change is complete only when the exact new SHA is confirmed via /build.txt, the service process is stable, and real media bytes have been checked from the external domain.

Limitations: third-party URLs, region rules, access restrictions and expiring CDN links are controlled by their respective platforms. Account restrictions or CAPTCHA cannot be diagnosed as local storage failures and are not silently bypassed.
