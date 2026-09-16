from __future__ import annotations

import io
import queue
import threading
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from app_compact import CompactDownloaderApp
from xhs_search import (
    XhsLoginRequired,
    XhsSearchError,
    XhsSearchItem,
    XiaohongshuBrowserSearch,
    build_search_url,
    translate_to_chinese,
)

_XHS_THUMB_MAX_BYTES = 5 * 1024 * 1024
_XHS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)


class WorkspaceDownloaderApp(CompactDownloaderApp):
    """Downloader plus a physically separate Xiaohongshu research workspace."""

    def __init__(self) -> None:
        self.xhs_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.xhs_client = XiaohongshuBrowserSearch()
        self.xhs_items: list[XhsSearchItem] = []
        self.xhs_thumb_labels: list[tk.Label] = []
        self.xhs_thumb_images: dict[int, ImageTk.PhotoImage] = {}
        self.xhs_search_busy = False
        super().__init__()
        self.geometry("1180x760")
        self.minsize(940, 640)
        self._install_workspace_tabs()
        self.after(100, self._drain_xhs_events)

    def _install_workspace_tabs(self) -> None:
        root_children = list(self.winfo_children())
        if not root_children:
            return
        self.download_workspace = root_children[0]

        self.workspace_tabs = ttk.Frame(self, padding=(14, 7, 14, 0))
        self.workspace_tabs.pack(fill="x", before=self.download_workspace)
        self.download_tab_button = ttk.Button(
            self.workspace_tabs,
            text="다운로드",
            command=self._show_download_workspace,
        )
        self.download_tab_button.pack(side="left", ipadx=14, ipady=3)
        self.xhs_tab_button = ttk.Button(
            self.workspace_tabs,
            text="샤오홍슈 검색",
            command=self._show_xhs_workspace,
        )
        self.xhs_tab_button.pack(side="left", padx=(6, 0), ipadx=14, ipady=3)

        self.xhs_workspace = ttk.Frame(self, padding=(14, 10))
        self._build_xhs_workspace(self.xhs_workspace)
        self._show_download_workspace()

    def _show_download_workspace(self) -> None:
        if hasattr(self, "xhs_workspace"):
            self.xhs_workspace.pack_forget()
        if hasattr(self, "download_workspace") and not self.download_workspace.winfo_ismapped():
            self.download_workspace.pack(fill="both", expand=True)
        if hasattr(self, "download_tab_button"):
            self.download_tab_button.configure(state="disabled")
            self.xhs_tab_button.configure(state="normal")

    def _show_xhs_workspace(self) -> None:
        if hasattr(self, "download_workspace"):
            self.download_workspace.pack_forget()
        if hasattr(self, "xhs_workspace") and not self.xhs_workspace.winfo_ismapped():
            self.xhs_workspace.pack(fill="both", expand=True)
        self.xhs_tab_button.configure(state="disabled")
        self.download_tab_button.configure(state="normal")
        self.xhs_query_entry.focus_set()

    def _build_xhs_workspace(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent)
        header.pack(fill="x")
        header_left = ttk.Frame(header)
        header_left.pack(side="left", fill="x", expand=True)
        ttk.Label(header_left, text="샤오홍슈 검색", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            header_left,
            text="한국어 검색어를 중국어로 번역한 뒤 샤오홍슈의 실제 검색 결과를 읽어옵니다.",
            foreground="#666666",
        ).pack(anchor="w", pady=(1, 0))
        ttk.Label(
            header_left,
            text="검색은 별도 Edge/Chrome 세션을 사용합니다. 샤오홍슈가 요구하면 열린 창에서 한 번 로그인해 주세요.",
            foreground="#777777",
        ).pack(anchor="w", pady=(1, 0))

        search_box = ttk.LabelFrame(parent, text="검색어", padding=(10, 8))
        search_box.pack(fill="x", pady=(10, 7))
        search_box.columnconfigure(1, weight=1)

        self.xhs_query_var = tk.StringVar()
        self.xhs_chinese_var = tk.StringVar()
        self.xhs_status_var = tk.StringVar(value="한국어 키워드를 입력하고 '번역 후 검색'을 누르세요.")
        self.xhs_count_var = tk.StringVar(value="검색 전")

        ttk.Label(search_box, text="한국어", width=10).grid(row=0, column=0, sticky="w")
        self.xhs_query_entry = ttk.Entry(search_box, textvariable=self.xhs_query_var)
        self.xhs_query_entry.grid(row=0, column=1, sticky="ew", padx=(0, 7))
        self.xhs_auto_button = ttk.Button(search_box, text="번역 후 검색", command=self._xhs_translate_and_search)
        self.xhs_auto_button.grid(row=0, column=2, padx=(0, 5))
        ttk.Button(search_box, text="지우기", command=self._clear_xhs_search).grid(row=0, column=3)
        self.xhs_query_entry.bind("<Return>", lambda _event: self._xhs_translate_and_search())

        ttk.Label(search_box, text="중국어", width=10).grid(row=1, column=0, sticky="w", pady=(7, 0))
        self.xhs_chinese_entry = ttk.Entry(search_box, textvariable=self.xhs_chinese_var)
        self.xhs_chinese_entry.grid(row=1, column=1, sticky="ew", padx=(0, 7), pady=(7, 0))
        self.xhs_manual_button = ttk.Button(search_box, text="이 단어로 검색", command=self._xhs_search_manual)
        self.xhs_manual_button.grid(row=1, column=2, padx=(0, 5), pady=(7, 0))
        ttk.Button(search_box, text="검색 페이지 열기", command=self._open_xhs_search_page).grid(
            row=1, column=3, pady=(7, 0)
        )
        self.xhs_chinese_entry.bind("<Return>", lambda _event: self._xhs_search_manual())

        status_row = ttk.Frame(parent)
        status_row.pack(fill="x", pady=(0, 7))
        self.xhs_progress = ttk.Progressbar(status_row, mode="indeterminate", length=150)
        self.xhs_progress.pack(side="left")
        ttk.Label(status_row, textvariable=self.xhs_status_var, foreground="#555555").pack(
            side="left", fill="x", expand=True, padx=(8, 0)
        )
        ttk.Label(status_row, textvariable=self.xhs_count_var, foreground="#666666").pack(side="right")

        result_header = ttk.Frame(parent)
        result_header.pack(fill="x", pady=(0, 5))
        ttk.Label(result_header, text="검색 결과", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Label(
            result_header,
            text="제목 · 작성자 · 좋아요/저장/댓글 · 원문 링크",
            foreground="#777777",
        ).pack(side="right")

        result_border = ttk.Frame(parent)
        result_border.pack(fill="both", expand=True)
        self.xhs_canvas = tk.Canvas(result_border, highlightthickness=0, borderwidth=0)
        xhs_scroll = ttk.Scrollbar(result_border, orient="vertical", command=self.xhs_canvas.yview)
        self.xhs_canvas.configure(yscrollcommand=xhs_scroll.set)
        self.xhs_canvas.pack(side="left", fill="both", expand=True)
        xhs_scroll.pack(side="right", fill="y")
        self.xhs_results_frame = ttk.Frame(self.xhs_canvas)
        self.xhs_results_window = self.xhs_canvas.create_window((0, 0), window=self.xhs_results_frame, anchor="nw")
        self.xhs_results_frame.bind(
            "<Configure>", lambda _event: self.xhs_canvas.configure(scrollregion=self.xhs_canvas.bbox("all"))
        )
        self.xhs_canvas.bind(
            "<Configure>", lambda event: self.xhs_canvas.itemconfigure(self.xhs_results_window, width=event.width)
        )
        self.xhs_canvas.bind("<MouseWheel>", self._on_xhs_mousewheel)

        placeholder = ttk.Label(
            self.xhs_results_frame,
            text="검색 결과가 여기에 표시됩니다.",
            foreground="#777777",
            anchor="center",
        )
        placeholder.pack(fill="both", expand=True, pady=90)

    def _on_xhs_mousewheel(self, event: tk.Event) -> None:
        try:
            self.xhs_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            pass

    def _set_xhs_busy(self, busy: bool, text: str | None = None) -> None:
        self.xhs_search_busy = busy
        state = "disabled" if busy else "normal"
        self.xhs_auto_button.configure(state=state)
        self.xhs_manual_button.configure(state=state)
        if busy:
            self.xhs_progress.start(12)
        else:
            self.xhs_progress.stop()
            self.xhs_progress.configure(value=0)
        if text is not None:
            self.xhs_status_var.set(text)

    def _clear_xhs_results(self) -> None:
        for child in self.xhs_results_frame.winfo_children():
            child.destroy()
        self.xhs_items = []
        self.xhs_thumb_labels.clear()
        self.xhs_thumb_images.clear()
        self.xhs_count_var.set("검색 전")

    def _clear_xhs_search(self) -> None:
        if self.xhs_search_busy:
            return
        self.xhs_query_var.set("")
        self.xhs_chinese_var.set("")
        self._clear_xhs_results()
        self.xhs_status_var.set("한국어 키워드를 입력하고 '번역 후 검색'을 누르세요.")
        ttk.Label(
            self.xhs_results_frame,
            text="검색 결과가 여기에 표시됩니다.",
            foreground="#777777",
            anchor="center",
        ).pack(fill="both", expand=True, pady=90)
        self.xhs_query_entry.focus_set()

    def _xhs_translate_and_search(self) -> None:
        if self.xhs_search_busy:
            return
        source = self.xhs_query_var.get().strip()
        if not source:
            messagebox.showinfo("샤오홍슈 검색", "검색할 한국어 단어를 입력해 주세요.")
            return
        self._clear_xhs_results()
        self._set_xhs_busy(True, "중국어로 번역하고 있습니다…")
        threading.Thread(target=self._xhs_worker, args=(source, True), daemon=True).start()

    def _xhs_search_manual(self) -> None:
        if self.xhs_search_busy:
            return
        keyword = self.xhs_chinese_var.get().strip()
        if not keyword:
            messagebox.showinfo("샤오홍슈 검색", "중국어 검색어를 입력해 주세요.")
            return
        self._clear_xhs_results()
        self._set_xhs_busy(True, f"샤오홍슈에서 '{keyword}' 검색 중…")
        threading.Thread(target=self._xhs_worker, args=(keyword, False), daemon=True).start()

    def _xhs_worker(self, text: str, translate_first: bool) -> None:
        try:
            keyword = translate_to_chinese(text) if translate_first else text.strip()
            if translate_first:
                self.xhs_events.put(("translated", keyword))
            self.xhs_events.put(("status", f"샤오홍슈에서 '{keyword}' 검색 중…"))
            items = self.xhs_client.search(keyword, limit=20)
            self.xhs_events.put(("results", (keyword, items)))
        except XhsLoginRequired as exc:
            self.xhs_events.put(("login_required", exc))
        except Exception as exc:
            self.xhs_events.put(("error", exc))

    def _open_xhs_search_page(self) -> None:
        keyword = self.xhs_chinese_var.get().strip() or self.xhs_query_var.get().strip()
        if not keyword:
            messagebox.showinfo("샤오홍슈 검색", "검색어를 입력해 주세요.")
            return
        url = build_search_url(keyword)
        if not self.xhs_client.open_in_search_browser(url):
            webbrowser.open(url)

    def _render_xhs_results(self, keyword: str, items: list[XhsSearchItem]) -> None:
        self._clear_xhs_results()
        self.xhs_items = items
        self.xhs_count_var.set(f"{len(items)}개 결과")
        self.xhs_status_var.set(f"중국어 '{keyword}' 검색 완료")
        if not items:
            ttk.Label(self.xhs_results_frame, text="검색 결과가 없습니다.").pack(pady=80)
            return

        for index, item in enumerate(items):
            card = ttk.Frame(self.xhs_results_frame, padding=9, relief="solid", borderwidth=1)
            card.pack(fill="x", padx=(0, 4), pady=(0, 7))

            thumb = tk.Label(
                card,
                text="미리보기\n불러오는 중",
                width=17,
                height=7,
                bg="#f2f2f2",
                fg="#666666",
            )
            thumb.pack(side="left", padx=(0, 10))
            self.xhs_thumb_labels.append(thumb)

            info = ttk.Frame(card)
            info.pack(side="left", fill="both", expand=True)
            title = item.title or "제목 없음"
            ttk.Label(info, text=title, font=("Segoe UI", 10, "bold"), wraplength=650).pack(anchor="w")
            byline = item.author or "작성자 정보 없음"
            if item.note_type:
                byline += f" · {item.note_type}"
            ttk.Label(info, text=byline, foreground="#555555").pack(anchor="w", pady=(4, 0))

            metrics: list[str] = []
            if item.likes:
                metrics.append(f"좋아요 {item.likes}")
            if item.collects:
                metrics.append(f"저장 {item.collects}")
            if item.comments:
                metrics.append(f"댓글 {item.comments}")
            ttk.Label(
                info,
                text=" · ".join(metrics) if metrics else "공개 검색 결과",
                foreground="#777777",
            ).pack(anchor="w", pady=(3, 5))

            actions = ttk.Frame(info)
            actions.pack(fill="x", side="bottom")
            ttk.Button(actions, text="샤오홍슈에서 열기", command=lambda u=item.url: self._open_xhs_item(u)).pack(
                side="left"
            )
            ttk.Button(
                actions,
                text="다운로드 탭으로",
                command=lambda u=item.url: self._send_xhs_to_downloader(u),
            ).pack(side="left", padx=(6, 0))
            ttk.Button(actions, text="링크 복사", command=lambda u=item.url: self._copy_xhs_url(u)).pack(
                side="left", padx=(6, 0)
            )

            if item.thumbnail_url.startswith("https://"):
                threading.Thread(
                    target=self._xhs_thumb_worker,
                    args=(index, item.thumbnail_url),
                    daemon=True,
                ).start()
            else:
                thumb.configure(text="미리보기 없음")

    def _xhs_thumb_worker(self, index: int, url: str) -> None:
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": _XHS_UA, "Referer": "https://www.xiaohongshu.com/"},
            )
            with urllib.request.urlopen(request, timeout=18) as response:
                raw = response.read(_XHS_THUMB_MAX_BYTES + 1)
            if len(raw) > _XHS_THUMB_MAX_BYTES:
                raise ValueError("thumbnail too large")
            self.xhs_events.put(("thumb", (index, raw)))
        except Exception:
            self.xhs_events.put(("thumb_error", index))

    def _open_xhs_item(self, url: str) -> None:
        if not self.xhs_client.open_in_search_browser(url):
            webbrowser.open(url)

    def _copy_xhs_url(self, url: str) -> None:
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update_idletasks()
        self.xhs_status_var.set("샤오홍슈 원문 링크를 복사했습니다.")

    def _send_xhs_to_downloader(self, url: str) -> None:
        self.url_var.set(url)
        self._show_download_workspace()
        self.after(50, self.analyze)

    def _drain_xhs_events(self) -> None:
        try:
            while True:
                kind, payload = self.xhs_events.get_nowait()
                if kind == "translated":
                    self.xhs_chinese_var.set(str(payload))
                elif kind == "status":
                    self.xhs_status_var.set(str(payload))
                elif kind == "results":
                    keyword, items = payload
                    self._set_xhs_busy(False)
                    self._render_xhs_results(str(keyword), list(items))
                elif kind == "login_required":
                    self._set_xhs_busy(False, "샤오홍슈 로그인이 필요합니다.")
                    messagebox.showinfo(
                        "샤오홍슈 로그인",
                        f"{payload}\n\n로그인을 마친 뒤 같은 검색어로 다시 검색하면 됩니다.",
                    )
                elif kind == "error":
                    self._set_xhs_busy(False, "검색에 실패했습니다.")
                    messagebox.showerror("샤오홍슈 검색", str(payload))
                elif kind == "thumb":
                    index, raw = payload
                    if 0 <= index < len(self.xhs_thumb_labels):
                        image = Image.open(io.BytesIO(raw))
                        image.thumbnail((128, 108), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(image)
                        self.xhs_thumb_images[index] = photo
                        self.xhs_thumb_labels[index].configure(image=photo, text="", width=128, height=108)
                elif kind == "thumb_error":
                    index = int(payload)
                    if 0 <= index < len(self.xhs_thumb_labels):
                        self.xhs_thumb_labels[index].configure(text="미리보기 없음")
        except queue.Empty:
            pass
        except Exception as exc:
            self.xhs_status_var.set(f"결과 표시 오류: {exc}")
        finally:
            if self.winfo_exists():
                self.after(100, self._drain_xhs_events)

    def _on_close(self) -> None:
        try:
            self.xhs_client.close()
        finally:
            super()._on_close()


if __name__ == "__main__":
    WorkspaceDownloaderApp().mainloop()
