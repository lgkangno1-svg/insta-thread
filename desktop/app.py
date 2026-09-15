from __future__ import annotations

import io
import os
import queue
import sys
import threading
import tkinter as tk
import urllib.request
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from core import (
    API_BASE,
    APP_VERSION,
    ApiClient,
    ApiError,
    SUPPORTED_PLATFORMS,
    ReleaseInfo,
    assets_from_response,
    detect_platform,
    extract_supported_url,
    resource_path,
    schedule_windows_self_update,
)

_PREVIEW_MAX_BYTES = 6 * 1024 * 1024
_PREVIEW_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


class DownloaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"AVOCADOSS Downloader v{APP_VERSION}")
        self.geometry("920x780")
        self.minsize(780, 640)
        self.client = ApiClient(API_BASE)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.analysis: dict | None = None
        self.assets = []
        self.busy = False
        self.update_busy = False
        self.last_file: Path | None = None
        self.download_buttons: list[ttk.Button] = []
        self.preview_labels: list[tk.Label] = []
        self.preview_images: dict[int, ImageTk.PhotoImage] = {}

        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.platform_var = tk.StringVar(value="지원: YouTube · Instagram · Threads · Douyin · Xiaohongshu/RedNote")
        self.status_var = tk.StringVar(value="링크를 붙여넣고 분석을 누르세요.")
        self.title_var = tk.StringVar(value="")
        self.meta_var = tk.StringVar(value="")
        self.version_var = tk.StringVar(value=f"v{APP_VERSION}")

        self._configure_window()
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_events)
        self.after(250, self._try_clipboard)
        self.after(1400, lambda: self.check_updates(manual=False))

    def _configure_window(self) -> None:
        try:
            self.iconbitmap(default=str(resource_path("assets/app.ico")))
        except tk.TclError:
            pass
        try:
            style = ttk.Style(self)
            if "vista" in style.theme_names():
                style.theme_use("vista")
        except tk.TclError:
            pass

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        header_left = ttk.Frame(header)
        header_left.pack(side="left", fill="x", expand=True)
        ttk.Label(header_left, text="AVOCADOSS Downloader", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(header_left, text="공개 미디어 링크 전용 · 광고 없음 · 로그인/쿠키 접근 없음").pack(anchor="w", pady=(2, 0))
        header_right = ttk.Frame(header)
        header_right.pack(side="right", anchor="ne")
        ttk.Label(header_right, textvariable=self.version_var).pack(anchor="e")
        self.update_button = ttk.Button(header_right, text="업데이트 확인", command=lambda: self.check_updates(manual=True))
        self.update_button.pack(anchor="e", pady=(5, 0))

        ttk.Separator(outer).pack(fill="x", pady=(14, 16))

        ttk.Label(outer, text="링크 또는 공유 문구").pack(anchor="w")
        url_row = ttk.Frame(outer)
        url_row.pack(fill="x", pady=(6, 4))
        self.url_entry = ttk.Entry(url_row, textvariable=self.url_var)
        self.url_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(url_row, text="클립보드", command=self._paste_clipboard).pack(side="left", padx=(8, 0))
        ttk.Button(url_row, text="지우기", command=self._clear_url).pack(side="left", padx=(6, 0))
        self.url_entry.bind("<Return>", lambda _e: self.analyze())
        self.url_var.trace_add("write", lambda *_: self._update_platform_hint())
        ttk.Label(outer, textvariable=self.platform_var).pack(anchor="w", pady=(0, 14))

        ttk.Label(outer, text="저장 폴더").pack(anchor="w")
        folder_row = ttk.Frame(outer)
        folder_row.pack(fill="x", pady=(6, 14))
        ttk.Entry(folder_row, textvariable=self.folder_var).pack(side="left", fill="x", expand=True)
        ttk.Button(folder_row, text="폴더 선택", command=self._choose_folder).pack(side="left", padx=(8, 0))
        ttk.Button(folder_row, text="폴더 열기", command=self._open_download_folder).pack(side="left", padx=(6, 0))

        self.analyze_button = ttk.Button(outer, text="링크 분석", command=self.analyze)
        self.analyze_button.pack(fill="x", ipady=6)

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(12, 8))
        ttk.Label(outer, textvariable=self.status_var, wraplength=860).pack(anchor="w")

        ttk.Separator(outer).pack(fill="x", pady=14)
        ttk.Label(outer, textvariable=self.title_var, font=("Segoe UI", 12, "bold"), wraplength=860).pack(anchor="w")
        ttk.Label(outer, textvariable=self.meta_var).pack(anchor="w", pady=(3, 8))
        ttk.Label(outer, text="다운로드 옵션", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(2, 6))

        cards_border = ttk.Frame(outer)
        cards_border.pack(fill="both", expand=True)
        self.cards_canvas = tk.Canvas(cards_border, highlightthickness=0, borderwidth=0)
        cards_scroll = ttk.Scrollbar(cards_border, orient="vertical", command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=cards_scroll.set)
        self.cards_canvas.pack(side="left", fill="both", expand=True)
        cards_scroll.pack(side="right", fill="y")
        self.cards_frame = ttk.Frame(self.cards_canvas)
        self.cards_window = self.cards_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.cards_frame.bind("<Configure>", self._sync_scrollregion)
        self.cards_canvas.bind("<Configure>", self._sync_cards_width)
        self.cards_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        completed_row = ttk.Frame(outer)
        completed_row.pack(fill="x", pady=(10, 0))
        self.open_file_button = ttk.Button(completed_row, text="저장 파일 열기", command=self._open_last_file, state="disabled")
        self.open_file_button.pack(side="left", fill="x", expand=True)
        self.open_folder_button = ttk.Button(completed_row, text="저장 폴더 열기", command=self._open_download_folder)
        self.open_folder_button.pack(side="left", fill="x", expand=True, padx=(8, 0))

        ttk.Label(
            outer,
            text="본인이 소유하거나 저장 권한이 있는 공개 콘텐츠만 다운로드하세요.",
            foreground="#666666",
        ).pack(anchor="w", pady=(10, 0))

    def _sync_scrollregion(self, _event=None) -> None:
        self.cards_canvas.configure(scrollregion=self.cards_canvas.bbox("all"))

    def _sync_cards_width(self, event) -> None:
        self.cards_canvas.itemconfigure(self.cards_window, width=event.width)

    def _on_mousewheel(self, event) -> None:
        try:
            self.cards_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            pass

    def _set_progress_indeterminate(self) -> None:
        self.progress.stop()
        self.progress.configure(mode="indeterminate", maximum=100, value=0)
        self.progress.start(10)

    def _set_progress_percent(self, value: float) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100, value=max(0, min(100, value)))

    def _reset_progress(self) -> None:
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100, value=0)

    def _set_busy(self, busy: bool, text: str | None = None) -> None:
        self.busy = busy
        self.analyze_button.configure(state="disabled" if busy else "normal")
        for button in self.download_buttons:
            button.configure(state="disabled" if busy else "normal")
        if busy:
            self._set_progress_indeterminate()
        else:
            self._reset_progress()
        if text is not None:
            self.status_var.set(text)

    def _try_clipboard(self) -> None:
        if self.url_var.get().strip():
            return
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            return
        if extract_supported_url(text):
            self.url_var.set(text)

    def _paste_clipboard(self) -> None:
        try:
            text = self.clipboard_get().strip()
        except tk.TclError:
            messagebox.showinfo("클립보드", "클립보드에 텍스트가 없습니다.")
            return
        self.url_var.set(text)
        self.url_entry.focus_set()

    def _clear_cards(self) -> None:
        for child in self.cards_frame.winfo_children():
            child.destroy()
        self.download_buttons.clear()
        self.preview_labels.clear()
        self.preview_images.clear()

    def _clear_url(self) -> None:
        if self.busy:
            return
        self.url_var.set("")
        self.analysis = None
        self.assets = []
        self._clear_cards()
        self.title_var.set("")
        self.meta_var.set("")
        self.status_var.set("링크를 붙여넣고 분석을 누르세요.")
        self.url_entry.focus_set()

    def _choose_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get() or str(Path.home()))
        if chosen:
            self.folder_var.set(chosen)

    def _update_platform_hint(self) -> None:
        url = extract_supported_url(self.url_var.get())
        platform = detect_platform(url) if url else ""
        if platform:
            self.platform_var.set(f"감지됨: {SUPPORTED_PLATFORMS.get(platform, platform)}")
        else:
            self.platform_var.set("지원: YouTube · Instagram · Threads · Douyin · Xiaohongshu/RedNote")

    @staticmethod
    def _kind_name(kind: str) -> str:
        return {
            "video": "영상",
            "image": "이미지",
            "thumbnail": "썸네일/커버",
            "archive": "묶음 파일",
        }.get(kind, "미디어")

    @staticmethod
    def _orientation(width: int | None, height: int | None) -> str:
        if not width or not height:
            return ""
        ratio = width / height
        if 0.92 <= ratio <= 1.08:
            return "정사각형"
        return "가로" if ratio > 1 else "세로"

    def _render_cards(self, data: dict) -> None:
        self._clear_cards()
        raw_assets = data.get("assets") or []
        for index, asset in enumerate(self.assets):
            raw = raw_assets[index] if index < len(raw_assets) and isinstance(raw_assets[index], dict) else {}
            card = ttk.Frame(self.cards_frame, padding=8, relief="solid", borderwidth=1)
            card.pack(fill="x", pady=(0, 8), padx=(0, 4))

            preview = tk.Label(
                card,
                text="미리보기\n불러오는 중",
                width=16,
                height=6,
                bg="#f2f2f2",
                fg="#666666",
                relief="flat",
            )
            preview.pack(side="left", padx=(0, 12))
            self.preview_labels.append(preview)

            info = ttk.Frame(card)
            info.pack(side="left", fill="both", expand=True)
            ttk.Label(info, text=asset.label or self._kind_name(asset.kind), font=("Segoe UI", 11, "bold")).pack(anchor="w")
            orientation = self._orientation(asset.width, asset.height)
            detail_parts = [self._kind_name(asset.kind)]
            if asset.ext:
                detail_parts.append(asset.ext.upper())
            if asset.width and asset.height:
                detail_parts.append(f"{asset.width}×{asset.height}")
            if orientation:
                detail_parts.append(orientation)
            ttk.Label(info, text=" · ".join(detail_parts)).pack(anchor="w", pady=(4, 0))
            hint = {
                "video": "게시물 영상 파일",
                "image": "게시물 원본 이미지",
                "thumbnail": "영상/게시물의 커버 이미지",
                "archive": "여러 이미지를 한 번에 저장",
            }.get(asset.kind, "다운로드 가능한 미디어")
            ttk.Label(info, text=hint, foreground="#666666").pack(anchor="w", pady=(3, 0))

            button = ttk.Button(card, text="다운로드", command=lambda i=index: self.download_index(i))
            button.pack(side="right", padx=(12, 0), ipadx=8, ipady=4)
            self.download_buttons.append(button)

            preview_url = str(raw.get("preview_url") or "")
            if preview_url.startswith("https://"):
                threading.Thread(target=self._preview_worker, args=(index, preview_url), daemon=True).start()
            else:
                preview.configure(text="미리보기 없음")

    def _preview_worker(self, index: int, url: str) -> None:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": _PREVIEW_UA})
            with urllib.request.urlopen(request, timeout=20) as response:
                length = response.headers.get("Content-Length")
                if length and length.isdigit() and int(length) > _PREVIEW_MAX_BYTES:
                    raise ValueError("preview too large")
                raw = response.read(_PREVIEW_MAX_BYTES + 1)
                if len(raw) > _PREVIEW_MAX_BYTES:
                    raise ValueError("preview too large")
            self.events.put(("preview", (index, raw)))
        except Exception:
            self.events.put(("preview_error", index))

    def analyze(self) -> None:
        if self.busy:
            return
        url = extract_supported_url(self.url_var.get())
        if not url:
            messagebox.showwarning("지원하지 않는 링크", "지원 플랫폼의 공개 링크를 입력해 주세요.")
            return
        self.url_var.set(url)
        self.assets = []
        self.analysis = None
        self._clear_cards()
        self.title_var.set("")
        self.meta_var.set("")
        self._set_busy(True, "링크를 분석하고 있습니다…")
        threading.Thread(target=self._analyze_worker, args=(url,), daemon=True).start()

    def _analyze_worker(self, url: str) -> None:
        try:
            data = self.client.analyze(url)
            assets = assets_from_response(data)
            if not data.get("analysis_token"):
                raise ApiError("서버가 다운로드 토큰을 발급하지 않았습니다. 다시 분석해 주세요.")
            if not assets:
                raise ApiError("다운로드 가능한 공개 미디어를 찾지 못했습니다.")
            self.events.put(("analysis", (data, assets)))
        except Exception as exc:
            self.events.put(("error", exc))

    def download_index(self, index: int) -> None:
        if self.busy or not self.analysis or not self.assets or index < 0 or index >= len(self.assets):
            return
        folder = Path(self.folder_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("저장 폴더", f"저장 폴더를 사용할 수 없습니다.\n\n{exc}")
            return

        asset = self.assets[index]
        source_url = str(self.analysis.get("source_url") or self.url_var.get())
        token = str(self.analysis.get("analysis_token") or "")
        self.last_file = None
        self.open_file_button.configure(state="disabled")
        self._set_busy(True, f"{asset.label} 파일을 준비하고 있습니다…")
        threading.Thread(target=self._download_worker, args=(source_url, token, asset, folder), daemon=True).start()

    def _download_worker(self, url: str, token: str, asset, folder: Path) -> None:
        try:
            job_id = self.client.create_job(url, asset.id, token)
            download_url = self.client.wait_until_ready(
                job_id,
                progress=lambda state: self.events.put(
                    ("status", "파일 변환/준비 중…" if state == "processing" else "다운로드 대기 중…")
                ),
            )
            target = self.client.download_file(
                download_url,
                folder,
                progress=lambda received, total: self.events.put(("bytes", (received, total))),
            )
            self.events.put(("downloaded", target))
        except Exception as exc:
            self.events.put(("error", exc))

    def _open_last_file(self) -> None:
        if not self.last_file or not self.last_file.exists():
            messagebox.showinfo("파일 열기", "최근에 저장한 파일을 찾을 수 없습니다.")
            return
        try:
            os.startfile(str(self.last_file))  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("파일 열기", str(exc))

    def _open_download_folder(self) -> None:
        folder = Path(self.folder_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder))  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("폴더 열기", str(exc))

    def check_updates(self, manual: bool = True) -> None:
        if self.update_busy:
            if manual:
                messagebox.showinfo("업데이트", "이미 업데이트를 확인하고 있습니다.")
            return
        self.update_busy = True
        self.update_button.configure(state="disabled")
        if manual:
            self.status_var.set("새 버전을 확인하고 있습니다…")
        threading.Thread(target=self._update_check_worker, args=(manual,), daemon=True).start()

    def _update_check_worker(self, manual: bool) -> None:
        try:
            release = self.client.check_for_update(APP_VERSION)
            self.events.put(("update_check", (release, manual)))
        except Exception as exc:
            self.events.put(("update_error", (exc, manual)))

    def _start_update_download(self, release: ReleaseInfo) -> None:
        self.update_busy = True
        self.update_button.configure(state="disabled")
        self.status_var.set(f"v{release.version} 업데이트를 다운로드하고 검증하고 있습니다…")
        threading.Thread(target=self._update_download_worker, args=(release,), daemon=True).start()

    def _update_download_worker(self, release: ReleaseInfo) -> None:
        try:
            path = self.client.download_update(
                release,
                progress=lambda received, total: self.events.put(("update_bytes", (received, total))),
            )
            self.events.put(("update_ready", (release, path)))
        except Exception as exc:
            self.events.put(("update_install_error", (exc, release)))

    def _handle_update_ready(self, release: ReleaseInfo, path: Path) -> None:
        self.update_busy = False
        self.update_button.configure(state="normal")
        self._reset_progress()
        if not getattr(sys, "frozen", False) or os.name != "nt":
            self.status_var.set(f"v{release.version} 업데이트 다운로드 완료.")
            webbrowser.open(release.page_url)
            return
        if not messagebox.askyesno(
            "업데이트 준비 완료",
            f"AVOCADOSS Downloader v{release.version}을(를) 검증했습니다.\n\n"
            "지금 프로그램을 종료하고 새 버전으로 교체한 뒤 다시 실행할까요?",
        ):
            self.status_var.set(f"v{release.version} 업데이트가 임시 폴더에 준비되었습니다.")
            return
        try:
            schedule_windows_self_update(path, Path(sys.executable), os.getpid())
        except Exception as exc:
            messagebox.showerror(
                "자동 업데이트",
                f"자동 교체를 시작하지 못했습니다.\n\n{exc}\n\n릴리스 페이지를 엽니다.",
            )
            webbrowser.open(release.page_url)
            return
        self.destroy()

    def _on_close(self) -> None:
        if self.busy and not messagebox.askyesno("종료", "작업이 진행 중입니다. 프로그램을 종료할까요?"):
            return
        self.destroy()

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "analysis":
                    data, assets = payload
                    self.analysis = data
                    self.assets = assets
                    self.title_var.set(str(data.get("title") or "공개 미디어"))
                    platform = str(data.get("platform") or "")
                    author = str(data.get("author") or "")
                    self.meta_var.set(" · ".join(x for x in [author, SUPPORTED_PLATFORMS.get(platform, platform)] if x))
                    self._render_cards(data)
                    self._set_busy(False, f"{len(assets)}개 다운로드 옵션을 찾았습니다. 미리보기를 보고 원하는 항목을 다운로드하세요.")
                elif kind == "preview":
                    index, raw = payload
                    if index < len(self.preview_labels):
                        try:
                            image = Image.open(io.BytesIO(raw))
                            image.thumbnail((128, 96), Image.Resampling.LANCZOS)
                            if image.mode not in {"RGB", "RGBA"}:
                                image = image.convert("RGB")
                            photo = ImageTk.PhotoImage(image)
                            self.preview_images[index] = photo
                            self.preview_labels[index].configure(image=photo, text="", width=128, height=96)
                        except Exception:
                            self.preview_labels[index].configure(text="미리보기 실패")
                elif kind == "preview_error":
                    index = int(payload)
                    if index < len(self.preview_labels):
                        self.preview_labels[index].configure(text="미리보기 없음")
                elif kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "bytes":
                    received, total = payload
                    if total:
                        pct = min(100, received * 100 / total)
                        self._set_progress_percent(pct)
                        self.status_var.set(f"파일 저장 중… {pct:.0f}%")
                    else:
                        self.status_var.set(f"파일 저장 중… {received / 1024 / 1024:.1f} MB")
                elif kind == "downloaded":
                    self.last_file = Path(payload)
                    self._set_busy(False, f"저장 완료: {payload}")
                    self.open_file_button.configure(state="normal")
                    if messagebox.askyesno("다운로드 완료", f"파일을 저장했습니다.\n\n{payload}\n\n저장 폴더를 열까요?"):
                        self._open_download_folder()
                elif kind == "error":
                    self._set_busy(False, "오류가 발생했습니다.")
                    messagebox.showerror("AVOCADOSS Downloader", str(payload))
                elif kind == "update_check":
                    release, manual = payload
                    self.update_busy = False
                    self.update_button.configure(state="normal")
                    if release:
                        yes = messagebox.askyesno(
                            "새 버전",
                            f"새 버전 v{release.version}이 있습니다.\n현재 버전: v{APP_VERSION}\n\n"
                            "SHA-256 검증 후 업데이트를 다운로드할까요?",
                        )
                        if yes:
                            self._start_update_download(release)
                    elif manual:
                        self.status_var.set(f"현재 v{APP_VERSION}이 최신 버전입니다.")
                        messagebox.showinfo("업데이트", f"현재 v{APP_VERSION}이 최신 버전입니다.")
                elif kind == "update_error":
                    exc, manual = payload
                    self.update_busy = False
                    self.update_button.configure(state="normal")
                    if manual:
                        messagebox.showerror("업데이트 확인", str(exc))
                elif kind == "update_bytes":
                    received, total = payload
                    if total:
                        pct = min(100, received * 100 / total)
                        self._set_progress_percent(pct)
                        self.status_var.set(f"업데이트 다운로드 중… {pct:.0f}%")
                    else:
                        self.status_var.set(f"업데이트 다운로드 중… {received / 1024 / 1024:.1f} MB")
                elif kind == "update_ready":
                    release, path = payload
                    self._handle_update_ready(release, Path(path))
                elif kind == "update_install_error":
                    exc, release = payload
                    self.update_busy = False
                    self.update_button.configure(state="normal")
                    self._reset_progress()
                    messagebox.showerror("업데이트", str(exc))
                    if messagebox.askyesno("업데이트", "릴리스 페이지를 열까요?"):
                        webbrowser.open(release.page_url)
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._drain_events)


if __name__ == "__main__":
    DownloaderApp().mainloop()
