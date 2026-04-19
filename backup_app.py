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

# ---------------------------------------------------------------------------
# CLI passthrough — must come before any CTk import so headless envs work
# ---------------------------------------------------------------------------

def _cli_passthrough() -> None:
    """If the first arg is -c, strip it and delegate to the CLI."""
    sys.argv = [sys.argv[0]] + sys.argv[2:]
    from backup_project import main as cli_main
    sys.exit(cli_main())


if len(sys.argv) > 1 and sys.argv[1] == "-c":
    _cli_passthrough()

# ---------------------------------------------------------------------------
# GUI imports
# ---------------------------------------------------------------------------

import customtkinter as ctk

# Import core logic (no GUI involved)
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

BG          = "#0d1117"   # canvas / window background
CARD        = "#161b22"   # card / panel background
INPUT       = "#21262d"   # input / entry background
BORDER      = "#30363d"   # subtle borders
ACCENT      = "#58a6ff"   # primary blue
ACCENT_DIM  = "#1f4070"   # muted blue (hover states, badges)
SUCCESS     = "#3fb950"   # green
WARNING     = "#d29922"   # amber
DANGER      = "#f85149"   # red
TEXT        = "#e6edf3"   # primary text
TEXT_DIM    = "#8b949e"   # secondary / muted text
TEXT_MUTED  = "#484f58"   # very muted text (labels, hints)

FONT_TITLE  = ("Segoe UI", 20, "bold")
FONT_HEAD   = ("Segoe UI", 13, "bold")
FONT_BODY   = ("Segoe UI", 12)
FONT_SMALL  = ("Segoe UI", 10)
FONT_MONO   = ("Consolas", 11)

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
# Sidebar
# ---------------------------------------------------------------------------

class Sidebar(ctk.CTkFrame):
    PAGES = [
        ("home",     "⌂",  "Backup"),
        ("history",  "◷",  "History"),
        ("settings", "⚙",  "Settings"),
    ]

    def __init__(self, master, on_navigate, **kw):
        super().__init__(master, width=72, corner_radius=0,
                         fg_color=CARD, **kw)
        self.pack_propagate(False)
        self._on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active = "home"

        # Logo
        ctk.CTkLabel(self, text="📦", font=("Segoe UI", 26),
                     text_color=ACCENT).pack(pady=(22, 18))

        for page_id, icon, label in self.PAGES:
            btn = ctk.CTkButton(
                self,
                text=f"{icon}\n{label}",
                font=("Segoe UI", 9),
                width=60, height=60,
                corner_radius=10,
                fg_color="transparent",
                hover_color=INPUT,
                text_color=TEXT_DIM,
                command=lambda pid=page_id: self._select(pid),
            )
            btn.pack(pady=4, padx=6)
            self._buttons[page_id] = btn

        self._select("home")

    def _select(self, page_id: str) -> None:
        for pid, btn in self._buttons.items():
            btn.configure(
                fg_color=ACCENT_DIM if pid == page_id else "transparent",
                text_color=ACCENT if pid == page_id else TEXT_DIM,
            )
        self._active = page_id
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

    # ── layout ──────────────────────────────────────────────────────────

    def _build(self) -> None:
        # Title bar
        title_bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=56)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        ctk.CTkLabel(title_bar, text="Backup", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=22, pady=14)
        self._status_dot = ctk.CTkLabel(title_bar, text="●", font=("Segoe UI", 14),
                                         text_color=TEXT_MUTED)
        self._status_dot.pack(side="right", padx=10)
        self._status_lbl = ctk.CTkLabel(title_bar, text="Ready",
                                         font=FONT_SMALL, text_color=TEXT_DIM)
        self._status_lbl.pack(side="right", padx=4)

        # Body
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=20, pady=16)

        # ── Source picker card ───────────────────────────────────────────
        src_card = self._card(body, "PROJECT DIRECTORY")
        src_card.pack(fill="x", pady=(0, 12))

        row = ctk.CTkFrame(src_card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))

        self._path_var = ctk.StringVar(value=str(Path.cwd()))
        path_entry = ctk.CTkEntry(
            row, textvariable=self._path_var,
            font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
            text_color=TEXT, placeholder_text="Select a project directory…",
        )
        path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        path_entry.bind("<Return>", lambda _: self._trigger_scan())

        ctk.CTkButton(row, text="Browse", width=90, height=34,
                      font=FONT_SMALL, fg_color=INPUT, hover_color=BORDER,
                      border_color=BORDER, border_width=1,
                      text_color=TEXT_DIM,
                      command=self._browse).pack(side="left")

        # ── Preview row ──────────────────────────────────────────────────
        preview_row = ctk.CTkFrame(body, fg_color="transparent")
        preview_row.pack(fill="both", expand=True, pady=(0, 12))
        preview_row.columnconfigure(0, weight=3)
        preview_row.columnconfigure(1, weight=2)
        preview_row.rowconfigure(0, weight=1)

        # Included panel
        inc_card = self._card(preview_row, "WILL BE BACKED UP")
        inc_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._inc_stats = ctk.CTkLabel(
            inc_card, text="Scan a directory to preview",
            font=FONT_SMALL, text_color=TEXT_MUTED,
        )
        self._inc_stats.pack(padx=16, pady=(0, 8), anchor="w")
        self._inc_list = ctk.CTkTextbox(
            inc_card, fg_color=INPUT, border_color=BORDER,
            font=FONT_MONO, text_color=TEXT_DIM,
            state="disabled", height=200,
        )
        self._inc_list.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # Excluded panel
        exc_card = self._card(preview_row, "EXCLUDED")
        exc_card.grid(row=0, column=1, sticky="nsew")
        self._exc_list = ctk.CTkTextbox(
            exc_card, fg_color=INPUT, border_color=BORDER,
            font=FONT_MONO, text_color=TEXT_DIM,
            state="disabled",
        )
        self._exc_list.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # ── Output + actions ─────────────────────────────────────────────
        bottom = ctk.CTkFrame(body, fg_color="transparent")
        bottom.pack(fill="x")

        out_card = self._card(bottom, "OUTPUT")
        out_card.pack(fill="x", pady=(0, 12))
        out_row = ctk.CTkFrame(out_card, fg_color="transparent")
        out_row.pack(fill="x", padx=16, pady=(0, 14))
        self._out_var = ctk.StringVar(value=self._app.settings.get(
            "backup_dir", str(Path.home() / "Downloads" / "backup")))
        ctk.CTkEntry(
            out_row, textvariable=self._out_var,
            font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
            text_color=TEXT,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            out_row, text="Change", width=90, height=34,
            font=FONT_SMALL, fg_color=INPUT, hover_color=BORDER,
            border_color=BORDER, border_width=1, text_color=TEXT_DIM,
            command=self._browse_output,
        ).pack(side="left")

        # Action buttons
        act = ctk.CTkFrame(body, fg_color="transparent")
        act.pack(fill="x", pady=(0, 8))
        self._scan_btn = ctk.CTkButton(
            act, text="⟳  Scan", width=130, height=42,
            font=("Segoe UI", 12, "bold"),
            fg_color=INPUT, hover_color=BORDER,
            border_color=ACCENT, border_width=1,
            text_color=ACCENT,
            command=self._trigger_scan,
        )
        self._scan_btn.pack(side="left", padx=(0, 10))

        self._dry_btn = ctk.CTkButton(
            act, text="⊙  Dry Run", width=130, height=42,
            font=("Segoe UI", 12, "bold"),
            fg_color=INPUT, hover_color=BORDER,
            border_color=WARNING, border_width=1,
            text_color=WARNING,
            command=self._trigger_dry_run,
            state="disabled",
        )
        self._dry_btn.pack(side="left", padx=(0, 10))

        self._backup_btn = ctk.CTkButton(
            act, text="▶  Backup Now", width=160, height=42,
            font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color="#79b8ff",
            text_color="#0d1117",
            command=self._trigger_backup,
            state="disabled",
        )
        self._backup_btn.pack(side="right")

        # ── Progress bar (hidden until needed) ───────────────────────────
        self._prog_frame = ctk.CTkFrame(body, fg_color=CARD,
                                         corner_radius=10, height=60)
        self._prog_frame.pack_forget()  # hidden initially
        self._prog_bar = ctk.CTkProgressBar(
            self._prog_frame, width=400,
            progress_color=ACCENT, fg_color=INPUT,
        )
        self._prog_bar.set(0)
        self._prog_bar.pack(side="left", padx=(16, 12), pady=18, fill="x", expand=True)
        self._prog_lbl = ctk.CTkLabel(
            self._prog_frame, text="0%", font=FONT_SMALL,
            text_color=TEXT_DIM, width=40,
        )
        self._prog_lbl.pack(side="left", padx=(0, 16))

    # ── helpers ─────────────────────────────────────────────────────────

    def _card(self, parent, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10,
                              border_color=BORDER, border_width=1)
        ctk.CTkLabel(frame, text=title, font=("Segoe UI", 9, "bold"),
                     text_color=TEXT_MUTED).pack(
            anchor="w", padx=16, pady=(12, 6))
        return frame

    def _set_text(self, widget: ctk.CTkTextbox, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("0.0", "end")
        widget.insert("0.0", text)
        widget.configure(state="disabled")

    def _set_status(self, msg: str, color: str = TEXT_DIM) -> None:
        self._status_lbl.configure(text=msg)
        self._status_dot.configure(text_color=color)

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

    # ── scan ────────────────────────────────────────────────────────────

    def _trigger_scan(self) -> None:
        raw = self._path_var.get().strip()
        source = Path(raw).resolve()
        if not source.is_dir():
            self._set_status("Not a valid directory", DANGER)
            return
        if self._scan_thread and self._scan_thread.is_alive():
            return

        self._source = source
        self._scanned_files = None
        self._scan_btn.configure(text="⟳  Scanning…", state="disabled")
        self._dry_btn.configure(state="disabled")
        self._backup_btn.configure(state="disabled")
        self._set_status("Scanning…", WARNING)
        self._set_text(self._inc_list, "Scanning…")
        self._set_text(self._exc_list, "")

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
        """Show a popup with the full dry-run report."""
        if not self._scanned_files:
            return
        DryRunWindow(self._app, self._source, self._scanned_files,
                     self._scanned_stats)

    # ── backup ───────────────────────────────────────────────────────────

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

        # Show progress bar
        self._prog_frame.pack(fill="x", pady=(0, 8))
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
                        arcname = file.relative_to(self._source)
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

    # ── queue polling ────────────────────────────────────────────────────

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
            self._inc_stats.configure(
                text=f"{len(files)} files  ·  {_fmt_size(total_size)} uncompressed",
                text_color=SUCCESS,
            )

            # Fill included list
            lines = []
            for f in files[:80]:
                rel = f.relative_to(self._source)
                lines.append(f"✓  {rel}")
            if len(files) > 80:
                lines.append(f"\n… and {len(files) - 80} more files")
            self._set_text(self._inc_list, "\n".join(lines))

            # Fill excluded list
            exc_lines = []
            for dname, count in sorted(stats.excluded_dirs.items(), key=lambda x: -x[1]):
                exc_lines.append(f"✗  {dname}/  ({count} files)")
            if stats.excluded_files:
                exc_lines.append(f"\n+{stats.excluded_files} files by pattern")
            self._set_text(self._exc_list, "\n".join(exc_lines) if exc_lines else "None")
            self._set_status(f"Found {len(files)} files", SUCCESS)

        elif kind == "scan_error":
            _, err = msg
            self._scan_btn.configure(text="⟳  Scan", state="normal")
            self._set_status(f"Scan error: {err}", DANGER)

        elif kind == "progress":
            _, pct, i, total = msg
            self._prog_bar.set(pct)
            self._prog_lbl.configure(text=f"{int(pct*100)}%")

        elif kind == "backup_done":
            _, dest, count, size = msg
            self._prog_frame.pack_forget()
            self._scan_btn.configure(state="normal")
            self._dry_btn.configure(state="normal")
            self._backup_btn.configure(state="normal", text="▶  Backup Now")
            self._set_status(f"Saved  {_fmt_size(size)}", SUCCESS)

            add_history_entry({
                "timestamp": datetime.now().isoformat(),
                "source": str(self._source),
                "destination": str(dest),
                "files": count,
                "size": size,
            })
            self._app.refresh_history()
            SuccessToast(self._app, dest, count, size)

        elif kind == "backup_error":
            _, err = msg
            self._prog_frame.pack_forget()
            self._scan_btn.configure(state="normal")
            self._dry_btn.configure(state="normal")
            self._backup_btn.configure(state="normal", text="▶  Backup Now")
            self._set_status(f"Error: {err}", DANGER)


# ---------------------------------------------------------------------------
# History frame
# ---------------------------------------------------------------------------

class HistoryFrame(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, corner_radius=0, fg_color=BG, **kw)
        self._build()

    def _build(self) -> None:
        title_bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=56)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        ctk.CTkLabel(title_bar, text="History", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=22, pady=14)

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
        )
        self._list_frame.pack(fill="both", expand=True, padx=20, pady=16)
        self.refresh()

    def refresh(self) -> None:
        for w in self._list_frame.winfo_children():
            w.destroy()
        entries = list(reversed(load_history()))
        if not entries:
            ctk.CTkLabel(self._list_frame, text="No backups yet.",
                         font=FONT_BODY, text_color=TEXT_MUTED).pack(pady=40)
            return
        for entry in entries:
            self._row(entry)

    def _row(self, entry: dict) -> None:
        ts = entry.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts)
            ts_str = dt.strftime("%d %b %Y  %H:%M:%S")
        except Exception:
            ts_str = ts

        card = ctk.CTkFrame(self._list_frame, fg_color=CARD,
                             corner_radius=10, border_color=BORDER, border_width=1)
        card.pack(fill="x", pady=5)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", padx=16, pady=12, fill="x", expand=True)

        src = Path(entry.get("source", "?")).name
        ctk.CTkLabel(left, text=src, font=FONT_HEAD, text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text=entry.get("destination", ""),
            font=FONT_MONO, text_color=TEXT_DIM, wraplength=520,
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(left, text=ts_str, font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(card, fg_color="transparent")
        right.pack(side="right", padx=16, pady=12)
        ctk.CTkLabel(right, text=_fmt_size(entry.get("size", 0)),
                     font=("Segoe UI", 13, "bold"), text_color=ACCENT).pack(anchor="e")
        ctk.CTkLabel(right,
                     text=f"{entry.get('files', 0)} files",
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
        title_bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=56)
        title_bar.pack(fill="x")
        title_bar.pack_propagate(False)
        ctk.CTkLabel(title_bar, text="Settings", font=FONT_TITLE,
                     text_color=TEXT).pack(side="left", padx=22, pady=14)

        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=20, pady=16)

        s = self._app.settings

        # ── Output directory ─────────────────────────────────────────────
        self._section(scroll, "OUTPUT DIRECTORY")
        self._out_var = ctk.StringVar(value=s.get("backup_dir", ""))
        out_row = ctk.CTkFrame(scroll, fg_color="transparent")
        out_row.pack(fill="x", pady=(0, 20))
        ctk.CTkEntry(out_row, textvariable=self._out_var,
                     font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
                     text_color=TEXT).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(out_row, text="Browse", width=90, height=34,
                      font=FONT_SMALL, fg_color=INPUT, border_color=BORDER,
                      border_width=1, hover_color=BORDER, text_color=TEXT_DIM,
                      command=self._browse_out).pack(side="left")

        # ── Compression ──────────────────────────────────────────────────
        self._section(scroll, "COMPRESSION")
        self._comp_var = ctk.StringVar(value=s.get("compression", "deflated"))
        ctk.CTkOptionMenu(
            scroll, values=["deflated", "stored", "bzip2", "lzma"],
            variable=self._comp_var,
            fg_color=INPUT, button_color=ACCENT_DIM,
            button_hover_color=ACCENT, text_color=TEXT,
            font=FONT_BODY,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(scroll,
                     text="deflated = best balance  ·  stored = no compression  "
                          "·  bzip2/lzma = maximum compression",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 20))

        # ── Extra exclusions ─────────────────────────────────────────────
        self._section(scroll, "EXTRA EXCLUDED DIRECTORIES")
        ctk.CTkLabel(scroll, text="Comma-separated directory names to add on top of defaults",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 4))
        self._dirs_var = ctk.StringVar(value=s.get("extra_dirs", ""))
        ctk.CTkEntry(scroll, textvariable=self._dirs_var,
                     placeholder_text="scratch, my-cache, generated",
                     font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
                     text_color=TEXT).pack(fill="x", pady=(0, 20))

        self._section(scroll, "EXTRA EXCLUDED EXTENSIONS")
        ctk.CTkLabel(scroll, text="Comma-separated extensions to skip",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 4))
        self._exts_var = ctk.StringVar(value=s.get("extra_extensions", ""))
        ctk.CTkEntry(scroll, textvariable=self._exts_var,
                     placeholder_text=".bak, .tmp, .swp",
                     font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
                     text_color=TEXT).pack(fill="x", pady=(0, 20))

        # ── Default exclusions toggle ─────────────────────────────────────
        self._section(scroll, "DEFAULT EXCLUSIONS")
        self._defaults_var = ctk.BooleanVar(value=s.get("include_defaults", True))
        row = ctk.CTkFrame(scroll, fg_color="transparent")
        row.pack(fill="x", pady=(0, 4))
        ctk.CTkSwitch(row, text="Include built-in exclusion rules",
                      variable=self._defaults_var,
                      font=FONT_BODY, text_color=TEXT,
                      button_color=ACCENT, progress_color=ACCENT_DIM).pack(side="left")
        ctk.CTkLabel(scroll,
                     text="Disable only if you want full control via custom rules",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 24))

        # ── Save button ───────────────────────────────────────────────────
        ctk.CTkButton(
            scroll, text="Save Settings", width=160, height=42,
            font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT, hover_color="#79b8ff",
            text_color="#0d1117",
            command=self._save,
        ).pack(anchor="w")

    def _section(self, parent, title: str) -> None:
        ctk.CTkLabel(parent, text=title, font=("Segoe UI", 9, "bold"),
                     text_color=TEXT_MUTED).pack(anchor="w", pady=(0, 6))

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
        # Flash confirmation
        btn = self.winfo_children()[-1].winfo_children()[-1]  # last child in scroll
        # Simple feedback via status — just resave is enough


# ---------------------------------------------------------------------------
# Dry-run popup
# ---------------------------------------------------------------------------

class DryRunWindow(ctk.CTkToplevel):
    def __init__(self, master, source: Path, files: list[Path],
                 stats: ExclusionStats):
        super().__init__(master)
        self.title("Dry Run — Backup Preview")
        self.geometry("740x580")
        self.configure(fg_color=BG)
        self.grab_set()

        ctk.CTkLabel(self, text="Dry Run Preview", font=FONT_TITLE,
                     text_color=TEXT).pack(anchor="w", padx=24, pady=(20, 4))
        ctk.CTkLabel(self, text=str(source), font=FONT_MONO,
                     text_color=ACCENT).pack(anchor="w", padx=24, pady=(0, 12))

        total_size = sum(f.stat().st_size for f in files if f.exists())
        ctk.CTkLabel(
            self,
            text=f"  {len(files)} files  ·  {_fmt_size(total_size)} uncompressed",
            font=("Segoe UI", 13, "bold"), text_color=SUCCESS,
        ).pack(anchor="w", padx=24, pady=(0, 8))

        exc_parts = []
        for dname, count in sorted(stats.excluded_dirs.items(), key=lambda x: -x[1]):
            exc_parts.append(f"  ✗  {dname}/  ({count} files)")
        if stats.excluded_files:
            exc_parts.append(f"  +{stats.excluded_files} files excluded by pattern")
        if exc_parts:
            ctk.CTkLabel(self, text="Excluded:", font=FONT_HEAD,
                         text_color=TEXT_DIM).pack(anchor="w", padx=24, pady=(4, 2))
            ctk.CTkLabel(self, text="\n".join(exc_parts), font=FONT_MONO,
                         text_color=DANGER, justify="left").pack(anchor="w", padx=24, pady=(0, 10))

        ctk.CTkLabel(self, text="Included files:", font=FONT_HEAD,
                     text_color=TEXT_DIM).pack(anchor="w", padx=24, pady=(0, 4))
        box = ctk.CTkTextbox(self, fg_color=CARD, border_color=BORDER,
                              font=FONT_MONO, text_color=TEXT_DIM)
        box.pack(fill="both", expand=True, padx=24, pady=(0, 16))
        lines = []
        for f in files:
            rel = f.relative_to(source)
            size = f.stat().st_size
            lines.append(f"  ✓  {rel}  ({_fmt_size(size)})")
        box.insert("0.0", "\n".join(lines))
        box.configure(state="disabled")

        ctk.CTkButton(self, text="Close", width=120, height=38,
                      fg_color=INPUT, border_color=BORDER, border_width=1,
                      hover_color=BORDER, text_color=TEXT_DIM,
                      command=self.destroy).pack(pady=(0, 20))


# ---------------------------------------------------------------------------
# Success toast
# ---------------------------------------------------------------------------

class SuccessToast(ctk.CTkToplevel):
    def __init__(self, master, dest: Path, count: int, size: int):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color=CARD)
        self.attributes("-topmost", True)

        # Position: bottom-right of master
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
        ctk.CTkLabel(inner, text=f"{dest.name}  ·  {count} files  ·  {_fmt_size(size)}",
                     font=FONT_SMALL, text_color=TEXT_DIM).pack(anchor="w", padx=16)
        ctk.CTkLabel(inner, text=str(dest.parent),
                     font=FONT_MONO, text_color=TEXT_MUTED).pack(anchor="w", padx=16, pady=(2, 12))

        self.after(5000, self.destroy)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class BackupApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.title("Backup Project")
        self.geometry("1020x680")
        self.minsize(820, 560)
        self.configure(fg_color=BG)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._frames: dict[str, ctk.CTkFrame] = {}
        self._build()

    def _build(self) -> None:
        # Root layout: sidebar | content
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._sidebar = Sidebar(self, on_navigate=self._navigate)
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        self._content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.rowconfigure(0, weight=1)
        self._content.columnconfigure(0, weight=1)

        self._frames["home"] = HomeFrame(self._content, self)
        self._frames["history"] = HistoryFrame(self._content)
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


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    app = BackupApp()
    app.mainloop()


if __name__ == "__main__":
    main()
