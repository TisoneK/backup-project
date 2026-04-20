"""
ui/popups/dry_run.py — Dry-run preview window.

Shows what would be backed up without writing anything to disk.
Receives already-computed scan results from HomeFrame; does no I/O itself.
"""

from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from backup_project import ExclusionStats
from ui.components import SectionLabel, StatCard
from ui.persistence import fmt_size
from ui.tokens import (
    ACCENT, BG, BORDER, CARD, CARD2,
    DANGER, FONT_MONO, FONT_SMALL, FONT_TITLE,
    INPUT, SUCCESS, TEXT, TEXT_DIM, TEXT_MUTED,
)


class DryRunWindow(ctk.CTkToplevel):
    """
    Modal window summarising a pending backup without executing it.

    Parameters
    ----------
    master:
        Parent window (BackupApp root).
    source:
        Project directory that was scanned.
    files:
        Included file list from _walk_with_stats.
    stats:
        Exclusion stats from _walk_with_stats.
    """

    def __init__(
        self,
        master,
        source: Path,
        files: list[Path],
        stats: ExclusionStats,
    ):
        super().__init__(master)
        self.title("Dry Run — Backup Preview")
        self.geometry("760x600")
        self.configure(fg_color=CARD)
        self.grab_set()

        self._build(source, files, stats)

    def _build(
        self,
        source: Path,
        files: list[Path],
        stats: ExclusionStats,
    ) -> None:
        # Header
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="Dry Run Preview",
            font=FONT_TITLE, text_color=TEXT,
        ).pack(side="left", padx=22)

        # Body
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=20, pady=14)

        ctk.CTkLabel(
            body, text=str(source),
            font=FONT_MONO, text_color=ACCENT,
        ).pack(anchor="w", pady=(0, 10))

        # Stats row
        total_size = sum(f.stat().st_size for f in files if f.exists())
        stats_row = ctk.CTkFrame(body, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, 12))
        stats_row.columnconfigure((0, 1), weight=1)

        StatCard(
            stats_row, "FILES TO BACK UP", f"{len(files):,}", SUCCESS,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

        StatCard(
            stats_row, "UNCOMPRESSED SIZE", fmt_size(total_size), ACCENT,
        ).grid(row=0, column=1, sticky="ew")

        # Excluded summary
        exc_parts = [
            f"  ✕  {dname}/  ({count:,} files)"
            for dname, count in sorted(
                stats.excluded_dirs.items(), key=lambda x: -x[1]
            )
        ]
        if stats.excluded_files:
            exc_parts.append(
                f"  +{stats.excluded_files} files excluded by pattern"
            )
        if exc_parts:
            SectionLabel(body, "EXCLUDED").pack(anchor="w", pady=(0, 4))
            ctk.CTkLabel(
                body, text="\n".join(exc_parts),
                font=FONT_MONO, text_color=DANGER, justify="left",
            ).pack(anchor="w", pady=(0, 10))

        # Full file list
        SectionLabel(body, "INCLUDED FILES").pack(anchor="w", pady=(0, 4))
        box = ctk.CTkTextbox(
            body,
            fg_color=CARD,
            border_color=BORDER,
            border_width=1,
            font=FONT_MONO,
            text_color=TEXT_DIM,
            corner_radius=8,
        )
        box.pack(fill="both", expand=True, pady=(0, 12))

        lines = []
        for f in files:
            rel = f.relative_to(source.parent)
            size = f.stat().st_size if f.exists() else 0
            lines.append(f"  ✓  {rel}  ({fmt_size(size)})")
        box.insert("0.0", "\n".join(lines))
        box.configure(state="disabled")

        ctk.CTkButton(
            body, text="Close", width=120, height=38,
            fg_color=INPUT, border_color=BORDER, border_width=1,
            hover_color=CARD2, text_color=TEXT_DIM, corner_radius=8,
            command=self.destroy,
        ).pack(anchor="e")
