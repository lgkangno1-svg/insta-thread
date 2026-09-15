from __future__ import annotations

import queue
import threading
from pathlib import Path
from tkinter import messagebox, ttk

from app import DownloaderApp
from core import ApiError
from desktop_extras import (
    improve_download_name,
    load_preferences,
    primary_asset_indices,
    save_preferences,
)


class EnhancedDownloaderApp(DownloaderApp):
    def __init__(self) -> None:
        self.batch_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.failed_batch_indices: list[int] = []
        super().__init__()

        preferences = load_preferences()
        saved_folder = preferences.get("download_folder")
        if saved_folder:
            self.folder_var.set(saved_folder)

        self._install_batch_controls()
        self.bind("<Control-Return>", lambda _event: self.analyze())
        self.after(100, self._drain_batch_events)

    def _install_batch_controls(self) -> None:
        completed_row = self.open_file_button.master
        outer = completed_row.master
        batch_row = ttk.Frame(outer)
        batch_row.pack(fill="x", pady=(10, 0), before=completed_row)

        self.download_all_button = ttk.Button(
            batch_row,
            text="게시물 전체 다운로드",
            command=self.download_all,
            state="disabled",
        )
        self.download_all_button.pack(side="left", fill="x", expand=True)

        self.retry_failed_button = ttk.Button(
            batch_row,
            text="실패 항목 다시 받기",
            command=self.retry_failed,
            state="disabled",
        )
        self.retry_failed_button.pack(side="left", fill="x", expand=True, padx=(8, 0))

    def _set_busy(self, busy: bool, text: str | None = None) -> None:
        super()._set_busy(busy, text)
        download_all = getattr(self, "download_all_button", None)
        retry_failed = getattr(self, "retry_failed_button", None)
        if download_all is not None:
            enabled = bool(self.assets and primary_asset_indices(self.assets)) and not busy
            download_all.configure(state="normal" if enabled else "disabled")
        if retry_failed is not None:
            retry_failed.configure(state="normal" if self.failed_batch_indices and not busy else "disabled")

    def _clear_cards(self) -> None:
        super()._clear_cards()
        self.failed_batch_indices = []
        button = getattr(self, "retry_failed_button", None)
        if button is not None:
            button.configure(state="disabled")

    def _render_cards(self, data: dict) -> None:
        super()._render_cards(data)
        indices = primary_asset_indices(self.assets)
        button = getattr(self, "download_all_button", None)
        if button is not None:
            button.configure(
                text=f"게시물 전체 다운로드 ({len(indices)}개)",
                state="normal" if indices and not self.busy else "disabled",
            )

    def _choose_folder(self) -> None:
        before = self.folder_var.get()
        super()._choose_folder()
        after = self.folder_var.get()
        if after and after != before:
            try:
                save_preferences(after)
            except OSError:
                pass

    def _on_close(self) -> None:
        try:
            save_preferences(self.folder_var.get())
        except OSError:
            pass
        super()._on_close()

    def _prepare_folder(self) -> Path | None:
        folder = Path(self.folder_var.get()).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            save_preferences(str(folder))
            return folder
        except OSError as exc:
            messagebox.showerror("저장 폴더", f"저장 폴더를 사용할 수 없습니다.\n\n{exc}")
            return None

    @staticmethod
    def _status_text(state: str) -> str:
        if state == "processing":
            return "파일 변환/준비 중…"
        if state == "ready":
            return "다운로드 준비 완료…"
        return "다운로드 대기 중…"

    def _download_one(self, url: str, token: str, asset, index: int, folder: Path, status_cb, bytes_cb) -> Path:
        job_id = self.client.create_job(url, asset.id, token)
        download_url = self.client.wait_until_ready(
            job_id,
            progress=lambda state: status_cb(self._status_text(state)),
        )
        target = self.client.download_file(download_url, folder, progress=bytes_cb)
        analysis = self.analysis or {}
        return improve_download_name(target, analysis, asset, index)

    def _download_worker(self, url: str, token: str, asset, folder: Path) -> None:
        try:
            try:
                index = next(i for i, candidate in enumerate(self.assets) if candidate is asset)
            except StopIteration:
                index = self.assets.index(asset)
            target = self._download_one(
                url,
                token,
                asset,
                index,
                folder,
                status_cb=lambda text: self.events.put(("status", text)),
                bytes_cb=lambda received, total: self.events.put(("bytes", (received, total))),
            )
            self.events.put(("downloaded", target))
        except Exception as exc:
            self.events.put(("error", exc))

    def download_all(self) -> None:
        self._start_batch(primary_asset_indices(self.assets))

    def retry_failed(self) -> None:
        self._start_batch(list(self.failed_batch_indices))

    def _start_batch(self, indices: list[int]) -> None:
        if self.busy or not self.analysis or not self.assets or not indices:
            return
        valid = [index for index in indices if 0 <= index < len(self.assets)]
        if not valid:
            return
        folder = self._prepare_folder()
        if folder is None:
            return
        self.failed_batch_indices = []
        self.last_file = None
        self.open_file_button.configure(state="disabled")
        self._set_busy(True, f"{len(valid)}개 미디어를 순서대로 다운로드합니다…")
        source_url = str(self.analysis.get("source_url") or self.url_var.get())
        token = str(self.analysis.get("analysis_token") or "")
        threading.Thread(
            target=self._download_batch_worker,
            args=(source_url, token, valid, folder),
            daemon=True,
        ).start()

    def _download_batch_worker(self, url: str, token: str, indices: list[int], folder: Path) -> None:
        saved: list[Path] = []
        failed: list[tuple[int, str]] = []
        total_items = len(indices)

        for position, index in enumerate(indices, start=1):
            asset = self.assets[index]
            try:
                target = self._download_one(
                    url,
                    token,
                    asset,
                    index,
                    folder,
                    status_cb=lambda text, p=position, t=total_items, label=asset.label: self.batch_events.put(
                        ("status", f"[{p}/{t}] {label} · {text}")
                    ),
                    bytes_cb=lambda received, total, p=position, t=total_items: self.batch_events.put(
                        ("bytes", (p, t, received, total))
                    ),
                )
                saved.append(target)
            except Exception as exc:
                failed.append((index, str(exc)))

        self.batch_events.put(("done", (saved, failed)))

    def _drain_batch_events(self) -> None:
        try:
            while True:
                kind, payload = self.batch_events.get_nowait()
                if kind == "status":
                    self.status_var.set(str(payload))
                elif kind == "bytes":
                    position, total_items, received, total = payload
                    if total:
                        item_progress = min(1.0, received / total)
                        overall = ((position - 1) + item_progress) * 100 / total_items
                        self._set_progress_percent(overall)
                        self.status_var.set(
                            f"[{position}/{total_items}] 파일 저장 중… {received / 1024 / 1024:.1f} MB"
                        )
                    else:
                        overall = (position - 1) * 100 / total_items
                        self._set_progress_percent(overall)
                        self.status_var.set(
                            f"[{position}/{total_items}] 파일 저장 중… {received / 1024 / 1024:.1f} MB"
                        )
                elif kind == "done":
                    saved, failed = payload
                    self.failed_batch_indices = [index for index, _error in failed]
                    if saved:
                        self.last_file = Path(saved[-1])
                        self.open_file_button.configure(state="normal")
                    summary = f"완료 {len(saved)}개"
                    if failed:
                        summary += f" · 실패 {len(failed)}개"
                    self._set_busy(False, summary)
                    if failed:
                        details = "\n".join(
                            f"- {self.assets[index].label}: {error}" for index, error in failed[:5]
                        )
                        if len(failed) > 5:
                            details += f"\n- 외 {len(failed) - 5}개"
                        if saved:
                            open_folder = messagebox.askyesno(
                                "일부 다운로드 완료",
                                f"{len(saved)}개 저장, {len(failed)}개 실패했습니다.\n\n{details}\n\n"
                                "실패 항목은 '실패 항목 다시 받기'로 재시도할 수 있습니다.\n"
                                "저장 폴더를 열까요?",
                            )
                            if open_folder:
                                self._open_download_folder()
                        else:
                            messagebox.showerror(
                                "다운로드 실패",
                                f"모든 항목의 다운로드에 실패했습니다.\n\n{details}\n\n"
                                "'실패 항목 다시 받기'로 재시도할 수 있습니다.",
                            )
                    elif saved:
                        if messagebox.askyesno(
                            "전체 다운로드 완료",
                            f"{len(saved)}개 미디어를 모두 저장했습니다.\n\n저장 폴더를 열까요?",
                        ):
                            self._open_download_folder()
        except queue.Empty:
            pass
        finally:
            if self.winfo_exists():
                self.after(100, self._drain_batch_events)


if __name__ == "__main__":
    EnhancedDownloaderApp().mainloop()
