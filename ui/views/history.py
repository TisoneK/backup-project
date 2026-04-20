"""
ui/views/history.py — Backup history view.

Displays a chronological list of completed backups loaded from disk.
Refreshed by the app after each successful backup.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from ui.persistence import fmt_size, load_history
from ui.tokens import (
    ACCENT, BG, BORDER, CARD, FONT_HEAD, FONT_MONO,
    FONT_SMALL, FONT_TITLE, TEXT, TEXT_DIM, TEXT_MUTED,
)


class HistoryFrame(ctk.CTkFrame):
    """Read-only view of past backups. Call refresh() to reload from disk."""

    def __init__(self, master, **kw):
        super().__init__(master, corner_radius=0, fg_color=BG, **kw)
        self._build()

    def _build(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(
            topbar, text="History", font=FONT_TITLE, text_color=TEXT,
        ).pack(side="left", padx=22)

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=BG, corner_radius=0,
        )
        self._list_frame.pack(fill="both", expand=True, padx=18, pady=16)
        self.refresh()

    def refresh(self) -> None:
        """Reload history from disk and re-render the list."""
        for w in self._list_frame.winfo_children():
            w.destroy()

        entries = list(reversed(load_history()))
        if not entries:
            ctk.CTkLabel(
                self._list_frame, text="No backups yet.",
                font=("Segoe UI", 12), text_color=TEXT_MUTED,
            ).pack(pady=60)
            return

        for entry in entries:
            self._render_row(entry)

    def _render_row(self, entry: dict) -> None:
        ts = entry.get("timestamp", "")
        try:
            ts_str = datetime.fromisoformat(ts).strftime("%d %b %Y  %H:%M")
        except Exception:
            ts_str = ts

        card = ctk.CTkFrame(
            self._list_frame, fg_color=CARD,
            corner_radius=10, border_color=BORDER, border_width=1,
        )
        card.pack(fill="x", pady=5)

        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", padx=16, pady=12, fill="x", expand=True)

        ctk.CTkLabel(
            left,
            text=Path(entry.get("source", "?")).name,
            font=FONT_HEAD,
            text_color=TEXT,
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text=entry.get("destination", ""),
            font=FONT_MONO,
            text_color=TEXT_DIM,
            wraplength=480,
        ).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(
            left, text=ts_str,
            font=FONT_SMALL, text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        right = ctk.CTkFrame(card, fg_color="transparent")
        right.pack(side="right", padx=16, pady=12)

        ctk.CTkLabel(
            right,
            text=fmt_size(entry.get("size", 0)),
            font=("Segoe UI", 13, "bold"),
            text_color=ACCENT,
        ).pack(anchor="e")
        ctk.CTkLabel(
            right,
            text=f"{entry.get('files', 0):,} files",
            font=FONT_SMALL,
            text_color=TEXT_DIM,
        ).pack(anchor="e")
