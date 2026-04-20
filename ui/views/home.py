"""
ui/views/home.py — Main backup view.

State machine:
  idle       → directory selected  → scanning  → ready  → backing_up  → idle
  (on error) → idle

Scan is automatic: fires whenever Browse picks a directory or the user
presses Enter in the path field. The "Rescan" button is a small utility
action positioned near the path field, not part of the primary workflow.

Primary action bar contains only:
  Preview Backup  (secondary — amber outline)
  Backup Now      (primary  — solid blue, disabled until scan completes)
"""

from __future__ import annotations

import queue
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from backup_project import (
    ExclusionRules,
    ExclusionStats,
    _walk_with_stats,
    make_destination,
)
from ui.components import SectionLabel, StatCard
from ui.persistence import (
    add_history_entry,
    build_config,
    fmt_size,
    save_settings,
)
from ui.popups.dry_run import DryRunWindow
from ui.popups.toast import SuccessToast
from ui.tokens import (
    ACCENT, ACCENT_DIM, ACCENT_GLOW, BG, BORDER, BORDER_ACTIVE,
    CARD, CARD2, DANGER, DANGER_DIM, FONT_BODY, FONT_HEAD, FONT_MONO,
    FONT_SMALL, FONT_TITLE, FONT_LABEL, INPUT, SUCCESS, SUCCESS_DIM,
    TEXT, TEXT_DIM, TEXT_MUTED, WARNING, WARNING_DIM,
)

_COMPRESSION_MAP = {
    "deflated": zipfile.ZIP_DEFLATED,
    "stored":   zipfile.ZIP_STORED,
    "bzip2":    zipfile.ZIP_BZIP2,
    "lzma":     zipfile.ZIP_LZMA,
}

# ---------------------------------------------------------------------------
# App states — drives button enable/disable and status display
# ---------------------------------------------------------------------------

class _State:
    IDLE       = "idle"
    SCANNING   = "scanning"
    READY      = "ready"
    BACKING_UP = "backing_up"


class HomeFrame(ctk.CTkFrame):
    """
    Primary view. All long-running work runs on daemon threads;
    results arrive via self._q, polled every 50 ms on the main thread.
    """

    def __init__(self, master, app, **kw):
        super().__init__(master, corner_radius=0, fg_color=BG, **kw)
        self._app   = app
        self._state = _State.IDLE
        self._scan_thread:   threading.Thread | None = None
        self._backup_thread: threading.Thread | None = None
        self._q: queue.Queue = queue.Queue()
        self._scanned_files: list[Path]    | None = None
        self._scanned_stats: ExclusionStats| None = None
        self._source: Path | None = None
        self._build()
        self._poll()

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _card(self, parent, **kw) -> ctk.CTkFrame:
        return ctk.CTkFrame(
            parent, fg_color=CARD, corner_radius=10,
            border_color=BORDER, border_width=1, **kw,
        )

    def _build(self) -> None:
        self._build_topbar()
        body = self._build_body()
        self._build_dir_card(body)
        self._build_stats_row(body)
        self._build_preview_panels(body)
        self._build_output_card(body)
        self._build_progress_bar(body)
        self._build_action_bar(body)

    # ------------------------------------------------------------------
    # Topbar — page title + unified status pill
    # ------------------------------------------------------------------

    def _build_topbar(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(
            topbar, text="Backup", font=FONT_TITLE, text_color=TEXT,
        ).pack(side="left", padx=22)

        # Status pill — single source of truth for app state messaging
        pill = ctk.CTkFrame(
            topbar, fg_color=INPUT, corner_radius=20,
            border_color=BORDER, border_width=1,
        )
        pill.pack(side="right", padx=18, pady=10)

        self._status_dot = ctk.CTkLabel(
            pill, text="●", font=("Segoe UI", 9), text_color=TEXT_MUTED,
        )
        self._status_dot.pack(side="left", padx=(10, 5), pady=6)

        self._status_lbl = ctk.CTkLabel(
            pill, text="Select a project to get started",
            font=FONT_SMALL, text_color=TEXT_DIM,
        )
        self._status_lbl.pack(side="left", padx=(0, 14), pady=6)

    # ------------------------------------------------------------------
    # Body grid
    # ------------------------------------------------------------------

    def _build_body(self) -> ctk.CTkFrame:
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)   # preview panels get all spare height
        return body

    # ------------------------------------------------------------------
    # Directory card — path entry + Browse + ↻ Rescan (utility, not primary)
    # ------------------------------------------------------------------

    def _build_dir_card(self, body: ctk.CTkFrame) -> None:
        card = self._card(body)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=13)
        content.columnconfigure(1, weight=1)

        SectionLabel(content, "PROJECT DIRECTORY").grid(
            row=0, column=0, sticky="w", padx=(0, 14),
        )

        row = ctk.CTkFrame(content, fg_color="transparent")
        row.grid(row=0, column=1, sticky="ew")

        self._path_var = ctk.StringVar(value="")
        entry = ctk.CTkEntry(
            row,
            textvariable=self._path_var,
            font=FONT_MONO,
            fg_color=INPUT,
            border_color=BORDER,
            border_width=1,
            text_color=ACCENT,
            height=36,
            corner_radius=8,
            placeholder_text="Select or paste a project path…",
        )
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry.bind("<Return>", lambda _: self._trigger_scan())
        entry.bind("<FocusOut>", lambda _: self._trigger_scan())

        ctk.CTkButton(
            row, text="Browse", width=82, height=36,
            font=FONT_SMALL, fg_color=INPUT, hover_color=CARD2,
            border_color=BORDER_ACTIVE, border_width=1,
            text_color=TEXT_DIM, corner_radius=8,
            command=self._browse,
        ).pack(side="left", padx=(0, 6))

        # ↻ Rescan — utility button, visually lighter than primary actions
        self._rescan_btn = ctk.CTkButton(
            row, text="↻", width=36, height=36,
            font=("Segoe UI", 14), fg_color="transparent",
            hover_color=CARD2, border_color=BORDER, border_width=1,
            text_color=TEXT_MUTED, corner_radius=8,
            command=self._trigger_scan,
        )
        self._rescan_btn.pack(side="left")

    # ------------------------------------------------------------------
    # Stats row — three metric cards
    # ------------------------------------------------------------------

    def _build_stats_row(self, body: ctk.CTkFrame) -> None:
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        row.columnconfigure((0, 1, 2), weight=1)

        self._stat_files = StatCard(
            row, "FILES FOUND", "—", TEXT, sub="select a project first",
        )
        self._stat_files.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._stat_size = StatCard(
            row, "TOTAL SIZE", "—", TEXT, sub="uncompressed estimate",
        )
        self._stat_size.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        self._stat_status = StatCard(
            row, "STATUS", "Idle", TEXT_MUTED, sub="waiting for a directory",
        )
        self._stat_status.grid(row=0, column=2, sticky="ew")

    # ------------------------------------------------------------------
    # Preview panels — included files + excluded dirs
    # ------------------------------------------------------------------

    def _build_preview_panels(self, body: ctk.CTkFrame) -> None:
        preview = ctk.CTkFrame(body, fg_color="transparent")
        preview.grid(row=2, column=0, sticky="nsew", pady=(0, 8))
        preview.columnconfigure(0, weight=4)
        preview.columnconfigure(1, weight=3)
        preview.rowconfigure(0, weight=1)

        # --- Included ---
        inc_card = self._card(preview)
        inc_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        inc_header = ctk.CTkFrame(inc_card, fg_color="transparent")
        inc_header.pack(fill="x", padx=14, pady=(12, 6))
        SectionLabel(inc_header, "WILL BE BACKED UP").pack(side="left")
        self._inc_badge = ctk.CTkLabel(
            inc_header, text="",
            font=FONT_LABEL, text_color=TEXT_MUTED,
        )
        self._inc_badge.pack(side="right")

        self._inc_scroll = ctk.CTkScrollableFrame(
            inc_card, fg_color=INPUT, corner_radius=8,
            border_color=BORDER, border_width=1,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BORDER_ACTIVE,
        )
        self._inc_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._set_empty_state(
            self._inc_scroll,
            "Scan a project to see included files",
        )

        # --- Excluded ---
        exc_card = self._card(preview)
        exc_card.grid(row=0, column=1, sticky="nsew")

        exc_header = ctk.CTkFrame(exc_card, fg_color="transparent")
        exc_header.pack(fill="x", padx=14, pady=(12, 6))
        SectionLabel(exc_header, "EXCLUDED").pack(side="left")
        self._exc_badge = ctk.CTkLabel(
            exc_header, text="",
            font=FONT_LABEL, text_color=TEXT_MUTED,
        )
        self._exc_badge.pack(side="right")

        self._exc_scroll = ctk.CTkScrollableFrame(
            exc_card, fg_color=INPUT, corner_radius=8,
            border_color=BORDER, border_width=1,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=BORDER_ACTIVE,
        )
        self._exc_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._set_empty_state(
            self._exc_scroll,
            "Excluded directories will appear here",
        )

    # ------------------------------------------------------------------
    # Output directory card
    # ------------------------------------------------------------------

    def _build_output_card(self, body: ctk.CTkFrame) -> None:
        card = self._card(body)
        card.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.pack(fill="x", padx=16, pady=13)
        content.columnconfigure(1, weight=1)

        SectionLabel(content, "OUTPUT DIRECTORY").grid(
            row=0, column=0, sticky="w", padx=(0, 14),
        )

        row = ctk.CTkFrame(content, fg_color="transparent")
        row.grid(row=0, column=1, sticky="ew")

        default_out = self._app.settings.get(
            "backup_dir", str(Path.home() / "Downloads" / "backup"),
        )
        self._out_var = ctk.StringVar(value=default_out)
        ctk.CTkEntry(
            row, textvariable=self._out_var,
            font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
            border_width=1, text_color=TEXT_DIM, height=36, corner_radius=8,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            row, text="Change", width=82, height=36,
            font=FONT_SMALL, fg_color=INPUT, hover_color=CARD2,
            border_color=BORDER_ACTIVE, border_width=1,
            text_color=TEXT_DIM, corner_radius=8,
            command=self._browse_output,
        ).pack(side="left")

    # ------------------------------------------------------------------
    # Progress bar (hidden until backup starts)
    # ------------------------------------------------------------------

    def _build_progress_bar(self, body: ctk.CTkFrame) -> None:
        self._prog_frame = ctk.CTkFrame(
            body, fg_color=CARD, corner_radius=10,
            border_color=BORDER, border_width=1, height=50,
        )
        self._prog_frame.grid(row=4, column=0, sticky="ew")
        self._prog_frame.grid_remove()
        self._prog_frame.grid_propagate(False)

        inner = ctk.CTkFrame(self._prog_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14, pady=14)

        self._prog_bar = ctk.CTkProgressBar(
            inner, progress_color=ACCENT, fg_color=INPUT,
            corner_radius=4, height=5,
        )
        self._prog_bar.set(0)
        self._prog_bar.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self._prog_lbl = ctk.CTkLabel(
            inner, text="0%", font=("Consolas", 10),
            text_color=ACCENT, width=36,
        )
        self._prog_lbl.pack(side="left")

    # ------------------------------------------------------------------
    # Action bar — Preview (secondary) + Backup Now (primary)
    # ------------------------------------------------------------------

    def _build_action_bar(self, body: ctk.CTkFrame) -> None:
        act = ctk.CTkFrame(
            body, fg_color=CARD, corner_radius=10,
            border_color=BORDER, border_width=1, height=60,
        )
        act.grid(row=5, column=0, sticky="ew")
        act.grid_propagate(False)

        # Secondary action — amber outline, only active after scan
        self._preview_btn = ctk.CTkButton(
            act, text="Preview Backup", width=148, height=38,
            font=FONT_HEAD,
            fg_color="transparent", hover_color=WARNING_DIM,
            border_color=WARNING, border_width=1,
            text_color=WARNING, corner_radius=8,
            command=self._trigger_dry_run, state="disabled",
        )
        self._preview_btn.pack(side="left", padx=(14, 0), pady=11)

        # Primary action — solid blue, dominant
        self._backup_btn = ctk.CTkButton(
            act, text="Backup Now", width=148, height=38,
            font=FONT_HEAD,
            fg_color=ACCENT_GLOW, hover_color="#5a9ff8",
            text_color="#06090f", corner_radius=8,
            command=self._trigger_backup, state="disabled",
        )
        self._backup_btn.pack(side="right", padx=14, pady=11)

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------

    def _browse(self) -> None:
        d = filedialog.askdirectory(
            title="Select project directory",
            initialdir=self._path_var.get() or str(Path.home()),
        )
        if d:
            self._path_var.set(d)
            self._trigger_scan()

    def _browse_output(self) -> None:
        d = filedialog.askdirectory(
            title="Select output directory",
            initialdir=self._out_var.get(),
        )
        if d:
            self._out_var.set(d)
            self._app.settings["backup_dir"] = d
            save_settings(self._app.settings)

    def _trigger_scan(self) -> None:
        if self._state in (_State.SCANNING, _State.BACKING_UP):
            return

        raw = self._path_var.get().strip()
        if not raw:
            return
        source = Path(raw).resolve()
        if not source.is_dir():
            self._set_state(_State.IDLE)
            self._set_status("Not a valid directory", DANGER)
            self._stat_status.set("Error", DANGER)
            self._stat_status.set_sub("check the path and try again", DANGER)
            return

        self._source = source
        self._scanned_files = None
        self._set_state(_State.SCANNING)

        config = build_config(self._app.settings)
        rules  = ExclusionRules.build(config)

        def _run():
            try:
                files, stats = _walk_with_stats(source, rules)
                self._q.put(("scan_done", files, stats))
            except Exception as e:
                self._q.put(("scan_error", str(e)))

        self._scan_thread = threading.Thread(target=_run, daemon=True)
        self._scan_thread.start()

    def _trigger_dry_run(self) -> None:
        if not self._scanned_files:
            return
        DryRunWindow(self._app, self._source, self._scanned_files, self._scanned_stats)

    def _trigger_backup(self) -> None:
        if not self._scanned_files or not self._source:
            return
        if self._state == _State.BACKING_UP:
            return

        config      = build_config(self._app.settings)
        out_dir     = Path(self._out_var.get()).expanduser().resolve()
        destination = make_destination(self._source, out_dir)
        files       = list(self._scanned_files)
        total       = len(files)
        source      = self._source
        comp        = _COMPRESSION_MAP.get(config.compression, zipfile.ZIP_DEFLATED)

        self._set_state(_State.BACKING_UP)
        self._prog_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self._prog_bar.set(0)
        self._prog_lbl.configure(text="0%")

        def _run():
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(destination, "w", compression=comp) as zf:
                    for i, file in enumerate(files, 1):
                        arcname = file.relative_to(source.parent)
                        try:
                            zf.write(file, arcname)
                        except (PermissionError, OSError):
                            pass
                        self._q.put(("progress", i / total))
                size = destination.stat().st_size
                self._q.put(("backup_done", destination, total, size))
            except Exception as e:
                self._q.put(("backup_error", str(e)))

        self._backup_thread = threading.Thread(target=_run, daemon=True)
        self._backup_thread.start()

    # ------------------------------------------------------------------
    # Queue polling
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        try:
            while True:
                self._handle(self._q.get_nowait())
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _handle(self, msg: tuple) -> None:
        kind = msg[0]
        if kind == "scan_done":
            self._on_scan_done(msg[1], msg[2])
        elif kind == "scan_error":
            self._on_scan_error(msg[1])
        elif kind == "progress":
            pct = msg[1]
            self._prog_bar.set(pct)
            self._prog_lbl.configure(text=f"{int(pct * 100)}%")
        elif kind == "backup_done":
            self._on_backup_done(msg[1], msg[2], msg[3])
        elif kind == "backup_error":
            self._on_backup_error(msg[1])

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    def _set_state(self, state: str) -> None:
        self._state = state

        if state == _State.IDLE:
            self._rescan_btn.configure(state="normal", text_color=TEXT_MUTED)
            self._preview_btn.configure(state="disabled")
            self._backup_btn.configure(state="disabled", text="Backup Now")
            self._set_status("Select a project to get started", TEXT_MUTED)
            self._stat_status.set("Idle", TEXT_MUTED)
            self._stat_status.set_sub("waiting for a directory")

        elif state == _State.SCANNING:
            self._rescan_btn.configure(state="disabled", text_color=TEXT_MUTED)
            self._preview_btn.configure(state="disabled")
            self._backup_btn.configure(state="disabled")
            self._set_status("Scanning project…", WARNING)
            self._stat_files.set("…", TEXT_MUTED)
            self._stat_files.set_sub("")
            self._stat_size.set("…", TEXT_MUTED)
            self._stat_size.set_sub("")
            self._stat_status.set("Scanning", WARNING)
            self._stat_status.set_sub("reading directory tree")
            self._clear_scroll(self._inc_scroll)
            self._set_empty_state(self._inc_scroll, "Scanning…")
            self._clear_scroll(self._exc_scroll)
            self._inc_badge.configure(text="")
            self._exc_badge.configure(text="")

        elif state == _State.READY:
            self._rescan_btn.configure(state="normal", text_color=TEXT_MUTED)
            self._preview_btn.configure(state="normal")
            self._backup_btn.configure(state="normal")

        elif state == _State.BACKING_UP:
            self._rescan_btn.configure(state="disabled")
            self._preview_btn.configure(state="disabled")
            self._backup_btn.configure(state="disabled", text="Backing up…")
            self._set_status("Backing up…", ACCENT)
            self._stat_status.set("Backing up", ACCENT)
            self._stat_status.set_sub("writing ZIP archive")

    # ------------------------------------------------------------------
    # Scan result handlers
    # ------------------------------------------------------------------

    def _on_scan_done(self, files: list[Path], stats: ExclusionStats) -> None:
        self._scanned_files = files
        self._scanned_stats = stats
        self._set_state(_State.READY)

        total_size = sum(f.stat().st_size for f in files if f.exists())
        total_excl = sum(stats.excluded_dirs.values()) + stats.excluded_files

        self._stat_files.set(f"{len(files):,}", SUCCESS)
        self._stat_files.set_sub("will be backed up")
        self._stat_size.set(fmt_size(total_size), ACCENT)
        self._stat_size.set_sub("uncompressed")
        self._stat_status.set("Ready", SUCCESS)
        self._stat_status.set_sub("all checks passed")
        self._set_status(
            f"{len(files):,} files · {fmt_size(total_size)} · ready to back up",
            SUCCESS,
        )

        # Included panel
        self._clear_scroll(self._inc_scroll)
        self._inc_badge.configure(
            text=f"{len(files):,} files", text_color=SUCCESS,
        )
        show_max = 120
        for f in files[:show_max]:
            rel = str(f.relative_to(self._source.parent))
            self._file_row(self._inc_scroll, rel, "✓", SUCCESS)

        if len(files) > show_max:
            ctk.CTkFrame(self._inc_scroll, fg_color=BORDER, height=1).pack(
                fill="x", pady=(6, 0),
            )
            ctk.CTkLabel(
                self._inc_scroll,
                text=f"+{len(files) - show_max:,} more files",
                font=FONT_SMALL, text_color=TEXT_MUTED,
            ).pack(pady=(4, 8))

        # Excluded panel
        self._clear_scroll(self._exc_scroll)
        self._exc_badge.configure(
            text=f"{total_excl:,} skipped", text_color=TEXT_MUTED,
        )
        for dname, count in sorted(
            stats.excluded_dirs.items(), key=lambda x: -x[1]
        ):
            self._excl_row(self._exc_scroll, dname, count)

        if stats.excluded_files:
            ctk.CTkFrame(self._exc_scroll, fg_color=BORDER, height=1).pack(
                fill="x", pady=(4, 0),
            )
            ctk.CTkLabel(
                self._exc_scroll,
                text=f"+{stats.excluded_files:,} files matched by pattern",
                font=FONT_SMALL, text_color=TEXT_MUTED,
            ).pack(anchor="w", padx=4, pady=(4, 8))

    def _on_scan_error(self, err: str) -> None:
        self._set_state(_State.IDLE)
        self._set_status(f"Scan failed — {err}", DANGER)
        self._stat_status.set("Error", DANGER)
        self._stat_status.set_sub(err[:40])

    # ------------------------------------------------------------------
    # Backup result handlers
    # ------------------------------------------------------------------

    def _on_backup_done(self, dest: Path, count: int, size: int) -> None:
        self._prog_frame.grid_remove()
        add_history_entry({
            "timestamp":   datetime.now().isoformat(),
            "source":      str(self._source),
            "destination": str(dest),
            "files":       count,
            "size":        size,
        })
        self._app.refresh_history()
        SuccessToast(self._app, dest, count, size)
        self._reset_ui()

    def _on_backup_error(self, err: str) -> None:
        self._prog_frame.grid_remove()
        self._set_state(_State.READY)  # let user retry
        self._set_status(f"Backup failed — {err}", DANGER)
        self._stat_status.set("Error", DANGER)
        self._stat_status.set_sub("backup was not created")

    # ------------------------------------------------------------------
    # Widget helpers
    # ------------------------------------------------------------------

    def _set_status(self, msg: str, color: str = TEXT_MUTED) -> None:
        self._status_lbl.configure(text=msg)
        self._status_dot.configure(text_color=color)

    def _set_empty_state(self, frame: ctk.CTkScrollableFrame, text: str) -> None:
        ctk.CTkLabel(
            frame, text=text, font=FONT_SMALL, text_color=TEXT_MUTED,
        ).pack(expand=True, pady=28)

    def _clear_scroll(self, frame: ctk.CTkScrollableFrame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    def _file_row(
        self,
        parent: ctk.CTkScrollableFrame,
        text: str,
        icon: str,
        icon_color: str,
    ) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=1)
        ctk.CTkLabel(
            row, text=icon, font=("Segoe UI", 9, "bold"),
            text_color=icon_color, width=14,
        ).pack(side="left", padx=(4, 6))
        ctk.CTkLabel(
            row, text=text, font=FONT_MONO,
            text_color=TEXT_DIM, anchor="w",
        ).pack(side="left", fill="x", expand=True)

    def _excl_row(
        self,
        parent: ctk.CTkScrollableFrame,
        dname: str,
        count: int,
    ) -> None:
        badge = ctk.CTkFrame(
            parent, fg_color=DANGER_DIM, corner_radius=6,
            border_color=BORDER, border_width=1,
        )
        badge.pack(fill="x", pady=2)

        inner = ctk.CTkFrame(badge, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            inner, text="✕", font=("Segoe UI", 9, "bold"),
            text_color=DANGER, width=12,
        ).pack(side="left", padx=(0, 7))

        ctk.CTkLabel(
            inner, text=f"{dname}/", font=FONT_MONO,
            text_color=TEXT_DIM, anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Count pill
        pill = ctk.CTkFrame(
            inner, fg_color=INPUT, corner_radius=4,
            border_color=BORDER, border_width=1,
        )
        pill.pack(side="right")
        ctk.CTkLabel(
            pill, text=f"{count:,}", font=("Consolas", 9),
            text_color=TEXT_DIM,
        ).pack(padx=7, pady=1)

    def _reset_ui(self) -> None:
        """Return to full idle state after a completed backup."""
        self._source        = None
        self._scanned_files = None
        self._scanned_stats = None
        self._path_var.set("")
        self._clear_scroll(self._inc_scroll)
        self._clear_scroll(self._exc_scroll)
        self._set_empty_state(self._inc_scroll, "Scan a project to see included files")
        self._set_empty_state(self._exc_scroll, "Excluded directories will appear here")
        self._inc_badge.configure(text="")
        self._exc_badge.configure(text="")
        self._stat_files.set("—", TEXT)
        self._stat_files.set_sub("select a project first")
        self._stat_size.set("—", TEXT)
        self._stat_size.set_sub("uncompressed estimate")
        self._set_state(_State.IDLE)
        self._prog_frame.grid_remove()
