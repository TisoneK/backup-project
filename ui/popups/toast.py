"""
ui/popups/toast.py — Success notification toast.

A borderless overlay that auto-dismisses after 5 seconds.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from ui.persistence import fmt_size
from ui.tokens import CARD, FONT_MONO, FONT_SMALL, SUCCESS, TEXT_DIM, TEXT_MUTED


class SuccessToast(ctk.CTkToplevel):
    """
    Transient success notification anchored to the bottom-right of the
    parent window. Destroys itself after 5 seconds.

    Parameters
    ----------
    master:
        Parent window (BackupApp root) used for positioning.
    dest:
        Path of the ZIP that was created.
    count:
        Number of files archived.
    size:
        Byte size of the resulting ZIP.
    """

    DURATION_MS = 5_000

    def __init__(self, master, dest: Path, count: int, size: int):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(fg_color=CARD)
        self.attributes("-topmost", True)

        master.update_idletasks()
        mx = master.winfo_x() + master.winfo_width()
        my = master.winfo_y() + master.winfo_height()
        self.geometry(f"380x100+{mx - 400}+{my - 120}")

        self._build(dest, count, size)
        self.after(self.DURATION_MS, self.destroy)

    def _build(self, dest: Path, count: int, size: int) -> None:
        inner = ctk.CTkFrame(
            self, fg_color=CARD, corner_radius=12,
            border_color=SUCCESS, border_width=1,
        )
        inner.pack(fill="both", expand=True, padx=2, pady=2)

        ctk.CTkLabel(
            inner, text="✓  Backup complete",
            font=("Segoe UI", 12, "bold"), text_color=SUCCESS,
        ).pack(anchor="w", padx=16, pady=(12, 2))

        ctk.CTkLabel(
            inner,
            text=f"{dest.name}  ·  {count:,} files  ·  {fmt_size(size)}",
            font=FONT_SMALL, text_color=TEXT_DIM,
        ).pack(anchor="w", padx=16)

        ctk.CTkLabel(
            inner, text=str(dest.parent),
            font=FONT_MONO, text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=16, pady=(2, 12))
