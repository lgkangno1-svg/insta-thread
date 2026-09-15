from __future__ import annotations

import http.cookiejar
import json
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_GRAPHQL_URL = "https://www.instagram.com/graphql/query"
_HOME_URL = "https://www.instagram.com/"
_DOC_ID = "27128499623469141"
_APP_ID = "936619743392459"
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)
_SHORTCODE_RE = re.compile(r"/(?:reel|reels|p|tv)/(?P<code>[A-Za-z0-9_-]+)", re.IGNORECASE)
_LOCAL_TOKEN_PREFIX = "local-instagram:"
_LOCAL_JOB_PREFIX = "local-instagram-job:"
_LOCAL_DOWNLOAD_PREFIX = "local-instagram://"
_MAX_DIRECT_BYTES = 750 * 1024 * 1024


class LocalInstagramError(RuntimeError):
    pass


def _shortcode(url: str) -> str:
    match = _SHORTCODE_RE.search(url)
    if not match:
        raise LocalInstagramError("지원하지 않는 Instagram 게시물 주소입니다.")
    return match.group("code")


def _canonical_url(url: str, shortcode: str) -> str:
    lowered = url.lower()
    if "/p/" in lowered:
        return f"https://www.instagram.com/p/{shortcode}/"
    if "/tv/" in lowered:
        return f"https://www.instagram.com/tv/{shortcode}/"
    return f"https://www.instagram.com/reel/{shortcode}/"


def _video_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [x for x in (item.get("video_versions") or []) if isinstance(x, dict) and x.get("url")]
    candidates.sort(
        key=lambda x: ((x.get("width") or 0) * (x.get("height") or 0), x.get("width") or 0),
        reverse=True,
    )
    return candidates


def _image_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    raw = ((item.get("image_versions2") or {}).get("candidates")) or []
    candidates = [x for x in raw if isinstance(x, dict) and x.get("url")]
    candidates.sort(
        key=lambda x: ((x.get("width") or 0) * (x.get("height") or 0), x.get("width") or 0),
        reverse=True,
    )
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for candidate in candidates:
        url = str(candidate["url"])
        if url in seen:
            continue
        seen.add(url)
        output.append(candidate)
    return output


def _caption(item: dict[str, Any]) -> str | None:
    caption = item.get("caption")
    if isinstance(caption, dict):
        text = caption.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def _media_items(item: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    carousel = [x for x in (item.get("carousel_media") or []) if isinstance(x, dict)]
    return (carousel, True) if carousel else ([item], False)


def _public_item(url: str) -> dict[str, Any]:
    shortcode = _shortcode(url)
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    common_headers = {
        "User-Agent": _BROWSER_UA,
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        home_req = urllib.request.Request(_HOME_URL, headers=common_headers)
        with opener.open(home_req, timeout=30) as response:
            response.read(128 * 1024)

        csrf = ""
        for cookie in jar:
            if cookie.name == "csrftoken":
                csrf = cookie.value
                break

        variables = json.dumps(
            {
                "shortcode": shortcode,
                "__relay_internal__pv__PolarisAIGMMediaWebLabelEnabledrelayprovider": False,
            },
            separators=(",", ":"),
        )
        body = urllib.parse.urlencode(
            {
                "variables": variables,
                "doc_id": _DOC_ID,
                "server_timestamps": "true",
            }
        ).encode("utf-8")
        headers = {
            **common_headers,
            "Accept": "*/*",
            "Origin": "https://www.instagram.com",
            "Referer": _canonical_url(url, shortcode),
            "X-CSRFToken": csrf,
            "X-IG-App-ID": _APP_ID,
            "Content-Type": "application/x-www-form-urlencoded",
        }
        request = urllib.request.Request(_GRAPHQL_URL, data=body, headers=headers, method="POST")
        with opener.open(request, timeout=40) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        raise LocalInstagramError(f"Instagram 공개 게시물을 직접 읽지 못했습니다: {exc}") from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    web_info = (data or {}).get("xdt_api__v1__media__shortcode__web_info") if isinstance(data, dict) else None
    items = (web_info or {}).get("items") if isinstance(web_info, dict) else None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise LocalInstagramError(
            "Instagram이 이 공개 게시물의 미디어 정보를 익명 요청에 제공하지 않았습니다. "
            "비공개/삭제/로그인 제한 게시물은 지원하지 않습니다."
        )
    return items[0]


def build_analysis_from_item(url: str, item: dict[str, Any]) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    shortcode = _shortcode(url)
    media_items, is_carousel = _media_items(item)
    assets: list[dict[str, Any]] = []
    direct: dict[str, dict[str, str]] = {}
    preview: str | None = None

    def add_asset(
        asset_id: str,
        kind: str,
        label: str,
        ext: str,
        source: str,
        preview_url: str | None,
        width: int | None,
        height: int | None,
    ) -> None:
        assets.append(
            {
                "id": asset_id,
                "kind": kind,
                "label": label,
                "ext": ext,
                "width": width,
                "height": height,
                "filesize": None,
                "preview_url": preview_url,
            }
        )
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", asset_id).strip("-") or "media"
        direct[asset_id] = {
            "url": source,
            "ext": ext,
            "filename": f"instagram-{shortcode}-{safe_id}.{ext}",
        }

    if is_carousel:
        for idx, media in enumerate(media_items):
            videos = _video_candidates(media)
            images = _image_candidates(media)
            best_image = images[0] if images else None
            if preview is None and best_image:
                preview = str(best_image["url"])
            if videos:
                best = videos[0]
                width = best.get("width") if isinstance(best.get("width"), int) else None
                height = best.get("height") if isinstance(best.get("height"), int) else None
                add_asset(
                    f"video:{idx}",
                    "video",
                    f"Video {idx + 1}",
                    "mp4",
                    str(best["url"]),
                    str(best_image["url"]) if best_image else None,
                    width,
                    height,
                )
            elif best_image:
                width = best_image.get("width") if isinstance(best_image.get("width"), int) else None
                height = best_image.get("height") if isinstance(best_image.get("height"), int) else None
                add_asset(
                    f"image:{idx}",
                    "image",
                    f"Image {idx + 1}",
                    "jpg",
                    str(best_image["url"]),
                    str(best_image["url"]),
                    width,
                    height,
                )
    else:
        videos = _video_candidates(item)
        images = _image_candidates(item)
        best_image = images[0] if images else None
        preview = str(best_image["url"]) if best_image else None
        if videos:
            best = videos[0]
            width = best.get("width") if isinstance(best.get("width"), int) else None
            height = best.get("height") if isinstance(best.get("height"), int) else None
            add_asset(
                "video:best",
                "video",
                "Best available video",
                "mp4",
                str(best["url"]),
                preview,
                width,
                height,
            )
            for idx, image in enumerate(images[:4]):
                width = image.get("width") if isinstance(image.get("width"), int) else None
                height = image.get("height") if isinstance(image.get("height"), int) else None
                dims = f"{width}×{height}" if width and height else "cover"
                add_asset(
                    f"thumbnail:{idx}",
                    "thumbnail",
                    f"Cover {dims}",
                    "jpg",
                    str(image["url"]),
                    str(image["url"]),
                    width,
                    height,
                )
        elif best_image:
            width = best_image.get("width") if isinstance(best_image.get("width"), int) else None
            height = best_image.get("height") if isinstance(best_image.get("height"), int) else None
            add_asset(
                "image:0",
                "image",
                "Original image",
                "jpg",
                str(best_image["url"]),
                str(best_image["url"]),
                width,
                height,
            )

    if not assets:
        raise LocalInstagramError("다운로드 가능한 공개 Instagram 미디어를 찾지 못했습니다.")

    user = item.get("user") or {}
    username = user.get("username") if isinstance(user, dict) else None
    title = _caption(item) or f"Instagram post {shortcode}"
    analysis = {
        "platform": "instagram",
        "title": title[:300],
        "author": f"@{username}" if username else None,
        "webpage_url": _canonical_url(url, shortcode),
        "preview_url": preview,
        "assets": assets,
        "source_url": url,
        "sponsor_gate_enabled": False,
        "gate_seconds": 0,
    }
    return analysis, direct


def analyze_public_instagram(url: str) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    return build_analysis_from_item(url, _public_item(url))


def _is_trusted_media_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not host:
        return False
    return host == "cdninstagram.com" or host.endswith(".cdninstagram.com") or host == "fbcdn.net" or host.endswith(".fbcdn.net")


def patch_api_client(core_module: Any) -> None:
    client_cls = core_module.ApiClient
    if getattr(client_cls, "_instagram_local_fallback_patched", False):
        return

    original_analyze = client_cls.analyze
    original_create_job = client_cls.create_job
    original_wait_until_ready = client_cls.wait_until_ready
    original_download_file = client_cls.download_file

    def analyze(self: Any, url: str) -> dict:
        try:
            return original_analyze(self, url)
        except core_module.ApiError as server_error:
            if core_module.detect_platform(url) != "instagram":
                raise
            try:
                data, direct_assets = analyze_public_instagram(url)
            except LocalInstagramError:
                raise server_error
            token = _LOCAL_TOKEN_PREFIX + secrets.token_urlsafe(18)
            data["analysis_token"] = token
            source_url = core_module.extract_supported_url(url) or url
            data["source_url"] = source_url
            stores = getattr(self, "_local_instagram_analyses", None)
            if not isinstance(stores, dict):
                stores = {}
                setattr(self, "_local_instagram_analyses", stores)
            if len(stores) >= 12:
                for stale in list(stores)[:-8]:
                    stores.pop(stale, None)
            stores[token] = {"source_url": source_url, "assets": direct_assets, "created": time.monotonic()}
            return data

    def create_job(self: Any, url: str, asset_id: str, analysis_token: str) -> str:
        if isinstance(analysis_token, str) and analysis_token.startswith(_LOCAL_TOKEN_PREFIX):
            stores = getattr(self, "_local_instagram_analyses", {})
            analysis = stores.get(analysis_token) if isinstance(stores, dict) else None
            normalized = core_module.extract_supported_url(url) or url
            if not isinstance(analysis, dict) or analysis.get("source_url") != normalized:
                raise core_module.ApiError("Instagram 로컬 분석 정보가 만료되었습니다. 링크를 다시 분석해 주세요.")
            assets = analysis.get("assets")
            selected = assets.get(asset_id) if isinstance(assets, dict) else None
            if not isinstance(selected, dict):
                raise core_module.ApiError("선택한 Instagram 미디어를 찾을 수 없습니다. 다시 분석해 주세요.")
            job_id = _LOCAL_JOB_PREFIX + secrets.token_urlsafe(18)
            jobs = getattr(self, "_local_instagram_jobs", None)
            if not isinstance(jobs, dict):
                jobs = {}
                setattr(self, "_local_instagram_jobs", jobs)
            jobs[job_id] = dict(selected)
            return job_id
        return original_create_job(self, url, asset_id, analysis_token)

    def wait_until_ready(self: Any, job_id: str, progress=None, timeout_seconds: int = 12 * 60) -> str:
        if isinstance(job_id, str) and job_id.startswith(_LOCAL_JOB_PREFIX):
            jobs = getattr(self, "_local_instagram_jobs", {})
            if not isinstance(jobs, dict) or job_id not in jobs:
                raise core_module.ApiError("Instagram 로컬 다운로드 작업이 만료되었습니다.")
            if progress:
                progress("ready")
            return _LOCAL_DOWNLOAD_PREFIX + urllib.parse.quote(job_id, safe="")
        return original_wait_until_ready(self, job_id, progress=progress, timeout_seconds=timeout_seconds)

    def download_file(self: Any, download_url: str, folder: Path, progress=None) -> Path:
        if not (isinstance(download_url, str) and download_url.startswith(_LOCAL_DOWNLOAD_PREFIX)):
            return original_download_file(self, download_url, folder, progress=progress)

        job_id = urllib.parse.unquote(download_url[len(_LOCAL_DOWNLOAD_PREFIX):])
        jobs = getattr(self, "_local_instagram_jobs", {})
        selected = jobs.get(job_id) if isinstance(jobs, dict) else None
        if not isinstance(selected, dict):
            raise core_module.ApiError("Instagram 로컬 다운로드 작업이 만료되었습니다.")
        source = str(selected.get("url") or "")
        if not _is_trusted_media_url(source):
            raise core_module.ApiError("Instagram 미디어 주소의 출처를 확인할 수 없어 다운로드를 중단했습니다.")
        filename = str(selected.get("filename") or "instagram-media.bin")
        target = core_module.unique_path(folder, filename)
        partial = Path(str(target) + ".part")
        request = urllib.request.Request(
            source,
            headers={
                "User-Agent": _BROWSER_UA,
                "Referer": "https://www.instagram.com/",
                "Accept": "*/*",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                total_header = response.headers.get("Content-Length")
                total = int(total_header) if total_header and total_header.isdigit() else None
                if total is not None and total > _MAX_DIRECT_BYTES:
                    raise core_module.ApiError("Instagram 미디어가 허용된 최대 파일 크기를 초과합니다.")
                received = 0
                with partial.open("wb") as handle:
                    while True:
                        chunk = response.read(512 * 1024)
                        if not chunk:
                            break
                        received += len(chunk)
                        if received > _MAX_DIRECT_BYTES:
                            raise core_module.ApiError("Instagram 미디어가 허용된 최대 파일 크기를 초과합니다.")
                        handle.write(chunk)
                        if progress:
                            progress(received, total)
                if total is not None and received != total:
                    raise core_module.ApiError("Instagram 미디어 다운로드가 중간에 끊겼습니다.")
            os.replace(partial, target)
            jobs.pop(job_id, None)
            return target
        except core_module.ApiError:
            raise
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise core_module.ApiError(f"Instagram 미디어 직접 다운로드에 실패했습니다: {exc}") from exc
        except OSError as exc:
            raise core_module.ApiError(f"파일을 저장할 수 없습니다: {exc}") from exc
        finally:
            if partial.exists():
                try:
                    partial.unlink()
                except OSError:
                    pass

    client_cls.analyze = analyze
    client_cls.create_job = create_job
    client_cls.wait_until_ready = wait_until_ready
    client_cls.download_file = download_file
    client_cls._instagram_local_fallback_patched = True
