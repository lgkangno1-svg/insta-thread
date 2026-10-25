# Douyin public mobile-feed fallback — 2026-10-26

Problem: Douyin's `iesdouyin.com/share/video/{id}` SSR HTML still loads, but on multiple publicly indexed October 2026 posts the embedded `_ROUTER_DATA` contains only template metadata, not `videoInfoRes.item_list`. The existing Douyin adapter returns HTTP 422 despite the public video being available.

Solution: preserve existing SSR extraction and then use two publicly accessible mobile-feed response endpoints as fallback, selecting **only the exact requested numeric aweme ID** with media URLs. Do not return a random recommendation entry or a login-restricted post. The source endpoints and general mobile-feed technique are described in [ucmao/media-parser](https://github.com/ucmao/media-parser), MIT licensed; our code is independently implemented, not copied. No bypass of user login challenges or CAPTCHA and no third-party paid API.

Observed public posts:
- `https://www.douyin.com/video/7699487756020750335`: new adapter resolves video plus covers. Live isolated download 3,790,444 bytes, MP4 `ftyp`; `ffprobe` reports H.264 720x1280, AAC, 21.94 seconds.
- `https://www.douyin.com/video/7694152397853930383`: mobile endpoint returns exact matching aweme with video info.
- `https://www.douyin.com/video/7696173697660407081`: feed may not contain the target; must return 422 and not download another user's unrelated recommendation.
- Two independently sampled Xiaohongshu pages `68c8d6d7000000001d01bdbd` and tokenized `6455b3d7000000000800e27f` also yielded real image bytes via the existing downloader. A public note without valid media may legitimately return 422.

Safety: preserve the existing `_assert_public_host` controls on CDN URL downloads and the signed-job authorization. The fallback uses fixed trusted hosts, bounded timeouts, no redirects for feed requests, and no asset link disclosure from other IDs. Provider access and media availability may change, so the page being publicly indexed does not guarantee file availability indefinitely.

Testing: MiniPC `scripts/ci-minipc-seo.sh` = 92 passed (1 third-party deprecation warning). Isolated real media bytes + FFprobe verified. Production SHA / external E2E verification required separately after integration, as a 200 from `/health` is insufficient. No GitHub Actions.
