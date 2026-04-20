"""
ui/views/settings.py — Application settings view.

Reads from and writes to app.settings via persistence.save_settings().
Does not touch any other UI frame directly.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from ui.components import SectionLabel
from ui.persistence import save_settings
from ui.tokens import (
    ACCENT, ACCENT_DIM, ACCENT_GLOW, BG, BORDER, CARD, CARD2,
    FONT_BODY, FONT_MONO, FONT_SMALL, FONT_TITLE, INPUT, SUCCESS, TEXT, TEXT_DIM, TEXT_MUTED,
)


class SettingsFrame(ctk.CTkFrame):
    """
    User preferences: output directory, compression, extra exclusions.

    Receives `app` so it can read/write app.settings in place, keeping
    the settings dict as the single source of truth for the whole app.
    """

    def __init__(self, master, app, **kw):
        super().__init__(master, corner_radius=0, fg_color=BG, **kw)
        self._app = app
        self._build()

    def _build(self) -> None:
        topbar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(
            topbar, text="Settings", font=FONT_TITLE, text_color=TEXT,
        ).pack(side="left", padx=22)

        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=18, pady=16)

        s = self._app.settings

        # Output directory
        SectionLabel(scroll, "OUTPUT DIRECTORY").pack(anchor="w", pady=(0, 6))
        self._out_var = ctk.StringVar(value=s.get("backup_dir", ""))
        out_row = ctk.CTkFrame(scroll, fg_color="transparent")
        out_row.pack(fill="x", pady=(0, 20))
        ctk.CTkEntry(
            out_row, textvariable=self._out_var,
            font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
            border_width=1, text_color=TEXT, height=36,
        ).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(
            out_row, text="Browse", width=90, height=36,
            font=FONT_SMALL, fg_color=INPUT, border_color=BORDER,
            border_width=1, hover_color=CARD2, text_color=TEXT_DIM,
            corner_radius=8, command=self._browse_output,
        ).pack(side="left")

        # Compression
        SectionLabel(scroll, "COMPRESSION").pack(anchor="w", pady=(0, 6))
        self._comp_var = ctk.StringVar(value=s.get("compression", "deflated"))
        ctk.CTkOptionMenu(
            scroll,
            values=["deflated", "stored", "bzip2", "lzma"],
            variable=self._comp_var,
            fg_color=INPUT,
            button_color=ACCENT_DIM,
            button_hover_color=ACCENT,
            text_color=TEXT,
            font=FONT_BODY,
            corner_radius=8,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            scroll,
            text="deflated = best balance  ·  stored = no compression  "
                 "·  bzip2/lzma = maximum compression",
            font=FONT_SMALL, text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 20))

        # Extra excluded directories
        SectionLabel(scroll, "EXTRA EXCLUDED DIRECTORIES").pack(
            anchor="w", pady=(0, 4),
        )
        ctk.CTkLabel(
            scroll, text="Comma-separated names added on top of defaults",
            font=FONT_SMALL, text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 4))
        self._dirs_var = ctk.StringVar(value=s.get("extra_dirs", ""))
        ctk.CTkEntry(
            scroll, textvariable=self._dirs_var,
            placeholder_text="scratch, my-cache, generated",
            font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
            border_width=1, text_color=TEXT, height=36,
        ).pack(fill="x", pady=(0, 20))

        # Extra excluded extensions
        SectionLabel(scroll, "EXTRA EXCLUDED EXTENSIONS").pack(
            anchor="w", pady=(0, 4),
        )
        ctk.CTkLabel(
            scroll, text="Comma-separated extensions to skip",
            font=FONT_SMALL, text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 4))
        self._exts_var = ctk.StringVar(value=s.get("extra_extensions", ""))
        ctk.CTkEntry(
            scroll, textvariable=self._exts_var,
            placeholder_text=".bak, .tmp, .swp",
            font=FONT_MONO, fg_color=INPUT, border_color=BORDER,
            border_width=1, text_color=TEXT, height=36,
        ).pack(fill="x", pady=(0, 20))

        # Default exclusions toggle
        SectionLabel(scroll, "DEFAULT EXCLUSIONS").pack(anchor="w", pady=(0, 6))
        self._defaults_var = ctk.BooleanVar(value=s.get("include_defaults", True))
        ctk.CTkSwitch(
            scroll,
            text="Include built-in exclusion rules",
            variable=self._defaults_var,
            font=FONT_BODY,
            text_color=TEXT,
            button_color=ACCENT,
            progress_color=ACCENT_DIM,
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            scroll,
            text="Disable only if you want full control via custom rules",
            font=FONT_SMALL, text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(0, 24))

        # Save button
        self._save_btn = ctk.CTkButton(
            scroll, text="Save Settings", width=160, height=40,
            font=("Segoe UI", 12, "bold"),
            fg_color=ACCENT_GLOW, hover_color="#60b0ff",
            text_color="#0d1117", corner_radius=8,
            command=self._save,
        )
        self._save_btn.pack(anchor="w")

    def _browse_output(self) -> None:
        d = filedialog.askdirectory(
            title="Select output directory",
            initialdir=self._out_var.get(),
        )
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
            text="Save Settings", fg_color=ACCENT_GLOW,
        ))
