from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

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


class DownloaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"AVOCADOSS Downloader v{APP_VERSION}")
        self.geometry("800x680")
        self.minsize(700, 570)
        self.client = ApiClient(API_BASE)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.analysis: dict | None = None
        self.assets = []
        self.busy = False
        self.update_busy = False
        self.last_file: Path | None = None

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

        self.analyze_button = ttk.Button(outer, text="링크 분석", command=self.analyze)
        self.analyze_button.pack(fill="x", ipady=6)

        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(12, 8))
        ttk.Label(outer, textvariable=self.status_var, wraplength=750).pack(anchor="w")

        ttk.Separator(outer).pack(fill="x", pady=16)
        ttk.Label(outer, textvariable=self.title_var, font=("Segoe UI", 12, "bold"), wraplength=750).pack(anchor="w")
        ttk.Label(outer, textvariable=self.meta_var).pack(anchor="w", pady=(3, 8))

        list_frame = ttk.Frame(outer)
        list_frame.pack(fill="both", expand=True)
        self.asset_list = tk.Listbox(
            list_frame,
            activestyle="dotbox",
            font=("Segoe UI", 10),
            height=10,
            selectmode=tk.SINGLE,
            exportselection=False,
        )
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.asset_list.yview)
        self.asset_list.configure(yscrollcommand=scroll.set)
        self.asset_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.asset_list.bind("<Double-Button-1>", lambda _e: self.download_selected())

        self.download_button = ttk.Button(outer, text="선택 항목 다운로드", command=self.download_selected, state="disabled")
        self.download_button.pack(fill="x", pady=(12, 0), ipady=6)

        completed_row = ttk.Frame(outer)
        completed_row.pack(fill="x", pady=(8, 0))
        self.open_file_button = ttk.Button(completed_row, text="저장 파일 열기", command=self._open_last_file, state="disabled")
        self.open_file_button.pack(side="left", fill="x", expand=True)
        self.open_folder_button = ttk.Button(completed_row, text="저장 폴더 열기", command=self._open_download_folder)
        self.open_folder_button.pack(side="left", fill="x", expand=True, padx=(8, 0))

        ttk.Label(
            outer,
            text="본인이 소유하거나 저장 권한이 있는 공개 콘텐츠만 다운로드하세요.",
            foreground="#666666",
        ).pack(anchor="w", pady=(12, 0))

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
        self.download_button.configure(state="disabled" if busy or not self.assets else "normal")
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

    def _clear_url(self) -> None:
        if self.busy:
            return
        self.url_var.set("")
        self.analysis = None
        self.assets = []
        self.asset_list.delete(0, tk.END)
        self.title_var.set("")
        self.meta_var.set("")
        self.status_var.set("링크를 붙여넣고 분석을 누르세요.")
        self.download_button.configure(state="disabled")
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

    def analyze(self) -> None:
        if self.busy:
            return
        url = extract_supported_url(self.url_var.get())
        if not url:
            messagebox.showwarning("지원하지 않는 링크", "지원 플랫폼의 공개 링크를 입력해 주세요.")
            return
        self.url_var.set(url)
        self.asset_list.delete(0, tk.END)
        self.assets = []
        self.analysis = None
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

    def download_selected(self) -> None:
        if self.busy or not self.analysis or not self.assets:
            return
        selection = self.asset_list.curselection()
        if not selection:
            messagebox.showinfo("파일 선택", "다운로드할 항목을 선택해 주세요.")
            return
        folder = Path(self.folder_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("저장 폴더", f"저장 폴더를 사용할 수 없습니다.\n\n{exc}")
            return

        index = int(selection[0])
        asset = self.assets[index]
        source_url = str(self.analysis.get("source_url") or self.url_var.get())
        token = str(self.analysis.get("analysis_token") or "")
        self.last_file = None
        self.open_file_button.configure(state="disabled")
        self._set_busy(True, "서버에서 파일을 준비하고 있습니다…")
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
        if not folder.exists():
            messagebox.showinfo("폴더 열기", "저장 폴더가 아직 존재하지 않습니다.")
            return
        try:
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
                    for asset in assets:
                        self.asset_list.insert(tk.END, asset.display)
                    self.asset_list.selection_set(0)
                    self._set_busy(False, f"{len(assets)}개 다운로드 옵션을 찾았습니다.")
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
                    messagebox.showinfo("다운로드 완료", f"파일을 저장했습니다.\n\n{payload}")
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
