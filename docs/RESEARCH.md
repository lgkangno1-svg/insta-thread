# Research notes

Research date: 2026-09-09

## 1. Core extraction engine: yt-dlp

Current upstream `yt-dlp` already contains native extractor logic for the main non-Threads platforms required by this project:

- Instagram Reels/posts: `yt_dlp/extractor/instagram.py`
- Xiaohongshu: `yt_dlp/extractor/xiaohongshu.py`
- Douyin: handled in the TikTok/Douyin extractor family
- YouTube: native extractor family

The current Xiaohongshu extractor reads the page's initial state, video stream metadata and image list. For this product's v1 UI, only Xiaohongshu video download is exposed.

Upstream: https://github.com/yt-dlp/yt-dlp

## 2. Threads

Upstream yt-dlp still does not ship a merged first-party Threads extractor.

Two useful current references were inspected:

### tribixbite/yt-dlp-threads

https://github.com/tribixbite/yt-dlp-threads

- public-domain/Unlicense yt-dlp plugin
- uses a Googlebot User-Agent so Threads returns link-preview crawler data for public posts
- selects the exact target shortcode instead of accidentally choosing a recommended post
- supports canonical post, `/t/`, share links and multi-video posts
- video-focused; image-only download is not its goal

### corvardt/nostos

https://github.com/corvardt/nostos

- MIT project
- dedicated Threads provider architecture
- extracts `video_versions` and `image_versions2`
- useful reference for the required video + thumbnail/image selection UX

The project implements its own small target-post parser rather than vendoring either application.

## 3. YouTube reliability in 2026

Current yt-dlp YouTube extraction uses the EJS challenge solver flow and requires a supported JavaScript runtime. Node.js 22 is installed in the backend Docker image.

Reference: https://github.com/yt-dlp/yt-dlp/wiki/EJS

A current bgutil PO-token provider is included as a private Docker sidecar. The provider is not exposed to the public host network.

Reference: https://github.com/Brainicism/bgutil-ytdlp-pot-provider

The provider can improve reliability for some YouTube bot checks but is not a guarantee against every 403/challenge condition.

## 4. Hugging Face findings

Hugging Face Spaces are useful implementation references but are not the right production dependency for this project.

Relevant examples found:

- `devil126/vid-downloader`: contains a dedicated Douyin downloader and quality-selection logic.
  https://huggingface.co/spaces/devil126/vid-downloader
- `RumaDev/Youtube_Downloader`: simple yt-dlp + Gradio resolution mapping.
  https://huggingface.co/spaces/RumaDev/Youtube_Downloader
- `wangzhao18/link-parser-agent`: documents Douyin/Xiaohongshu/YouTube/Instagram parsing and cookie/API fallback tradeoffs.
  https://huggingface.co/spaces/wangzhao18/link-parser-agent

Conclusion: extraction is primarily protocol/anti-bot engineering, not an ML task. Use Hugging Face as a reference/testing source, not a critical runtime.

## 5. Cloudflare deployment finding

Cloudflare Tunnel is suitable for the mini-PC origin because it uses outbound-only connections and can publish multiple public hostnames to the same local service without exposing the origin IP/ports.

However, Cloudflare's normal origin Proxy Read Timeout is 125 seconds on non-Enterprise plans. Large YouTube preparation can exceed that, so the application uses background jobs + polling rather than keeping the original HTTP request open while yt-dlp/FFmpeg work.

References:

- https://developers.cloudflare.com/tunnel/
- https://developers.cloudflare.com/fundamentals/reference/connection-limits/

## 6. SEO finding

Google states that it has no indexing/ranking preference between subdomains and subdirectories. Therefore platform subdomains are used as memorable 301 aliases, while one canonical hostname contains the actual indexable pages.

Reference:
https://developers.google.com/search/help/crawling-index-faq

## 7. Monetization policy finding

AdSense cannot be assumed suitable for a streaming-media downloader. Google Publisher Policies include pages that help users download streaming videos when prohibited by the provider as a disallowed example. YouTube's Terms also restrict downloading except where authorized by the service, rights holders, or applicable law.

References:

- https://support.google.com/publisherpolicies/answer/10436828
- https://www.youtube.com/t/terms

For that reason the code ships with a disabled direct-sponsor/affiliate view gate, not an AdSense click gate.
