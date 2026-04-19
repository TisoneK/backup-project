#!/usr/bin/env python3
"""
backup_app.py — GUI entry point for Backup Project.

Launches a modern desktop UI built with CustomTkinter.
For CLI users, pass -c as the first argument to bypass the GUI entirely:

    backup_project.exe -c [DIR] [--dry-run] [--output PATH] ...

All other CLI flags are identical to backup_project.py.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
from PIL import Image, ImageDraw, ImageFont, ImageTk

# ---------------------------------------------------------------------------
# CLI passthrough — must come before any CTk import so headless envs work
# ---------------------------------------------------------------------------

def _cli_passthrough() -> None:
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    from backup_project import main as cli_main
    sys.exit(cli_main())

if len(sys.argv) > 1 and sys.argv[1] == "-c":
    _cli_passthrough()

# ---------------------------------------------------------------------------
# GUI imports
# ---------------------------------------------------------------------------

import customtkinter as ctk

from backup_project import (
    BackupConfig,
    ExclusionRules,
    ExclusionStats,
    _walk,
    _walk_with_stats,
    create_backup,
    load_config,
    make_destination,
)

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

BG           = "#0d1117"
CARD         = "#161b22"
CARD2        = "#1c2333"
INPUT        = "#21262d"
BORDER       = "#30363d"
BORDER_SUB   = "#21262d"
ACCENT       = "#58a6ff"
ACCENT_DIM   = "#1f4070"
ACCENT_GLOW  = "#388bfd"
SUCCESS      = "#3fb950"
SUCCESS_DIM  = "#0d3320"
WARNING      = "#d29922"
WARNING_DIM  = "#2d1f00"
DANGER       = "#f85149"
DANGER_DIM   = "#3d1a18"
TEXT         = "#e6edf3"
TEXT_DIM     = "#8b949e"
TEXT_MUTED   = "#484f58"

FONT_TITLE   = ("Segoe UI", 18, "bold")
FONT_HEAD    = ("Segoe UI", 11, "bold")
FONT_BODY    = ("Segoe UI", 12)
FONT_SMALL   = ("Segoe UI", 10)
FONT_MONO    = ("Consolas", 10)
FONT_LABEL   = ("Segoe UI", 9, "bold")

# ---------------------------------------------------------------------------
# Persistent history
# ---------------------------------------------------------------------------

def _history_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    p = base / "backup_project"
    p.mkdir(parents=True, exist_ok=True)
    return p / "history.json"

def load_history() -> list[dict]:
    try:
        return json.loads(_history_path().read_text())
    except Exception:
        return []

def save_history(entries: list[dict]) -> None:
    try:
        _history_path().write_text(json.dumps(entries[-50:], indent=2))
    except Exception:
        pass

def add_history_entry(entry: dict) -> list[dict]:
    history = load_history()
    history.append(entry)
    save_history(history)
    return history

# ---------------------------------------------------------------------------
# Persistent settings
# ---------------------------------------------------------------------------

def _settings_path() -> Path:
    return _history_path().parent / "settings.json"

def load_settings() -> dict:
    defaults = {
        "backup_dir": str(Path.home() / "Downloads" / "backup"),
        "compression": "deflated",
        "extra_dirs": "",
        "extra_extensions": "",
        "include_defaults": True,
    }
    try:
        saved = json.loads(_settings_path().read_text())
        defaults.update(saved)
    except Exception:
        pass
    return defaults

def save_settings(s: dict) -> None:
    try:
        _settings_path().write_text(json.dumps(s, indent=2))
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024**2:.2f} MB"
    return f"{size_bytes / 1024**3:.2f} GB"

def _build_config(settings: dict) -> BackupConfig:
    extra_dirs = [d.strip() for d in settings.get("extra_dirs", "").split(",") if d.strip()]
    extra_exts = [e.strip() for e in settings.get("extra_extensions", "").split(",") if e.strip()]
    return BackupConfig(
        extra_dirs=extra_dirs,
        extra_names=[],
        extra_extensions=extra_exts,
        extra_patterns=[],
        include_defaults=settings.get("include_defaults", True),
        backup_dir=settings.get("backup_dir") or None,
        compression=settings.get("compression", "deflated"),
    )

# ---------------------------------------------------------------------------
# Reusable components
# ---------------------------------------------------------------------------

class SectionLabel(ctk.CTkLabel):
    def __init__(self, master, text: str, **kw):
        super().__init__(master, text=text, font=FONT_LABEL, text_color=TEXT_MUTED, **kw)


class StatCard(ctk.CTkFrame):
    def __init__(self, master, label: str, value: str = "—", value_color: str = TEXT, **kw):
        super().__init__(master, fg_color=INPUT, corner_radius=8,
                         border_color=BORDER_SUB, border_width=1, **kw)
        ctk.CTkLabel(self, text=label, font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(6, 0))
        self._val = ctk.CTkLabel(self, text=value, font=("Segoe UI", 15, "bold"),
                                  text_color=value_color)
        self._val.pack(anchor="w", padx=12, pady=(1, 6))

    def set(self, value: str, color: str | None = None) -> None:
        self._val.configure(text=value)
        if color:
            self._val.configure(text_color=color)


class Logo(ctk.CTkFrame):
    def __init__(self, master, icon: str = "📦", **kw):
        super().__init__(master, fg_color=ACCENT_DIM, corner_radius=10,
                         width=40, height=40, **kw)
        self.pack_propagate(False)
        ctk.CTkLabel(self, text=icon, font=("Segoe UI", 18)).pack(expand=True, pady=6)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

class Sidebar(ctk.CTkFrame):
    PAGES = [
        ("home",     "⌂",  "Backup"),
        ("history",  "◷",  "History"),
        ("settings", "⚙",  "Settings"),
    ]

    def __init__(self, master, on_navigate, **kw):
        super().__init__(master, width=72, corner_radius=0, fg_color=CARD, **kw)
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}

        Logo(self).pack(pady=(20, 20))

        for page_id, icon, label in self.PAGES:
            btn = ctk.CTkButton(
                self, text=f"{icon}\n{label}", font=("Segoe UI", 9),
                width=58, height=58, corner_radius=10,
                fg_color="transparent", hover_color=INPUT, text_color=TEXT_MUTED,
                command=lambda pid=page_id: self._select(pid),
            )
            btn.pack(pady=3, padx=7)
            self._buttons[page_id] = btn

        self._select("home")

    def _select(self, page_id: str) -> None:
        for pid, btn in self._buttons.items():
            btn.configure(
                fg_color=ACCENT_DIM if pid == page_id else "transparent",
                text_color=ACCENT if pid == page_id else TEXT_MUTED,
            )
        self._on_navigate(page_id)

# ---------------------------------------------------------------------------
# Home frame
# ---------------------------------------------------------------------------

class HomeFrame(ctk.CTkFrame):
    def __init__(self, master, app: "BackupApp", **kw):
        super().__init__(master, corner_radius=0, fg_color=BG, **kw)
        self._app = app
        self._scan_thread: threading.Thread | None = None
        self._backup_thread: threading.Thread | None = None
        self._q: queue.Queue = queue.Queue()
        self._scanned_files: list[Path] | None = None
        self._scanned_stats: ExclusionStats | None = None
        self._source: Path | None = None
        self._build()
        self._poll()

    def _card(self, parent) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10,
                             border_color=BORDER, border_width=1)

    def _set_status(self, msg: str, color: str = TEXT_DIM) -> None:
        self._status_lbl.configure(text=msg)
        self._status_dot.configure(text_color=color)

    def _clear_scroll(self, frame: ctk.CTkScrollableFrame) -> None:
        for w in frame.winfo_children():
            w.destroy()

    def _build(self) -> None:
        # ── Top bar
        topbar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Backup", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=22)

        pill = ctk.CTkFrame(topbar, fg_color=INPUT, corner_radius=20,
                             border_color=BORDER, border_width=1)
        pill.pack(side="right", padx=16)
        self._status_dot = ctk.CTkLabel(pill, text="●", font=("Segoe UI", 10),
                                         text_color=TEXT_MUTED)
        self._status_dot.pack(side="left", padx=(10, 4), pady=5)
        self._status_lbl = ctk.CTkLabel(pill, text="Ready", font=FONT_SMALL,
                                         text_color=TEXT_DIM)
        self._status_lbl.pack(side="left", padx=(0, 12), pady=5)

        # ── Body
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=18, pady=14)
        body.columnconfigure(0, weight=1)  # Main content column expands
        body.rowconfigure(2, weight=1)  # Preview row expands

        # ── Project directory card
        dir_card = self._card(body)
        dir_card.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        dir_content_frame = ctk.CTkFrame(dir_card, fg_color="transparent")
        dir_content_frame.pack(fill="x", padx=16, pady=(12, 14))
        dir_content_frame.columnconfigure(1, weight=1)  # Make entry field expand

        SectionLabel(dir_content_frame, "PROJECT DIRECTORY").grid(row=0, column=0, sticky="w", padx=(0, 16))

        dir_row = ctk.CTkFrame(dir_content_frame, fg_color="transparent")
        dir_row.grid(row=0, column=1, sticky="ew")

        self._path_var = ctk.StringVar(value="")
        path_entry = ctk.CTkEntry(
            dir_row, textvariable=self._path_var,
            font=FONT_MONO, fg_color=INPUT,
            border_color=BORDER, border_width=1,
            text_color=ACCENT, height=36,
            placeholder_text="Select a project directory…",
        )
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        path_entry.bind("<Return>", lambda _: self._trigger_scan())

        ctk.CTkButton(dir_row, text="Browse", width=90, height=36,
                      font=FONT_SMALL, fg_color=INPUT, hover_color=CARD2,
                      border_color=BORDER, border_width=1, text_color=TEXT_DIM,
                      corner_radius=8, command=self._browse).pack(side="left")

        # ── Stat cards
        stats_row = ctk.CTkFrame(body, fg_color="transparent")
        stats_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        stats_row.columnconfigure((0, 1, 2), weight=1)

        self._stat_files  = StatCard(stats_row, "FILES", "—")
        self._stat_files.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self._stat_size   = StatCard(stats_row, "UNCOMPRESSED SIZE", "—")
        self._stat_size.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        self._stat_status = StatCard(stats_row, "STATUS", "Waiting")
        self._stat_status.grid(row=0, column=2, sticky="ew")

        # ── Preview panels
        preview = ctk.CTkFrame(body, fg_color="transparent")
        preview.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        preview.columnconfigure(0, weight=4)  # "WILL BE BACKED UP" gets more space
        preview.columnconfigure(1, weight=3)  # "EXCLUDED" gets more space
        preview.rowconfigure(0, weight=1)

        inc_card = self._card(preview)
        inc_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        SectionLabel(inc_card, "WILL BE BACKED UP").pack(anchor="w", padx=16, pady=(12, 8))
        self._inc_scroll = ctk.CTkScrollableFrame(
            inc_card, fg_color=INPUT, corner_radius=8,
            border_color=BORDER_SUB, border_width=1,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT_DIM,
        )
        self._inc_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ctk.CTkLabel(self._inc_scroll, text="Scan a directory to see files",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(pady=20)

        exc_card = self._card(preview)
        exc_card.grid(row=0, column=1, sticky="nsew")
        SectionLabel(exc_card, "EXCLUDED").pack(anchor="w", padx=16, pady=(12, 8))
        self._exc_scroll = ctk.CTkScrollableFrame(
            exc_card, fg_color=INPUT, corner_radius=8,
            border_color=BORDER_SUB, border_width=1,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT_DIM,
        )
        self._exc_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ctk.CTkLabel(self._exc_scroll, text="No exclusions yet",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(pady=20)

        # ── Output card
        out_card = self._card(body)
        out_card.grid(row=3, column=0, sticky="ew", pady=(0, 6))
        out_content_frame = ctk.CTkFrame(out_card, fg_color="transparent")
        out_content_frame.pack(fill="x", padx=16, pady=(12, 14))
        out_content_frame.columnconfigure(1, weight=1)  # Make entry field expand

        SectionLabel(out_content_frame, "OUTPUT DIRECTORY").grid(row=0, column=0, sticky="w", padx=(0, 16))

        out_row = ctk.CTkFrame(out_content_frame, fg_color="transparent")
        out_row.grid(row=0, column=1, sticky="ew")

        self._out_var = ctk.StringVar(value=self._app.settings.get(
            "backup_dir", str(Path.home() / "Downloads" / "backup")))
        ctk.CTkEntry(out_row, textvariable=self._out_var,
                     font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
                     border_width=1, text_color=TEXT_DIM, height=36,
                     ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(out_row, text="Change", width=90, height=36,
                      font=FONT_SMALL, fg_color=INPUT, hover_color=CARD2,
                      border_color=BORDER, border_width=1, text_color=TEXT_DIM,
                      corner_radius=8, command=self._browse_output).pack(side="left")

        # ── Progress bar (hidden until backup)
        self._prog_frame = ctk.CTkFrame(body, fg_color=CARD, corner_radius=10, height=52)
        self._prog_frame.grid(row=4, column=0, sticky="ew")
        self._prog_frame.grid_remove()  # Initially hidden
        self._prog_bar = ctk.CTkProgressBar(self._prog_frame,
                                             progress_color=ACCENT, fg_color=INPUT,
                                             corner_radius=4, height=6)
        self._prog_bar.set(0)
        self._prog_bar.pack(side="left", padx=(16, 10), pady=18, fill="x", expand=True)
        self._prog_lbl = ctk.CTkLabel(self._prog_frame, text="0%",
                                       font=("Consolas", 11), text_color=ACCENT, width=40)
        self._prog_lbl.pack(side="left", padx=(0, 16))

        # ── Action bar
        act = ctk.CTkFrame(body, fg_color=CARD, corner_radius=10, height=62)
        act.grid(row=5, column=0, sticky="ew")
        act.grid_propagate(False)

        left_btns = ctk.CTkFrame(act, fg_color="transparent")
        left_btns.pack(side="left", padx=14, pady=10)

        self._scan_btn = ctk.CTkButton(
            left_btns, text="⟳  Scan", width=120, height=38,
            font=("Segoe UI", 11, "bold"),
            fg_color=INPUT, hover_color=CARD2,
            border_color=ACCENT, border_width=1, text_color=ACCENT,
            corner_radius=8, command=self._trigger_scan,
        )
        self._scan_btn.pack(side="left", padx=(0, 8))

        self._dry_btn = ctk.CTkButton(
            left_btns, text="⊙  Dry Run", width=120, height=38,
            font=("Segoe UI", 11, "bold"),
            fg_color=INPUT, hover_color=CARD2,
            border_color=WARNING, border_width=1, text_color=WARNING,
            corner_radius=8, command=self._trigger_dry_run, state="disabled",
        )
        self._dry_btn.pack(side="left")

        self._backup_btn = ctk.CTkButton(
            act, text="▶  Backup Now", width=160, height=38,
            font=("Segoe UI", 11, "bold"),
            fg_color=ACCENT_GLOW, hover_color="#60b0ff",
            text_color="#0d1117", corner_radius=8,
            command=self._trigger_backup, state="disabled",
        )
        self._backup_btn.pack(side="right", padx=14, pady=10)

    # ── Navigation helpers
    def _browse(self) -> None:
        d = filedialog.askdirectory(title="Select project directory",
                                    initialdir=self._path_var.get())
        if d:
            self._path_var.set(d)
            self._trigger_scan()

    def _browse_output(self) -> None:
        d = filedialog.askdirectory(title="Select output directory",
                                    initialdir=self._out_var.get())
        if d:
            self._out_var.set(d)
            self._app.settings["backup_dir"] = d
            save_settings(self._app.settings)

    # ── Scan
    def _trigger_scan(self) -> None:
        raw = self._path_var.get().strip()
        source = Path(raw).resolve()
        if not source.is_dir():
            self._set_status("Not a valid directory", DANGER)
            self._stat_status.set("Error", DANGER)
            return
        if self._scan_thread and self._scan_thread.is_alive():
            return

        self._source = source
        self._scanned_files = None
        self._scan_btn.configure(text="⟳  Scanning…", state="disabled")
        self._dry_btn.configure(state="disabled")
        self._backup_btn.configure(state="disabled")
        self._set_status("Scanning…", WARNING)
        self._stat_files.set("…", TEXT_MUTED)
        self._stat_size.set("…", TEXT_MUTED)
        self._stat_status.set("Scanning", WARNING)

        self._clear_scroll(self._inc_scroll)
        ctk.CTkLabel(self._inc_scroll, text="Scanning…",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(pady=20)
        self._clear_scroll(self._exc_scroll)

        config = _build_config(self._app.settings)
        rules = ExclusionRules.build(config)

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

    # ── Backup
    def _trigger_backup(self) -> None:
        if not self._scanned_files or not self._source:
            return
        if self._backup_thread and self._backup_thread.is_alive():
            return

        config = _build_config(self._app.settings)
        out_dir = Path(self._out_var.get()).expanduser().resolve()
        destination = make_destination(self._source, out_dir)

        self._backup_btn.configure(state="disabled", text="Backing up…")
        self._scan_btn.configure(state="disabled")
        self._dry_btn.configure(state="disabled")
        self._set_status("Backing up…", ACCENT)
        self._stat_status.set("Backing up", ACCENT)

        self._prog_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        self._prog_bar.set(0)
        self._prog_lbl.configure(text="0%")

        files = list(self._scanned_files)
        total = len(files)

        def _run():
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                import zipfile
                _CMAP = {
                    "deflated": zipfile.ZIP_DEFLATED,
                    "stored":   zipfile.ZIP_STORED,
                    "bzip2":    zipfile.ZIP_BZIP2,
                    "lzma":     zipfile.ZIP_LZMA,
                }
                comp = _CMAP.get(config.compression, zipfile.ZIP_DEFLATED)
                with zipfile.ZipFile(destination, "w", compression=comp) as zf:
                    for i, file in enumerate(files, 1):
                        arcname = file.relative_to(self._source.parent)
                        try:
                            zf.write(file, arcname)
                        except (PermissionError, OSError):
                            pass
                        self._q.put(("progress", i / total, i, total))
                size = destination.stat().st_size
                self._q.put(("backup_done", destination, total, size))
            except Exception as e:
                self._q.put(("backup_error", str(e)))

        self._backup_thread = threading.Thread(target=_run, daemon=True)
        self._backup_thread.start()

    # ── Queue polling
    def _poll(self) -> None:
        try:
            while True:
                msg = self._q.get_nowait()
                self._handle(msg)
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _handle(self, msg: tuple) -> None:
        kind = msg[0]

        if kind == "scan_done":
            _, files, stats = msg
            self._scanned_files = files
            self._scanned_stats = stats
            self._scan_btn.configure(text="⟳  Scan", state="normal")
            self._dry_btn.configure(state="normal")
            self._backup_btn.configure(state="normal")

            total_size = sum(f.stat().st_size for f in files if f.exists())
            self._stat_files.set(f"{len(files):,}", SUCCESS)
            self._stat_size.set(_fmt_size(total_size), ACCENT)
            self._stat_status.set("Ready  ✓", SUCCESS)
            self._set_status(f"Found {len(files):,} files · ready to back up", SUCCESS)

            # Populate included list with styled rows
            self._clear_scroll(self._inc_scroll)
            show_max = 120
            for f in files[:show_max]:
                rel = str(f.relative_to(self._source.parent))
                row = ctk.CTkFrame(self._inc_scroll, fg_color="transparent")
                row.pack(fill="x", pady=1)
                ctk.CTkLabel(row, text="✓", font=("Segoe UI", 9, "bold"),
                             text_color=SUCCESS, width=16).pack(side="left", padx=(2, 6))
                ctk.CTkLabel(row, text=rel, font=FONT_MONO,
                             text_color=TEXT_DIM, anchor="w").pack(
                    side="left", fill="x", expand=True)

            if len(files) > show_max:
                ctk.CTkFrame(self._inc_scroll, fg_color=BORDER_SUB,
                              height=1).pack(fill="x", pady=6)
                ctk.CTkLabel(self._inc_scroll,
                             text=f"… and {len(files) - show_max:,} more files",
                             font=FONT_SMALL, text_color=TEXT_MUTED).pack(pady=(0, 8))

            # Populate excluded list with styled badges
            self._clear_scroll(self._exc_scroll)
            for dname, count in sorted(stats.excluded_dirs.items(), key=lambda x: -x[1]):
                badge = ctk.CTkFrame(self._exc_scroll, fg_color=DANGER_DIM,
                                      corner_radius=6,
                                      border_color="#4a1f1a", border_width=1)
                badge.pack(fill="x", pady=1)
                inner = ctk.CTkFrame(badge, fg_color="transparent")
                inner.pack(fill="x", padx=10, pady=2)
                ctk.CTkLabel(inner, text="✕", font=("Segoe UI", 9, "bold"),
                             text_color=DANGER, width=14).pack(side="left", padx=(0, 6))
                ctk.CTkLabel(inner, text=f"{dname}/", font=FONT_MONO,
                             text_color="#d07070", anchor="w").pack(
                    side="left", fill="x", expand=True)
                pill = ctk.CTkFrame(inner, fg_color="#3d1a18", corner_radius=4,
                                     border_color=DANGER, border_width=1)
                pill.pack(side="right")
                ctk.CTkLabel(pill, text=f"{count:,}", font=("Consolas", 9),
                             text_color=DANGER).pack(padx=6, pady=0)

            if stats.excluded_files:
                ctk.CTkFrame(self._exc_scroll, fg_color=BORDER_SUB,
                              height=1).pack(fill="x", pady=4)
                ctk.CTkLabel(self._exc_scroll,
                             text=f"+{stats.excluded_files} files by pattern",
                             font=FONT_SMALL, text_color=TEXT_MUTED).pack(
                    pady=(0, 4), anchor="w", padx=4)

        elif kind == "scan_error":
            _, err = msg
            self._scan_btn.configure(text="⟳  Scan", state="normal")
            self._set_status(f"Scan error: {err}", DANGER)
            self._stat_status.set("Error", DANGER)

        elif kind == "progress":
            _, pct, i, total = msg
            self._prog_bar.set(pct)
            self._prog_lbl.configure(text=f"{int(pct * 100)}%")

        elif kind == "backup_done":
            _, dest, count, size = msg
            self._prog_frame.grid_remove()
            self._scan_btn.configure(state="normal")
            self._dry_btn.configure(state="normal")
            self._backup_btn.configure(state="normal", text="▶  Backup Now")
            self._set_status(f"Saved  {_fmt_size(size)}", SUCCESS)
            self._stat_status.set("Done  ✓", SUCCESS)
            add_history_entry({
                "timestamp": datetime.now().isoformat(),
                "source": str(self._source),
                "destination": str(dest),
                "files": count,
                "size": size,
            })
            self._app.refresh_history()
            SuccessToast(self._app, dest, count, size)
            # Reset UI to default state after backup
            self._reset_ui()

        elif kind == "backup_error":
            _, err = msg
            self._prog_frame.grid_remove()
            self._scan_btn.configure(state="normal")
            self._dry_btn.configure(state="normal")
            self._backup_btn.configure(state="normal", text="▶  Backup Now")
            self._set_status(f"Error: {err}", DANGER)
            self._stat_status.set("Error", DANGER)

    def _reset_ui(self) -> None:
        """Reset UI to default state after backup completion."""
        # Clear project directory
        self._path_var.set("")
        self._source = None
        
        # Clear preview panels only - let them show empty state naturally
        self._clear_scroll(self._inc_scroll)
        self._clear_scroll(self._exc_scroll)
        
        # Reset stat cards
        self._stat_files.set("â\u20ac\"", TEXT)
        self._stat_size.set("â\u20ac\"", TEXT)
        self._stat_status.set("Waiting", TEXT_MUTED)
        
        # Reset buttons
        self._scan_btn.configure(state="normal")
        self._dry_btn.configure(state="disabled")
        self._backup_btn.configure(state="disabled", text="â\u20ac  Backup Now")
        
        # Reset status
        self._set_status("Ready", TEXT_MUTED)
        
        # Hide progress bar
        self._prog_frame.grid_remove()


# ---------------------------------------------------------------------------
# History frame
# ---------------------------------------------------------------------------

class HistoryFrame(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, corner_radius=0, fg_color=BG, **kw)
        self._build()

    def _build(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="History", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=22)

        self._list_frame = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self._list_frame.pack(fill="both", expand=True, padx=18, pady=16)
        self.refresh()

    def refresh(self) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()
        entries = list(reversed(load_history()))
        if not entries:
            ctk.CTkLabel(self._list_frame, text="No backups yet.",
                         font=FONT_BODY, text_color=TEXT_MUTED).pack(pady=60)
            return
        for entry in entries:
            self._row(entry)

    def _row(self, entry: dict) -> None:
        ts = entry.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            ts_str = dt.strftime("%d %b %Y  %H:%M")
        except Exception:
            ts_str = ts

        card = ctk.CTkFrame(self._list_frame, fg_color=CARD,
                             corner_radius=10, border_color=BORDER, border_width=1)
        card.pack(fill="x", pady=5)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", padx=16, pady=12, fill="x", expand=True)

        src = Path(entry.get("source", "?")).name
        ctk.CTkLabel(left, text=src, font=FONT_HEAD, text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(left, text=entry.get("destination", ""),
                     font=FONT_MONO, text_color=TEXT_DIM, wraplength=480,
                     ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(left, text=ts_str, font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(card, fg_color="transparent")
        right.pack(side="right", padx=16, pady=12)
        ctk.CTkLabel(right, text=_fmt_size(entry.get("size", 0)),
                     font=("Segoe UI", 13, "bold"), text_color=ACCENT).pack(anchor="e")
        ctk.CTkLabel(right, text=f"{entry.get('files', 0):,} files",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="e")


# ---------------------------------------------------------------------------
# Settings frame
# ---------------------------------------------------------------------------

class SettingsFrame(ctk.CTkFrame):
    def __init__(self, master, app: "BackupApp", **kw):
        super().__init__(master, corner_radius=0, fg_color=BG, **kw)
        self._app = app
        self._build()

    def _build(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Settings", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=22)

        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=18, pady=16)

        s = self._app.settings

        SectionLabel(scroll, "OUTPUT DIRECTORY").pack(anchor="w", pady=(0, 6))
        self._out_var = ctk.StringVar(value=s.get("backup_dir", ""))
        out_row = ctk.CTkFrame(scroll, fg_color="transparent")
        out_row.pack(fill="x", pady=(0, 20))
        ctk.CTkEntry(out_row, textvariable=self._out_var, font=FONT_MONO,
                     fg_color=INPUT, border_color=BORDER, border_width=1,
                     text_color=TEXT, height=36).pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(out_row, text="Browse", width=90, height=36,
                      font=FONT_SMALL, fg_color=INPUT, border_color=BORDER,
                      border_width=1, hover_color=CARD2, text_color=TEXT_DIM,
                      corner_radius=8, command=self._browse_out).pack(side="left")

        SectionLabel(scroll, "COMPRESSION").pack(anchor="w", pady=(0, 6))
        self._comp_var = ctk.StringVar(value=s.get("compression", "deflated"))
        ctk.CTkOptionMenu(scroll, values=["deflated", "stored", "bzip2", "lzma"],
                          variable=self._comp_var, fg_color=INPUT,
                          button_color=ACCENT_DIM, button_hover_color=ACCENT,
                          text_color=TEXT, font=FONT_BODY, corner_radius=8,
                          ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(scroll,
                     text="deflated = best balance  ·  stored = no compression  "
                          "·  bzip2/lzma = maximum compression",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 20))

        SectionLabel(scroll, "EXTRA EXCLUDED DIRECTORIES").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(scroll, text="Comma-separated names added on top of defaults",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 4))
        self._dirs_var = ctk.StringVar(value=s.get("extra_dirs", ""))
        ctk.CTkEntry(scroll, textvariable=self._dirs_var,
                     placeholder_text="scratch, my-cache, generated",
                     font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
                     border_width=1, text_color=TEXT, height=36).pack(fill="x", pady=(0, 20))

        SectionLabel(scroll, "EXTRA EXCLUDED EXTENSIONS").pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(scroll, text="Comma-separated extensions to skip",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 4))
        self._exts_var = ctk.StringVar(value=s.get("extra_extensions", ""))
        ctk.CTkEntry(scroll, textvariable=self._exts_var,
                     placeholder_text=".bak, .tmp, .swp",
                     font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
                     border_width=1, text_color=TEXT, height=36).pack(fill="x", pady=(0, 20))

        SectionLabel(scroll, "DEFAULT EXCLUSIONS").pack(anchor="w", pady=(0, 6))
        self._defaults_var = ctk.BooleanVar(value=s.get("include_defaults", True))
        ctk.CTkSwitch(scroll, text="Include built-in exclusion rules",
                      variable=self._defaults_var, font=FONT_BODY, text_color=TEXT,
                      button_color=ACCENT, progress_color=ACCENT_DIM).pack(
            anchor="w", pady=(0, 4))
        ctk.CTkLabel(scroll,
                     text="Disable only if you want full control via custom rules",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 24))

        self._save_btn = ctk.CTkButton(
            scroll, text="Save Settings", width=160, height=40,
            font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT_GLOW, hover_color="#60b0ff",
            text_color="#0d1117", corner_radius=8,
            command=self._save,
        )
        self._save_btn.pack(anchor="w")

    def _browse_out(self) -> None:
        d = filedialog.askdirectory(title="Select output directory",
                                    initialdir=self._out_var.get())
        if d:
            self._out_var.set(d)

    def _save(self) -> None:
        self._app.settings.update({
            "backup_dir": self._out_var.get().strip(),
            "compression": self._comp_var.get(),
            "extra_dirs": self._dirs_var.get().strip(),
            "extra_extensions": self._exts_var.get().strip(),
            "include_defaults": self._defaults_var.get(),
        })
        save_settings(self._app.settings)
        self._save_btn.configure(text="✓  Saved!", fg_color=SUCCESS)
        self.after(2000, lambda: self._save_btn.configure(
            text="Save Settings", fg_color=ACCENT_GLOW))


# ---------------------------------------------------------------------------
# Dry-run popup
# ---------------------------------------------------------------------------

class DryRunWindow(ctk.CTkToplevel):
    def __init__(self, master, source: Path, files: list[Path], stats: ExclusionStats):
        super().__init__(master)
        self.title("Dry Run — Backup Preview")
        self.geometry("760x600")
        self.configure(fg_color=CARD)
        self.grab_set()

        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="Dry Run Preview",
                     font=FONT_TITLE, text_color=TEXT).pack(side="left", padx=22)

        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=20, pady=14)

        ctk.CTkLabel(body, text=str(source), font=FONT_MONO,
                     text_color=ACCENT).pack(anchor="w", pady=(0, 10))

        total_size = sum(f.stat().st_size for f in files if f.exists())
        stats_row = ctk.CTkFrame(body, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, 12))
        stats_row.columnconfigure((0, 1), weight=1)
        StatCard(stats_row, "FILES TO BACK UP", f"{len(files):,}", SUCCESS).grid(
            row=0, column=0, sticky="ew", padx=(0, 6))
        StatCard(stats_row, "UNCOMPRESSED SIZE", _fmt_size(total_size), ACCENT).grid(
            row=0, column=1, sticky="ew")

        exc_parts = []
        for dname, count in sorted(stats.excluded_dirs.items(), key=lambda x: -x[1]):
            exc_parts.append(f"  ✕  {dname}/  ({count:,} files)")
        if stats.excluded_files:
            exc_parts.append(f"  +{stats.excluded_files} files excluded by pattern")
        if exc_parts:
            SectionLabel(body, "EXCLUDED").pack(anchor="w", pady=(0, 4))
            ctk.CTkLabel(body, text="\n".join(exc_parts), font=FONT_MONO,
                         text_color=DANGER, justify="left").pack(anchor="w", pady=(0, 10))

        SectionLabel(body, "INCLUDED FILES").pack(anchor="w", pady=(0, 4))
        box = ctk.CTkTextbox(body, fg_color=CARD, border_color=BORDER,
                              border_width=1, font=FONT_MONO, text_color=TEXT_DIM,
                              corner_radius=8)
        box.pack(fill="both", expand=True, pady=(0, 12))
        lines = []
        for f in files:
            rel = f.relative_to(source.parent)
            size = f.stat().st_size if f.exists() else 0
            lines.append(f"  ✓  {rel}  ({_fmt_size(size)})")
        box.insert("0.0", "\n".join(lines))
        box.configure(state="disabled")

        ctk.CTkButton(body, text="Close", width=120, height=38,
                      fg_color=INPUT, border_color=BORDER, border_width=1,
                      hover_color=CARD2, text_color=TEXT_DIM, corner_radius=8,
                      command=self.destroy).pack(anchor="e")


# ---------------------------------------------------------------------------
# Success toast
# ---------------------------------------------------------------------------

class SuccessToast(ctk.CTkToplevel):
    def __init__(self, master, dest: Path, count: int, size: int):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color=CARD)
        self.attributes("-topmost", True)

        master.update_idletasks()
        mx = master.winfo_x() + master.winfo_width()
        my = master.winfo_y() + master.winfo_height()
        self.geometry(f"380x100+{mx - 400}+{my - 120}")

        inner = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12,
                              border_color=SUCCESS, border_width=1)
        inner.pack(fill="both", expand=True, padx=2, pady=2)
        ctk.CTkLabel(inner, text="✓  Backup complete",
                     font=("Segoe UI", 12, "bold"), text_color=SUCCESS).pack(
            anchor="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(inner, text=f"{dest.name}  ·  {count:,} files  ·  {_fmt_size(size)}",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="w", padx=16)
        ctk.CTkLabel(inner, text=str(dest.parent),
                     font=FONT_MONO, text_color=TEXT_MUTED).pack(
            anchor="w", padx=16, pady=(2, 12))
        self.after(5000, self.destroy)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

def _create_logo_image(size: int = 64) -> Image.Image:
    """Create a logo image with a drawn box shape."""
    # Create a new image with transparent background
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Draw background circle
    bg_color = (88, 166, 255, 255)  # ACCENT color
    draw.ellipse([2, 2, size-2, size-2], fill=bg_color)
    
    # Draw a simple box shape
    box_size = int(size * 0.5)
    box_x = (size - box_size) // 2
    box_y = (size - box_size) // 2
    
    # Box outline
    draw.rectangle([box_x, box_y, box_x + box_size, box_y + box_size], 
                  outline=(255, 255, 255, 255), width=2)
    
    # Box lid lines (to make it look like a package)
    lid_offset = int(box_size * 0.3)
    draw.line([box_x, box_y + lid_offset, box_x + box_size, box_y + lid_offset],
             fill=(255, 255, 255, 255), width=2)
    draw.line([box_x + box_size//2, box_y, box_x + box_size//2, box_y + box_size],
             fill=(255, 255, 255, 255), width=2)
    
    return img


def _save_logo_as_ico(output_path: str = "logo.ico") -> None:
    """Save the logo as a .ico file for use as exe icon."""
    try:
        # Create multiple sizes for the .ico file
        sizes = [16, 32, 48, 64, 128, 256]
        images = []
        
        for size in sizes:
            img = _create_logo_image(size)
            images.append(img)
        
        # Save as .ico file
        images[0].save(output_path, format="ICO", sizes=[(img.width, img.height) for img in images])
        print(f"Logo saved as {output_path}")
    except Exception as e:
        print(f"Failed to save logo: {e}")


class BackupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.title("Backup Project")
        self.geometry("1020x720")
        self.minsize(820, 580)
        self.configure(fg_color=CARD)

        # Set window icon
        try:
            logo_img = _create_logo_image(64)
            self.iconphoto(True, ImageTk.PhotoImage(logo_img))
        except Exception:
            pass  # Fail silently if icon creation fails

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._frames: dict[str, ctk.CTkFrame] = {}
        self._build()
        
        # Center window on screen
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._sidebar = Sidebar(self, on_navigate=self._navigate)
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        self._content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.rowconfigure(0, weight=1)
        self._content.columnconfigure(0, weight=1)

        self._frames["home"]     = HomeFrame(self._content, self)
        self._frames["history"]  = HistoryFrame(self._content)
        self._frames["settings"] = SettingsFrame(self._content, self)

        self._navigate("home")

    def _navigate(self, page_id: str) -> None:
        for fid, frame in self._frames.items():
            if fid == page_id:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

    def refresh_history(self) -> None:
        self._frames["history"].refresh()


def main() -> None:
    app = BackupApp()
    app.mainloop()


if __name__ == "__main__":
    main()