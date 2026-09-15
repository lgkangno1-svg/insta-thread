from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core import API_BASE, ApiClient, ApiError, SUPPORTED_PLATFORMS, assets_from_response, detect_platform, extract_supported_url


class DownloaderApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("AVOCADOSS Downloader")
        self.geometry("760x610")
        self.minsize(680, 540)
        self.client = ApiClient(API_BASE)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.analysis: dict | None = None
        self.assets = []
        self.busy = False

        self.url_var = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.platform_var = tk.StringVar(value="지원: YouTube · Instagram · Threads · Douyin · Xiaohongshu/RedNote")
        self.status_var = tk.StringVar(value="링크를 붙여넣고 분석을 누르세요.")
        self.title_var = tk.StringVar(value="")
        self.meta_var = tk.StringVar(value="")

        self._build_ui()
        self.after(100, self._drain_events)
        self.after(250, self._try_clipboard)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="AVOCADOSS Downloader", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text="공개 미디어 링크 전용 · 광고 없음 · 로그인/쿠키 접근 없음").pack(anchor="w", pady=(2, 18))

        ttk.Label(outer, text="링크 또는 공유 문구").pack(anchor="w")
        url_row = ttk.Frame(outer)
        url_row.pack(fill="x", pady=(6, 4))
        self.url_entry = ttk.Entry(url_row, textvariable=self.url_var)
        self.url_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(url_row, text="클립보드", command=self._paste_clipboard).pack(side="left", padx=(8, 0))
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
        ttk.Label(outer, textvariable=self.status_var, wraplength=700).pack(anchor="w")

        ttk.Separator(outer).pack(fill="x", pady=16)
        ttk.Label(outer, textvariable=self.title_var, font=("Segoe UI", 12, "bold"), wraplength=700).pack(anchor="w")
        ttk.Label(outer, textvariable=self.meta_var).pack(anchor="w", pady=(3, 8))

        list_frame = ttk.Frame(outer)
        list_frame.pack(fill="both", expand=True)
        self.asset_list = tk.Listbox(list_frame, activestyle="dotbox", font=("Segoe UI", 10), height=10)
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.asset_list.yview)
        self.asset_list.configure(yscrollcommand=scroll.set)
        self.asset_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.asset_list.bind("<Double-Button-1>", lambda _e: self.download_selected())

        self.download_button = ttk.Button(outer, text="선택 항목 다운로드", command=self.download_selected, state="disabled")
        self.download_button.pack(fill="x", pady=(12, 0), ipady=6)

        ttk.Label(
            outer,
            text="본인이 소유하거나 저장 권한이 있는 공개 콘텐츠만 다운로드하세요.",
            foreground="#666666",
        ).pack(anchor="w", pady=(12, 0))

    def _set_busy(self, busy: bool, text: str | None = None) -> None:
        self.busy = busy
        self.analyze_button.configure(state="disabled" if busy else "normal")
        self.download_button.configure(state="disabled" if busy or not self.assets else "normal")
        if busy:
            self.progress.start(10)
        else:
            self.progress.stop()
        if text is not None:
            self.status_var.set(text)

    def _try_clipboard(self) -> None:
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
        index = int(selection[0])
        asset = self.assets[index]
        folder = Path(self.folder_var.get()).expanduser()
        source_url = str(self.analysis.get("source_url") or self.url_var.get())
        token = str(self.analysis.get("analysis_token") or "")
        self._set_busy(True, "서버에서 파일을 준비하고 있습니다…")
        threading.Thread(target=self._download_worker, args=(source_url, token, asset, folder), daemon=True).start()

    def _download_worker(self, url: str, token: str, asset, folder: Path) -> None:
        try:
            job_id = self.client.create_job(url, asset.id, token)
            download_url = self.client.wait_until_ready(
                job_id,
                progress=lambda state: self.events.put(("status", "파일 변환/준비 중…" if state == "processing" else "다운로드 대기 중…")),
            )
            target = self.client.download_file(
                download_url,
                folder,
                progress=lambda received, total: self.events.put(("bytes", (received, total))),
            )
            self.events.put(("downloaded", target))
        except Exception as exc:
            self.events.put(("error", exc))

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
                        pct = min(100, int(received * 100 / total))
                        self.status_var.set(f"파일 저장 중… {pct}%")
                    else:
                        self.status_var.set(f"파일 저장 중… {received / 1024 / 1024:.1f} MB")
                elif kind == "downloaded":
                    self._set_busy(False, f"저장 완료: {payload}")
                    messagebox.showinfo("다운로드 완료", f"파일을 저장했습니다.\n\n{payload}")
                elif kind == "error":
                    self._set_busy(False, "오류가 발생했습니다.")
                    messagebox.showerror("AVOCADOSS Downloader", str(payload))
        except queue.Empty:
            pass
        finally:
            self.after(100, self._drain_events)


if __name__ == "__main__":
    DownloaderApp().mainloop()
