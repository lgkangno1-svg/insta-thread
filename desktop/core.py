from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

API_BASE = "https://download.avocadoss.co.kr"
SUPPORTED_PLATFORMS = {
    "youtube": "YouTube",
    "instagram": "Instagram",
    "threads": "Threads",
    "douyin": "Douyin / 도우인",
    "xiaohongshu": "Xiaohongshu / 샤오홍슈 / RedNote",
}

_EXPLICIT_URL = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
_BARE_URL = re.compile(
    r"(?<![\w@])(?:(?:www|m|music|v)\.)?"
    r"(?:youtu\.be|youtube\.com|instagram\.com|instagr\.am|"
    r"threads\.com|threads\.net|douyin\.com|iesdouyin\.com|"
    r"xiaohongshu\.com|rednote\.com|xhslink\.com|xhslink\.cn)"
    r"/[^\s<>\"'`]+",
    re.IGNORECASE,
)
_TRAILING = re.compile(r"[.,;:!?，。；：！？、)\]}>】》」』）”’\"]+$")
_ZERO_WIDTH = re.compile(r"[\u200B-\u200D\u2060\uFEFF]")
_SAFE_FILENAME = re.compile(r"[<>:\"/\\|?*\x00-\x1f]")


class ApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class Asset:
    id: str
    kind: str
    label: str
    ext: str = ""
    width: int | None = None
    height: int | None = None
    filesize: int | None = None

    @property
    def display(self) -> str:
        parts = [self.label or self.kind.title()]
        details: list[str] = []
        if self.ext:
            details.append(self.ext.upper())
        if self.width and self.height:
            details.append(f"{self.width}×{self.height}")
        if self.filesize:
            details.append(format_bytes(self.filesize))
        if details:
            parts.append(" · ".join(details))
        return " — ".join(parts)


def detect_platform(candidate: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(candidate)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"}:
        return ""
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com"):
        return "youtube"
    if host in {"instagram.com", "instagr.am"} or host.endswith(".instagram.com"):
        return "instagram"
    if host in {"threads.com", "threads.net"} or host.endswith((".threads.com", ".threads.net")):
        return "threads"
    if host in {"douyin.com", "iesdouyin.com"} or host.endswith(".douyin.com"):
        return "douyin"
    if host in {"xiaohongshu.com", "xhslink.com", "xhslink.cn", "rednote.com"} or host.endswith(
        (".xiaohongshu.com", ".rednote.com")
    ):
        return "xiaohongshu"
    return ""


def extract_supported_url(raw: str) -> str:
    text = _ZERO_WIDTH.sub("", str(raw or "")).strip()
    if not text:
        return ""

    for match in _EXPLICIT_URL.finditer(text):
        candidate = _TRAILING.sub("", match.group(0).strip())
        if detect_platform(candidate):
            return candidate

    for match in _BARE_URL.finditer(text):
        candidate = "https://" + _TRAILING.sub("", match.group(0).strip())
        if detect_platform(candidate):
            return candidate

    if re.fullmatch(r"[0-9a-fA-F]{24}", text):
        return f"https://www.xiaohongshu.com/explore/{text.lower()}"
    return ""


def format_bytes(value: int | None) -> str:
    if not value or value < 1:
        return ""
    size = float(value)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def sanitize_filename(name: str, fallback: str = "AVOCADOSS-download") -> str:
    cleaned = _SAFE_FILENAME.sub("_", (name or "").strip()).rstrip(". ")
    if not cleaned:
        cleaned = fallback
    stem, ext = os.path.splitext(cleaned)
    if len(stem) > 150:
        stem = stem[:150].rstrip()
    return f"{stem}{ext}" if ext else stem


def unique_path(folder: Path, filename: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    filename = sanitize_filename(filename)
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 10000):
        alt = folder / f"{stem} ({index}){suffix}"
        if not alt.exists():
            return alt
    raise ApiError("같은 이름의 파일이 너무 많습니다. 저장 폴더를 변경해 주세요.")


class ApiClient:
    def __init__(self, base_url: str = API_BASE) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = "AVOCADOSS-Downloader-Windows/1.0"

    def _request_json(self, path: str, method: str = "GET", payload: dict | None = None, timeout: int = 75) -> dict:
        body = None
        headers = {"Accept": "application/json", "User-Agent": self.user_agent}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                parsed = json.loads(exc.read().decode("utf-8", "replace"))
                detail = str(parsed.get("detail") or parsed.get("error") or "")
            except Exception:
                pass
            if exc.code == 429:
                raise ApiError("요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.") from exc
            raise ApiError(detail or f"서버 요청 실패 ({exc.code})") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"서버에 연결할 수 없습니다: {getattr(exc, 'reason', exc)}") from exc
        except TimeoutError as exc:
            raise ApiError("서버 응답 시간이 초과되었습니다. 다시 시도해 주세요.") from exc

        try:
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("서버 응답을 읽을 수 없습니다.") from exc

    def analyze(self, url: str) -> dict:
        return self._request_json("/api/v1/analyze", "POST", {"url": url}, timeout=80)

    def create_job(self, url: str, asset_id: str, analysis_token: str) -> str:
        result = self._request_json(
            "/api/v1/jobs",
            "POST",
            {"url": url, "asset_id": asset_id, "analysis_token": analysis_token},
            timeout=30,
        )
        job_id = str(result.get("id") or "")
        if not job_id:
            raise ApiError("다운로드 작업 ID를 받지 못했습니다.")
        return job_id

    def wait_until_ready(
        self,
        job_id: str,
        progress: Callable[[str], None] | None = None,
        timeout_seconds: int = 12 * 60,
    ) -> str:
        started = time.monotonic()
        failures = 0
        while time.monotonic() - started < timeout_seconds:
            time.sleep(1.5)
            try:
                result = self._request_json(f"/api/v1/jobs/{urllib.parse.quote(job_id)}", timeout=20)
                failures = 0
            except ApiError:
                failures += 1
                if failures <= 8:
                    continue
                raise
            status = str(result.get("status") or "")
            if progress:
                progress(status)
            if status == "ready":
                download_url = str(result.get("download_url") or "")
                if not download_url:
                    raise ApiError("준비된 파일의 다운로드 주소가 없습니다.")
                return download_url
            if status == "error":
                raise ApiError(str(result.get("error") or "다운로드 준비에 실패했습니다."))
        raise ApiError("다운로드 준비 시간이 초과되었습니다. 더 낮은 화질로 다시 시도해 주세요.")

    def download_file(
        self,
        download_url: str,
        folder: Path,
        progress: Callable[[int, int | None], None] | None = None,
    ) -> Path:
        absolute = urllib.parse.urljoin(self.base_url + "/", download_url)
        request = urllib.request.Request(absolute, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                disposition = response.headers.get("Content-Disposition", "")
                filename = self._filename_from_disposition(disposition) or "AVOCADOSS-download.bin"
                target = unique_path(folder, filename)
                total_header = response.headers.get("Content-Length")
                total = int(total_header) if total_header and total_header.isdigit() else None
                received = 0
                with target.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        handle.write(chunk)
                        received += len(chunk)
                        if progress:
                            progress(received, total)
                return target
        except urllib.error.HTTPError as exc:
            raise ApiError(f"파일 다운로드 실패 ({exc.code})") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"파일 다운로드 연결 실패: {getattr(exc, 'reason', exc)}") from exc
        except OSError as exc:
            raise ApiError(f"파일을 저장할 수 없습니다: {exc}") from exc

    @staticmethod
    def _filename_from_disposition(disposition: str) -> str:
        if not disposition:
            return ""
        star = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.IGNORECASE)
        if star:
            return sanitize_filename(urllib.parse.unquote(star.group(1)))
        plain = re.search(r'filename="?([^";]+)"?', disposition, re.IGNORECASE)
        return sanitize_filename(plain.group(1).strip()) if plain else ""


def assets_from_response(data: dict) -> list[Asset]:
    result: list[Asset] = []
    for raw in data.get("assets") or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        result.append(
            Asset(
                id=str(raw["id"]),
                kind=str(raw.get("kind") or "media"),
                label=str(raw.get("label") or raw.get("kind") or "Media"),
                ext=str(raw.get("ext") or ""),
                width=raw.get("width") if isinstance(raw.get("width"), int) else None,
                height=raw.get("height") if isinstance(raw.get("height"), int) else None,
                filesize=raw.get("filesize") if isinstance(raw.get("filesize"), int) else None,
            )
        )
    return result
