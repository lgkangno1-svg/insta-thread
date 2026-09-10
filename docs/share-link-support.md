# Share-link input compatibility

The downloader accepts a single public media reference as a bare URL, a URL embedded in copied share text, or (for Xiaohongshu only) a 24-character note ID.

## YouTube
- `youtube.com/watch?v=...`
- `youtube.com/shorts/...`
- `youtu.be/...`
- mobile/music subdomains
- the same URLs embedded in copied text

## Instagram
- `instagram.com/reel/...`
- `instagram.com/reels/...`
- `instagram.com/p/...`
- `instagram.com/tv/...`
- current `/share/...` wrappers and legacy `instagr.am` redirects
- `igsh`, `igsi`, and ordinary tracking query strings are tolerated
- the same URLs embedded in copied text

## Threads
- `threads.com/@user/post/...`
- legacy `threads.net/...`
- `/share/...` and `/t/...` wrappers
- tracking query strings are tolerated
- the same URLs embedded in copied text

## Douyin
- `douyin.com/video/...`
- `v.douyin.com/...`
- legacy `iesdouyin.com/...`
- Chinese copied-share captions containing one of those URLs

## Xiaohongshu / RedNote
- `xiaohongshu.com/explore/<note_id>`
- `xiaohongshu.com/discovery/item/<note_id>`
- profile-note form `xiaohongshu.com/user/profile/<user_id>/<note_id>`
- `xhslink.com/...` and `xhslink.cn/...`, including `/m/`, `/o/`, and other redirect codes
- `rednote.com/...` note aliases
- PC/app share URLs carrying `xsec_token`/`xsec_source` (query parameters are preserved)
- a 24-character note ID
- full copied share text containing any supported URL

Only public media is supported. Private/login-only content, DRM, paywalls, and access-control bypasses are out of scope. Redirects are constrained to official hosts for the detected platform.
