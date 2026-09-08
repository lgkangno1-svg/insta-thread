# BUILD_SPEC — insta-thread

## 1. Product objective

One website accepts a public URL from one of five target platforms, detects the source, previews supported assets, and lets the visitor download the exact video or cover asset they choose.

### Required support

1. **YouTube**
   - public video / Shorts URL
   - Best / 2160 / 1440 / 1080 / 720 / 480 / 360 options when source formats make them available
   - FFmpeg merge/remux where audio/video are separate

2. **Instagram Reels**
   - Reel video
   - thumbnail candidates
   - video or selected thumbnail download

3. **Xiaohongshu / 小红书**
   - supported public video-note URLs
   - video download

4. **Threads**
   - `threads.com` and `threads.net`
   - canonical post, `/t/` and share-link handling where the canonical post can be resolved
   - target-post-only selection; never silently use recommendation media
   - video + available image/cover candidates

5. **Douyin / 抖音**
   - public video URL
   - common short share links where yt-dlp resolves them
   - video + selectable cover candidates

## 2. UX

1. Paste URL.
2. Analyze.
3. Auto-detect platform.
4. Preview title/author/cover.
5. Show only valid media choices for that platform.
6. User selects one asset.
7. Optional compliant sponsor gate runs.
8. Server creates a background preparation job.
9. Browser polls job status.
10. Once ready, file starts streaming immediately.
11. Temporary server copy is deleted after delivery or TTL expiry.

## 3. Canonical web structure

Primary host: `download.avocadoss.co.kr`.

Platform subdomains are marketing aliases only and 301 redirect to canonical subdirectory pages. Do not serve duplicate indexed copies of the same content on all hostnames.

## 4. Backend

- FastAPI
- Python yt-dlp
- FFmpeg
- Node.js 22 for current yt-dlp YouTube EJS challenges
- bgutil POT provider sidecar on private Docker network
- dedicated Threads parser
- strict five-platform input-domain allowlist
- background ThreadPoolExecutor queue for mini-PC MVP
- SSD-backed temporary files
- rate limiting at Nginx / Cloudflare layer

## 5. Security

- http/https only
- URL credentials rejected
- unsupported host rejected before network access
- private/local resolved media hosts rejected
- Threads exact-shortcode targeting
- selected assets are re-resolved server-side
- temporary file cleanup after response and TTL expiry
- private yt-dlp cookies, if ever used, must be owner-controlled secrets and never client-supplied

## 6. Monetization

- Core service remains free.
- Normal ad clicks are never required.
- Direct sponsor/affiliate gate may require a short view but not a click.
- Google AdSense/Offerwall must not be assumed eligible for downloader pages; Publisher Policy review is required.
- Affiliate ads must be clearly disclosed and separate from Download controls.

## 7. SEO/content

Required canonical pages:

- `/youtube-downloader`
- `/instagram-reels-downloader`
- `/xiaohongshu-downloader`
- `/threads-downloader`
- `/douyin-downloader`
- `/faq`
- `/terms`
- `/privacy`
- `/copyright`

Also required:

- canonical tags
- `robots.txt`
- `sitemap.xml`
- useful non-doorway help copy

## 8. Deployment

Recommended MVP:

`Cloudflare -> Cloudflare Tunnel -> N100 mini PC -> Docker Compose`

Cloudflare routes six public hostnames to the same Nginx service. No inbound router port-forward is required.

## 9. Acceptance tests

- all supported hostnames detect correctly
- unsupported domain returns 400 without network access
- Threads exact target is selected over unrelated recommended media
- API health works
- downloader job API returns quickly before long yt-dlp processing begins
- stale job files are cleaned
- frontend platform aliases return 301 in production Nginx config
