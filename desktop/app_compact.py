from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from app_enhanced import EnhancedDownloaderApp
from desktop_extras import primary_asset_indices


class CompactDownloaderApp(EnhancedDownloaderApp):
    """Space-efficient desktop UI focused on preview-first downloading."""

    CARD_COLUMNS = 2
    POST_PREVIEW_ROWS = 4

    def __init__(self) -> None:
        super().__init__()
        self.geometry("1080x720")
        self.minsize(900, 600)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=(14, 10))
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x")
        header_left = ttk.Frame(header)
        header_left.pack(side="left", fill="x", expand=True)
        ttk.Label(header_left, text="AVOCADOSS Downloader", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(
            header_left,
            text="공개 미디어 링크 전용 · 광고 없음 · 로그인/쿠키 접근 없음",
            foreground="#666666",
        ).pack(anchor="w", pady=(1, 0))

        header_right = ttk.Frame(header)
        header_right.pack(side="right", anchor="ne")
        ttk.Label(header_right, textvariable=self.version_var).pack(side="left", padx=(0, 8))
        self.update_button = ttk.Button(
            header_right,
            text="업데이트 확인",
            command=lambda: self.check_updates(manual=True),
        )
        self.update_button.pack(side="left")

        ttk.Separator(outer).pack(fill="x", pady=(7, 7))

        top = ttk.Frame(outer)
        top.pack(fill="x")
        top.columnconfigure(0, weight=3)
        top.columnconfigure(1, weight=2)

        controls = ttk.LabelFrame(top, text="빠른 입력", padding=(10, 7))
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="링크", width=8).grid(row=0, column=0, sticky="w")
        self.url_entry = ttk.Entry(controls, textvariable=self.url_var)
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 6))
        ttk.Button(controls, text="붙여넣기", command=self._paste_clipboard, width=9).grid(row=0, column=2)
        ttk.Button(controls, text="지우기", command=self._clear_url, width=7).grid(row=0, column=3, padx=(5, 0))
        self.url_entry.bind("<Return>", lambda _e: self.analyze())
        self.url_var.trace_add("write", lambda *_: self._update_platform_hint())

        ttk.Label(controls, text="저장", width=8).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(controls, textvariable=self.folder_var).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(0, 6),
            pady=(6, 0),
        )
        ttk.Button(controls, text="폴더 선택", command=self._choose_folder, width=9).grid(
            row=1,
            column=2,
            pady=(6, 0),
        )
        ttk.Button(controls, text="열기", command=self._open_download_folder, width=7).grid(
            row=1,
            column=3,
            padx=(5, 0),
            pady=(6, 0),
        )

        control_bottom = ttk.Frame(controls)
        control_bottom.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(7, 0))
        control_bottom.columnconfigure(1, weight=1)
        self.analyze_button = ttk.Button(control_bottom, text="링크 분석", command=self.analyze, width=16)
        self.analyze_button.grid(row=0, column=0, sticky="w", ipady=2)
        ttk.Label(control_bottom, textvariable=self.platform_var, foreground="#666666").grid(
            row=0,
            column=1,
            sticky="w",
            padx=(10, 0),
        )

        post = ttk.LabelFrame(top, text="게시물 본문", padding=(8, 6))
        post.grid(row=0, column=1, sticky="nsew")
        post.columnconfigure(0, weight=1)
        post.rowconfigure(1, weight=1)
        ttk.Label(post, textvariable=self.meta_var, foreground="#666666").grid(row=0, column=0, sticky="ew")

        post_body = ttk.Frame(post)
        post_body.grid(row=1, column=0, sticky="nsew", pady=(4, 4))
        post_body.columnconfigure(0, weight=1)
        post_body.rowconfigure(0, weight=1)
        self.post_text = tk.Text(
            post_body,
            height=self.POST_PREVIEW_ROWS,
            wrap="word",
            font=("Segoe UI", 10),
            relief="solid",
            borderwidth=1,
            padx=5,
            pady=4,
            undo=False,
            exportselection=True,
        )
        post_scroll = ttk.Scrollbar(post_body, orient="vertical", command=self.post_text.yview)
        self.post_text.configure(yscrollcommand=post_scroll.set, state="disabled")
        self.post_text.grid(row=0, column=0, sticky="nsew")
        post_scroll.grid(row=0, column=1, sticky="ns")
        self.post_text.bind("<Control-a>", self._select_all_post_text)
        self.post_text.bind("<Control-A>", self._select_all_post_text)

        post_actions = ttk.Frame(post)
        post_actions.grid(row=2, column=0, sticky="ew")
        self.result_count_var = tk.StringVar(value="아직 분석하지 않음")
        ttk.Label(post_actions, textvariable=self.result_count_var, foreground="#666666").pack(side="left")
        ttk.Button(post_actions, text="본문 전체 보기", command=self._show_post_text).pack(side="right")
        ttk.Button(post_actions, text="본문 전체 복사", command=self._copy_post_text).pack(side="right", padx=(0, 5))
        self.title_var.trace_add("write", self._sync_post_preview)
        self._sync_post_preview()

        status = ttk.Frame(outer)
        status.pack(fill="x", pady=(5, 4))
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=150)
        self.progress.pack(side="left", fill="x")
        ttk.Label(status, textvariable=self.status_var, wraplength=820).pack(
            side="left",
            fill="x",
            expand=True,
            padx=(8, 0),
        )

        self.quick_actions = ttk.Frame(outer)
        self.quick_actions.pack(fill="x", pady=(0, 5))

        options_header = ttk.Frame(outer)
        options_header.pack(fill="x", pady=(0, 4))
        ttk.Label(options_header, text="다운로드 옵션", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Label(
            options_header,
            text="미리보기를 보고 필요한 콘텐츠를 바로 다운로드하세요.",
            foreground="#666666",
        ).pack(side="right")

        cards_border = ttk.Frame(outer)
        cards_border.pack(fill="both", expand=True)
        self.cards_canvas = tk.Canvas(cards_border, highlightthickness=0, borderwidth=0)
        cards_scroll = ttk.Scrollbar(cards_border, orient="vertical", command=self.cards_canvas.yview)
        self.cards_canvas.configure(yscrollcommand=cards_scroll.set)
        self.cards_canvas.pack(side="left", fill="both", expand=True)
        cards_scroll.pack(side="right", fill="y")
        self.cards_frame = ttk.Frame(self.cards_canvas)
        for column in range(self.CARD_COLUMNS):
            self.cards_frame.columnconfigure(column, weight=1, uniform="media-card")
        self.cards_window = self.cards_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.cards_frame.bind("<Configure>", self._sync_scrollregion)
        self.cards_canvas.bind("<Configure>", self._sync_cards_width)
        self.cards_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        completed_row = ttk.Frame(outer)
        completed_row.pack(fill="x", pady=(6, 0))
        self.open_file_button = ttk.Button(
            completed_row,
            text="최근 저장 파일 열기",
            command=self._open_last_file,
            state="disabled",
        )
        self.open_file_button.pack(side="left", fill="x", expand=True)
        self.open_folder_button = ttk.Button(
            completed_row,
            text="저장 폴더 열기",
            command=self._open_download_folder,
        )
        self.open_folder_button.pack(side="left", fill="x", expand=True, padx=(7, 0))

        ttk.Label(
            outer,
            text="본인이 소유하거나 저장 권한이 있는 공개 콘텐츠만 다운로드하세요.",
            foreground="#777777",
        ).pack(anchor="w", pady=(5, 0))

    def _install_batch_controls(self) -> None:
        self.quick_download_button = ttk.Button(
            self.quick_actions,
            text="대표 영상 바로 다운로드",
            command=self._download_primary,
            state="disabled",
        )
        self.quick_download_button.pack(side="left", fill="x", expand=True)

        self.download_all_button = ttk.Button(
            self.quick_actions,
            text="게시물 전체 다운로드",
            command=self.download_all,
            state="disabled",
        )
        self.download_all_button.pack(side="left", fill="x", expand=True, padx=(7, 0))

        self.retry_failed_button = ttk.Button(
            self.quick_actions,
            text="실패 항목 다시 받기",
            command=self.retry_failed,
            state="disabled",
        )
        self.retry_failed_button.pack(side="left", fill="x", expand=True, padx=(7, 0))

    def _sync_post_preview(self, *_args: object) -> None:
        widget = getattr(self, "post_text", None)
        if widget is None:
            return
        body = self.title_var.get().strip()
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if body:
            widget.insert("1.0", body)
        widget.configure(state="disabled")
        widget.yview_moveto(0.0)

    def _select_all_post_text(self, event: tk.Event | None = None) -> str:
        widget = event.widget if event is not None else getattr(self, "post_text", None)
        if isinstance(widget, tk.Text):
            widget.tag_add("sel", "1.0", "end-1c")
            widget.mark_set("insert", "1.0")
            widget.see("1.0")
        return "break"

    def _copy_post_text(self) -> None:
        text = self.title_var.get().strip()
        if not text:
            messagebox.showinfo("본문 복사", "분석된 게시물 본문이 없습니다.")
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update_idletasks()
        self.status_var.set("게시물 본문 전체를 클립보드에 복사했습니다.")

    def _show_post_text(self) -> None:
        text = self.title_var.get().strip()
        meta = self.meta_var.get().strip()
        if not text:
            messagebox.showinfo("게시물 본문", "분석된 게시물 본문이 없습니다.")
            return

        window = tk.Toplevel(self)
        window.title("게시물 본문")
        window.geometry("680x520")
        window.minsize(480, 320)
        window.transient(self)

        outer = ttk.Frame(window, padding=10)
        outer.pack(fill="both", expand=True)
        if meta:
            ttk.Label(outer, text=meta, foreground="#666666").pack(anchor="w", pady=(0, 6))

        body_frame = ttk.Frame(outer)
        body_frame.pack(fill="both", expand=True)
        full_text = tk.Text(body_frame, wrap="word", font=("Segoe UI", 10), padx=8, pady=8)
        full_scroll = ttk.Scrollbar(body_frame, orient="vertical", command=full_text.yview)
        full_text.configure(yscrollcommand=full_scroll.set)
        full_text.pack(side="left", fill="both", expand=True)
        full_scroll.pack(side="right", fill="y")
        full_text.insert("1.0", text)
        full_text.configure(state="disabled")
        full_text.bind("<Control-a>", self._select_all_post_text)
        full_text.bind("<Control-A>", self._select_all_post_text)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(8, 0))
        ttk.Button(actions, text="전체 복사", command=self._copy_post_text).pack(side="right")
        ttk.Button(actions, text="닫기", command=window.destroy).pack(side="right", padx=(0, 6))
        window.focus_set()

    def _download_primary(self) -> None:
        if self.busy or not self.assets:
            return
        index = next((i for i, asset in enumerate(self.assets) if asset.kind == "video"), None)
        if index is None:
            primary = primary_asset_indices(self.assets)
            index = primary[0] if primary else 0
        self.download_index(index)

    def _set_busy(self, busy: bool, text: str | None = None) -> None:
        super()._set_busy(busy, text)
        quick = getattr(self, "quick_download_button", None)
        if quick is not None:
            quick.configure(state="normal" if self.assets and not busy else "disabled")

    def _clear_cards(self) -> None:
        super()._clear_cards()
        result_count = getattr(self, "result_count_var", None)
        if result_count is not None:
            result_count.set("아직 분석하지 않음")
        quick = getattr(self, "quick_download_button", None)
        if quick is not None:
            quick.configure(state="disabled")

    def _render_cards(self, data: dict) -> None:
        self._clear_cards()
        raw_assets = data.get("assets") or []
        fallback_preview = ""
        for raw in raw_assets:
            if isinstance(raw, dict):
                candidate = str(raw.get("preview_url") or "")
                if candidate.startswith("https://"):
                    fallback_preview = candidate
                    if str(raw.get("kind") or "") in {"thumbnail", "image"}:
                        break

        self.result_count_var.set(f"다운로드 가능 {len(self.assets)}개")

        primary_indices = primary_asset_indices(self.assets)
        primary_set = set(primary_indices)
        for index, asset in enumerate(self.assets):
            raw = raw_assets[index] if index < len(raw_assets) and isinstance(raw_assets[index], dict) else {}
            row = index // self.CARD_COLUMNS
            column = index % self.CARD_COLUMNS
            card = ttk.Frame(self.cards_frame, padding=10, relief="solid", borderwidth=1)
            card.grid(
                row=row,
                column=column,
                sticky="nsew",
                padx=(0 if column == 0 else 4, 4 if column == 0 else 0),
                pady=(0, 7),
            )

            preview = tk.Label(
                card,
                text="미리보기\n불러오는 중",
                width=18,
                height=7,
                bg="#f2f2f2",
                fg="#666666",
                relief="flat",
            )
            preview.pack(side="left", padx=(0, 10))
            self.preview_labels.append(preview)

            info = ttk.Frame(card)
            info.pack(side="left", fill="both", expand=True)
            label = asset.label or self._kind_name(asset.kind)
            if index in primary_set and asset.kind == "video":
                label = f"대표 영상 · {label}"
            ttk.Label(info, text=label, font=("Segoe UI", 10, "bold"), wraplength=300).pack(anchor="w")

            orientation = self._orientation(asset.width, asset.height)
            detail_parts = [self._kind_name(asset.kind)]
            if asset.ext:
                detail_parts.append(asset.ext.upper())
            if asset.width and asset.height:
                detail_parts.append(f"{asset.width}×{asset.height}")
            if orientation:
                detail_parts.append(orientation)
            ttk.Label(info, text=" · ".join(detail_parts), foreground="#555555").pack(anchor="w", pady=(4, 4))

            button_text = {
                "video": "영상 다운로드",
                "image": "이미지 다운로드",
                "thumbnail": "썸네일 다운로드",
                "archive": "묶음 다운로드",
            }.get(asset.kind, "다운로드")
            button = ttk.Button(info, text=button_text, command=lambda i=index: self.download_index(i))
            button.pack(fill="x", side="bottom", ipady=3)
            self.download_buttons.append(button)

            preview_url = str(raw.get("preview_url") or "")
            if not preview_url.startswith("https://") and asset.kind == "video":
                preview_url = fallback_preview
            if preview_url.startswith("https://"):
                threading.Thread(target=self._preview_worker, args=(index, preview_url), daemon=True).start()
            else:
                preview.configure(text="미리보기 없음")

        download_all = getattr(self, "download_all_button", None)
        if download_all is not None:
            download_all.configure(
                text=f"게시물 전체 다운로드 ({len(primary_indices)}개)",
                state="normal" if primary_indices and not self.busy else "disabled",
            )
        quick = getattr(self, "quick_download_button", None)
        if quick is not None:
            quick.configure(state="normal" if self.assets and not self.busy else "disabled")


if __name__ == "__main__":
    CompactDownloaderApp().mainloop()
