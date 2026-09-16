# Changelog

## 1.3.1

- Reworks the Windows client into a compact preview-first layout so download controls stay visible without excessive scrolling.
- Compresses the link and save-folder controls into a small two-row input panel.
- Moves the analyzed post text into a bounded summary panel with a separate full-text dialog.
- Shows download choices in a two-column card grid so common Threads/Instagram posts expose up to four choices in the first viewport.
- Adds a top-level `대표 영상 바로 다운로드` action and keeps whole-post batch download/retry actions beside it.
- Uses an available post image/thumbnail as the visual fallback for video cards that do not expose their own preview URL.
- Gives each card a media-specific button label such as `영상 다운로드`, `이미지 다운로드`, or `썸네일 다운로드`.

## 1.3.0

- Adds one-click whole-post downloads for photo/video carousels while excluding duplicate cover thumbnails when primary media is available.
- Remembers the last selected download folder between app launches.
- Renames generic files such as `download.mp4` to readable platform/author/post/media names when safe to do so.
- Adds a failed-item retry button for partial batch failures.
- Shows aggregate progress while downloading multiple media items sequentially.
- Keeps individual media-card downloads and the Instagram local fallback unchanged.

## 1.2.1

- Adds a local public-Instagram fallback when the production backend is temporarily behind or unavailable for Instagram parsing.
- Supports public Instagram photo posts, video posts and mixed carousels through the anonymous public media endpoint.
- Restricts direct fallback downloads to trusted Instagram/Facebook CDN HTTPS hosts.

## 1.2.0

- Replaces the ambiguous text-only download option list with thumbnail preview cards.
- Shows media type, format, resolution and orientation for each downloadable item.
- Adds a download button directly on every media card.
- Adds Pillow-based JPEG/WEBP thumbnail rendering inside the Windows app.
- Fixes Instagram public photo posts that previously failed with “No downloadable video was found”.
- Adds support for Instagram photo carousels and mixed image/video carousels.

## 1.1.0

- Adds AVOCADOSS application icon and Windows file/product version metadata.
- Adds visible download progress and buttons to open the downloaded file or save folder.
- Writes downloads to `.part` first and atomically renames only after a complete transfer.
- Adds startup/manual update checks against official `desktop-v*` GitHub Releases only.
- Downloads updates only from the official repository, verifies SHA-256, then asks before replacing the running EXE.
- Adds automatic versioned GitHub Release publishing from successful main-branch Windows builds.

## 1.0.0

- Initial Windows EXE client.
- Supports YouTube, Instagram, Threads, Douyin and Xiaohongshu/RedNote public links.
- Reuses the production AVOCADOSS analyze/job/download API.
- Adds folder selection, duplicate-name protection and explicit error handling.
