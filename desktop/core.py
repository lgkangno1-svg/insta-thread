from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

API_BASE = "https://download.avocadoss.co.kr"
RELEASES_API = "https://api.github.com/repos/lgkangno1-svg/insta-thread/releases?per_page=20"
RELEASE_TAG_PREFIX = "desktop-v"
RELEASE_ASSET_NAME = "AVOCADOSS-Downloader.exe"
RELEASE_CHECKSUM_NAME = RELEASE_ASSET_NAME + ".sha256"

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
_SAFE_FILENAME = re.compile(r'[<>:\"/\\|?*\x00-\x1f]')
_VERSION = re.compile(r"^\s*(\d+)\.(\d+)\.(\d+)\s*$")


class ApiError(RuntimeError):
    pass


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / relative


def load_app_version() -> str:
    try:
        version = resource_path("VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"
    return version if _VERSION.fullmatch(version) else "0.0.0"


APP_VERSION = load_app_version()


def parse_version(value: str) -> tuple[int, int, int]:
    match = _VERSION.fullmatch(str(value or ""))
    if not match:
        raise ValueError(f"Invalid version: {value}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def is_newer_version(candidate: str, current: str) -> bool:
    try:
        return parse_version(candidate) > parse_version(current)
    except ValueError:
        return False


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


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    download_url: str
    checksum_url: str
    page_url: str


def _trusted_release_asset_url(url: str, filename: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        return False
    prefix = "/lgkangno1-svg/insta-thread/releases/download/"
    return parsed.path.startswith(prefix) and parsed.path.endswith("/" + filename)


def select_release_info(releases: object, current_version: str = APP_VERSION) -> ReleaseInfo | None:
    if not isinstance(releases, list):
        return None
    candidates: list[tuple[tuple[int, int, int], ReleaseInfo]] = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = str(release.get("tag_name") or "")
        if not tag.startswith(RELEASE_TAG_PREFIX):
            continue
        version = tag[len(RELEASE_TAG_PREFIX):]
        if not is_newer_version(version, current_version):
            continue
        assets = release.get("assets")
        if not isinstance(assets, list):
            continue
        urls: dict[str, str] = {}
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            url = str(asset.get("browser_download_url") or "")
            if name and url:
                urls[name] = url
        exe_url = urls.get(RELEASE_ASSET_NAME, "")
        checksum_url = urls.get(RELEASE_CHECKSUM_NAME, "")
        if not _trusted_release_asset_url(exe_url, RELEASE_ASSET_NAME):
            continue
        if not _trusted_release_asset_url(checksum_url, RELEASE_CHECKSUM_NAME):
            continue
        info = ReleaseInfo(
            version=version,
            download_url=exe_url,
            checksum_url=checksum_url,
            page_url=str(release.get("html_url") or "https://github.com/lgkangno1-svg/insta-thread/releases"),
        )
        candidates.append((parse_version(version), info))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


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
    if not candidate.exists() and not Path(str(candidate) + ".part").exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 10000):
        alt = folder / f"{stem} ({index}){suffix}"
        if not alt.exists() and not Path(str(alt) + ".part").exists():
            return alt
    raise ApiError("같은 이름의 파일이 너무 많습니다. 저장 폴더를 변경해 주세요.")


class ApiClient:
    def __init__(self, base_url: str = API_BASE) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = f"AVOCADOSS-Downloader-Windows/{APP_VERSION}"

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
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError("서버 응답을 읽을 수 없습니다.") from exc
        if not isinstance(decoded, dict):
            raise ApiError("서버 응답 형식이 올바르지 않습니다.")
        return decoded

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
                if not download_url.startswith("/api/v1/jobs/") or not download_url.endswith("/file"):
                    raise ApiError("준비된 파일의 다운로드 주소가 올바르지 않습니다.")
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
        if not download_url.startswith("/api/v1/jobs/") or not download_url.endswith("/file"):
            raise ApiError("다운로드 주소가 올바르지 않습니다.")
        absolute = urllib.parse.urljoin(self.base_url + "/", download_url)
        request = urllib.request.Request(absolute, headers={"User-Agent": self.user_agent})
        target: Path | None = None
        partial: Path | None = None
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                disposition = response.headers.get("Content-Disposition", "")
                filename = self._filename_from_disposition(disposition) or "AVOCADOSS-download.bin"
                target = unique_path(folder, filename)
                partial = Path(str(target) + ".part")
                total_header = response.headers.get("Content-Length")
                total = int(total_header) if total_header and total_header.isdigit() else None
                received = 0
                with partial.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 512)
                        if not chunk:
                            break
                        handle.write(chunk)
                        received += len(chunk)
                        if progress:
                            progress(received, total)
                if total is not None and received != total:
                    raise ApiError(f"다운로드가 완전히 끝나지 않았습니다 ({received}/{total} bytes).")
                os.replace(partial, target)
                return target
        except urllib.error.HTTPError as exc:
            raise ApiError(f"파일 다운로드 실패 ({exc.code})") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"파일 다운로드 연결 실패: {getattr(exc, 'reason', exc)}") from exc
        except OSError as exc:
            raise ApiError(f"파일을 저장할 수 없습니다: {exc}") from exc
        finally:
            if partial and partial.exists():
                try:
                    partial.unlink()
                except OSError:
                    pass

    def check_for_update(self, current_version: str = APP_VERSION) -> ReleaseInfo | None:
        request = urllib.request.Request(
            RELEASES_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": self.user_agent,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ApiError(f"업데이트 서버를 확인할 수 없습니다: {exc}") from exc
        return select_release_info(payload, current_version)

    def download_update(
        self,
        release: ReleaseInfo,
        progress: Callable[[int, int | None], None] | None = None,
    ) -> Path:
        if not _trusted_release_asset_url(release.download_url, RELEASE_ASSET_NAME):
            raise ApiError("업데이트 다운로드 주소가 신뢰할 수 없는 주소입니다.")
        if not _trusted_release_asset_url(release.checksum_url, RELEASE_CHECKSUM_NAME):
            raise ApiError("업데이트 검증 파일 주소가 올바르지 않습니다.")

        checksum_request = urllib.request.Request(
            release.checksum_url,
            headers={"User-Agent": self.user_agent, "Accept": "text/plain"},
        )
        try:
            with urllib.request.urlopen(checksum_request, timeout=20) as response:
                checksum_text = response.read(4096).decode("utf-8", "replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            raise ApiError(f"업데이트 검증 정보를 받을 수 없습니다: {exc}") from exc
        match = re.search(r"\b([0-9a-fA-F]{64})\b", checksum_text)
        if not match:
            raise ApiError("업데이트 SHA-256 검증값이 없습니다.")
        expected = match.group(1).lower()

        destination = Path(tempfile.gettempdir()) / f"AVOCADOSS-Downloader-{release.version}.exe"
        partial = Path(str(destination) + ".part")
        for path in (destination, partial):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise ApiError(f"기존 업데이트 파일을 정리할 수 없습니다: {exc}") from exc

        request = urllib.request.Request(release.download_url, headers={"User-Agent": self.user_agent})
        digest = hashlib.sha256()
        try:
            with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as handle:
                total_header = response.headers.get("Content-Length")
                total = int(total_header) if total_header and total_header.isdigit() else None
                received = 0
                while True:
                    chunk = response.read(1024 * 512)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if progress:
                        progress(received, total)
                if total is not None and received != total:
                    raise ApiError("업데이트 파일 다운로드가 중간에 끊겼습니다.")
            if digest.hexdigest().lower() != expected:
                raise ApiError("업데이트 파일 SHA-256 검증에 실패했습니다.")
            os.replace(partial, destination)
            return destination
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            raise ApiError(f"업데이트 파일 다운로드에 실패했습니다: {exc}") from exc
        finally:
            if partial.exists():
                try:
                    partial.unlink()
                except OSError:
                    pass

    @staticmethod
    def _filename_from_disposition(disposition: str) -> str:
        if not disposition:
            return ""
        star = re.search(r"filename\*=UTF-8''([^;]+)", disposition, re.IGNORECASE)
        if star:
            return sanitize_filename(urllib.parse.unquote(star.group(1)))
        plain = re.search(r'filename="?([^";]+)"?', disposition, re.IGNORECASE)
        return sanitize_filename(plain.group(1).strip()) if plain else ""


def schedule_windows_self_update(new_exe: Path, current_exe: Path, pid: int) -> Path:
    if os.name != "nt":
        raise ApiError("자동 교체는 Windows 실행파일에서만 지원합니다.")
    new_exe = new_exe.resolve()
    current_exe = current_exe.resolve()
    if not new_exe.is_file() or not current_exe.is_file():
        raise ApiError("업데이트할 실행파일을 찾을 수 없습니다.")
    if not os.access(current_exe.parent, os.W_OK):
        raise ApiError("현재 프로그램 폴더에 쓰기 권한이 없습니다.")

    script = Path(tempfile.gettempdir()) / f"avocadoss-update-{pid}.cmd"
    current_q = str(current_exe).replace("%", "%%")
    new_q = str(new_exe).replace("%", "%%")
    script.write_text(
        "@echo off\r\n"
        "setlocal\r\n"
        f"set \"TARGET={current_q}\"\r\n"
        f"set \"SOURCE={new_q}\"\r\n"
        f"set \"APP_PID={int(pid)}\"\r\n"
        ":wait\r\n"
        "tasklist /FI \"PID eq %APP_PID%\" /NH 2>NUL | find \"%APP_PID%\" >NUL\r\n"
        "if not errorlevel 1 (\r\n"
        "  timeout /T 1 /NOBREAK >NUL\r\n"
        "  goto wait\r\n"
        ")\r\n"
        "copy /Y \"%SOURCE%\" \"%TARGET%\" >NUL\r\n"
        "if errorlevel 1 exit /B 1\r\n"
        "start \"\" \"%TARGET%\"\r\n"
        "del /Q \"%SOURCE%\" >NUL 2>&1\r\n"
        "del /Q \"%~f0\" >NUL 2>&1\r\n",
        encoding="utf-8",
        newline="",
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(["cmd.exe", "/c", str(script)], creationflags=flags, close_fds=True)
    return script


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
