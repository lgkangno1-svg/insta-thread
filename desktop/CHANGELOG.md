# Changelog

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
