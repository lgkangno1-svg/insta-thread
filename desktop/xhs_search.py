from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import websocket
except ImportError:  # pragma: no cover - packaging/runtime guard
    websocket = None

_SEARCH_BASE = "https://www.xiaohongshu.com/search_result"
_GOOGLE_TRANSLATE = "https://translate.googleapis.com/translate_a/single"
_MYMEMORY_TRANSLATE = "https://api.mymemory.translated.net/get"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


class XhsSearchError(RuntimeError):
    pass


class XhsLoginRequired(XhsSearchError):
    pass


@dataclass(slots=True)
class XhsSearchItem:
    note_id: str
    title: str
    author: str
    url: str
    thumbnail_url: str = ""
    likes: str = ""
    collects: str = ""
    comments: str = ""
    note_type: str = ""


def build_search_url(keyword: str) -> str:
    query = urllib.parse.urlencode({"keyword": keyword.strip(), "source": "web_explore_feed"})
    return f"{_SEARCH_BASE}?{query}"


def _http_json(url: str, timeout: float = 12.0) -> Any:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json,text/plain,*/*"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _parse_google_translation(payload: Any) -> str:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
        return ""
    parts: list[str] = []
    for segment in payload[0]:
        if isinstance(segment, list) and segment and isinstance(segment[0], str):
            parts.append(segment[0])
    return "".join(parts).strip()


def translate_to_chinese(text: str) -> str:
    source = text.strip()
    if not source:
        raise XhsSearchError("검색어를 입력해 주세요.")

    params = urllib.parse.urlencode(
        {"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": source}
    )
    try:
        translated = _parse_google_translation(_http_json(f"{_GOOGLE_TRANSLATE}?{params}"))
        if translated:
            return translated
    except Exception:
        pass

    params = urllib.parse.urlencode({"q": source, "langpair": "ko|zh-CN"})
    try:
        payload = _http_json(f"{_MYMEMORY_TRANSLATE}?{params}")
        translated = str((payload.get("responseData") or {}).get("translatedText") or "").strip()
        if translated:
            return translated
    except Exception:
        pass

    raise XhsSearchError(
        "자동 번역 서비스에 연결하지 못했습니다. 중국어 검색어 칸에 직접 입력한 뒤 검색해 주세요."
    )


def _find_browser() -> Path | None:
    candidates: list[Path] = []
    local = os.getenv("LOCALAPPDATA")
    program_files = [os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)")]
    if local:
        candidates.extend(
            [
                Path(local) / "Microsoft/Edge/Application/msedge.exe",
                Path(local) / "Google/Chrome/Application/chrome.exe",
            ]
        )
    for root in program_files:
        if root:
            candidates.extend(
                [
                    Path(root) / "Microsoft/Edge/Application/msedge.exe",
                    Path(root) / "Google/Chrome/Application/chrome.exe",
                ]
            )
    for command in ("msedge.exe", "chrome.exe", "msedge", "google-chrome", "chromium"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))
    return next((path for path in candidates if path.is_file()), None)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _browser_profile_dir() -> Path:
    local = os.getenv("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / ".cache"
    return base / "AVOCADOSS Downloader" / "xiaohongshu-browser"


def _json_get(url: str, timeout: float = 2.5) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


_EXTRACT_SCRIPT = r"""
(() => {
  const result = { items: [], loginRequired: false, href: location.href, title: document.title || '' };
  const bodyText = (document.body && document.body.innerText) ? document.body.innerText : '';
  result.loginRequired = /登录后查看|扫码登录|登录小红书|登录\/注册/.test(bodyText);
  let state = window.__INITIAL_STATE__ || {};
  let feeds = state && state.search ? state.search.feeds : null;
  if (feeds && typeof feeds === 'object') feeds = feeds._value ?? feeds.value ?? feeds;
  if (!Array.isArray(feeds)) feeds = [];
  const normalizeCover = (cover) => {
    if (!cover) return '';
    if (typeof cover === 'string') return cover;
    return cover.urlDefault || cover.urlPre || cover.url ||
      (Array.isArray(cover.urlList) ? cover.urlList[0] : '') || '';
  };
  for (const entry of feeds) {
    const card = entry && entry.noteCard;
    if (!card) continue;
    const id = String(entry.id || card.noteId || card.note_id || '');
    const token = String(entry.xsecToken || entry.xsec_token || '');
    if (!id) continue;
    const user = card.user || {};
    const interact = card.interactInfo || card.interact_info || {};
    const cover = normalizeCover(card.cover || card.imageList?.[0] || card.image_list?.[0]);
    const url = `https://www.xiaohongshu.com/explore/${encodeURIComponent(id)}?xsec_token=${encodeURIComponent(token)}&xsec_source=pc_search`;
    result.items.push({
      note_id: id,
      title: String(card.displayTitle || card.title || card.desc || '').trim(),
      author: String(user.nickname || user.nickName || user.name || '').trim(),
      url,
      thumbnail_url: String(cover || ''),
      likes: String(interact.likedCount ?? interact.liked_count ?? ''),
      collects: String(interact.collectedCount ?? interact.collected_count ?? ''),
      comments: String(interact.commentCount ?? interact.comment_count ?? ''),
      note_type: String(card.type || '').trim()
    });
  }
  if (result.items.length === 0) {
    const cards = [...document.querySelectorAll('section.note-item')];
    for (const card of cards) {
      const link = card.querySelector('a.cover') || card.querySelector('a[href*="/explore/"]');
      if (!link) continue;
      const href = link.href || '';
      const idMatch = href.match(/\/explore\/([^?/#]+)/);
      const id = idMatch ? idMatch[1] : '';
      const titleEl = card.querySelector('.title, .footer .title, [class*="title"]');
      const userEl = card.querySelector('.author .name, .username, [class*="name"]');
      const likeEl = card.querySelector('.like-wrapper .count, [class*="like"] [class*="count"]');
      const img = card.querySelector('img');
      result.items.push({
        note_id: id,
        title: titleEl ? titleEl.textContent.trim() : '',
        author: userEl ? userEl.textContent.trim() : '',
        url: href,
        thumbnail_url: img ? (img.currentSrc || img.src || '') : '',
        likes: likeEl ? likeEl.textContent.trim() : '',
        collects: '', comments: '', note_type: ''
      });
    }
  }
  return JSON.stringify(result);
})()
"""


class XiaohongshuBrowserSearch:
    """Uses a dedicated real Edge/Chrome profile and reads the rendered public search page via CDP."""

    def __init__(self) -> None:
        self.browser_path = _find_browser()
        self.process: subprocess.Popen | None = None
        self.port: int | None = None
        self.profile_dir = _browser_profile_dir()

    def _ensure_browser(self, url: str) -> None:
        if self.browser_path is None:
            raise XhsSearchError("Microsoft Edge 또는 Google Chrome을 찾지 못했습니다.")
        if self.process is not None and self.process.poll() is None and self.port:
            self._navigate_new_tab(url)
            return

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.port = _free_port()
        args = [
            str(self.browser_path),
            f"--remote-debugging-port={self.port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-features=TranslateUI",
            url,
        ]
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        self.process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        deadline = time.monotonic() + 12
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                _json_get(f"http://127.0.0.1:{self.port}/json/version")
                return
            except Exception as exc:
                last_error = exc
                time.sleep(0.25)
        raise XhsSearchError(f"검색 브라우저를 시작하지 못했습니다: {last_error}")

    def _navigate_new_tab(self, url: str) -> None:
        if not self.port:
            return
        encoded = urllib.parse.quote(url, safe="")
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/json/new?{encoded}",
            method="PUT",
        )
        try:
            with urllib.request.urlopen(request, timeout=3):
                return
        except Exception:
            pass

    def _search_target(self) -> dict[str, Any]:
        if not self.port:
            raise XhsSearchError("검색 브라우저 연결이 없습니다.")
        targets = _json_get(f"http://127.0.0.1:{self.port}/json/list")
        pages = [
            item for item in targets
            if item.get("type") == "page" and "xiaohongshu.com/search_result" in str(item.get("url") or "")
        ]
        if not pages:
            raise XhsSearchError("샤오홍슈 검색 페이지를 찾지 못했습니다.")
        return pages[0]

    def _evaluate(self, expression: str) -> Any:
        if websocket is None:
            raise XhsSearchError("검색 모듈(websocket-client)이 설치되지 않았습니다.")
        target = self._search_target()
        ws_url = str(target.get("webSocketDebuggerUrl") or "")
        if not ws_url:
            raise XhsSearchError("브라우저 디버깅 채널을 찾지 못했습니다.")
        ws = websocket.create_connection(ws_url, timeout=5, origin=f"http://127.0.0.1:{self.port}")
        try:
            request_id = 1
            ws.send(json.dumps({
                "id": request_id,
                "method": "Runtime.evaluate",
                "params": {"expression": expression, "returnByValue": True, "awaitPromise": True},
            }))
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                message = json.loads(ws.recv())
                if message.get("id") != request_id:
                    continue
                result = (((message.get("result") or {}).get("result") or {}).get("value"))
                return result
            raise XhsSearchError("브라우저 검색 결과 응답 시간이 초과되었습니다.")
        finally:
            ws.close()

    def search(self, keyword: str, limit: int = 20) -> list[XhsSearchItem]:
        keyword = keyword.strip()
        if not keyword:
            raise XhsSearchError("중국어 검색어가 비어 있습니다.")
        self._ensure_browser(build_search_url(keyword))
        deadline = time.monotonic() + 18
        latest: dict[str, Any] = {"items": []}
        while time.monotonic() < deadline:
            time.sleep(0.7)
            try:
                raw = self._evaluate(_EXTRACT_SCRIPT)
                latest = json.loads(raw) if isinstance(raw, str) else {}
            except Exception:
                continue
            items = latest.get("items") or []
            if items:
                return [XhsSearchItem(**item) for item in items[: max(1, min(limit, 40))]]
            if latest.get("loginRequired"):
                raise XhsLoginRequired(
                    "샤오홍슈가 검색 결과를 로그인 사용자에게만 보여주고 있습니다. "
                    "열린 Edge/Chrome 창에서 한 번 로그인한 뒤 다시 검색해 주세요."
                )
        raise XhsSearchError(
            "샤오홍슈 검색 결과를 읽지 못했습니다. 열린 검색 브라우저에서 페이지가 정상 표시되는지 확인한 뒤 다시 시도해 주세요."
        )

    def open_in_search_browser(self, url: str) -> bool:
        if self.process is None or self.process.poll() is not None or not self.port:
            return False
        self._navigate_new_tab(url)
        return True

    def close(self) -> None:
        # Keep the dedicated browser profile on disk so a one-time Xiaohongshu login persists.
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.process = None
        self.port = None
