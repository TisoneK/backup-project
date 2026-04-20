"""
ui/components.py — Small, reusable CTk widgets shared across views.

Each class owns its layout and exposes a minimal public API.
Nothing here knows about app state or business logic.
"""

from __future__ import annotations

import customtkinter as ctk

from ui.tokens import (
    ACCENT_DIM, BORDER, FONT_LABEL, FONT_SMALL,
    INPUT, TEXT, TEXT_DIM, TEXT_MUTED,
)


class SectionLabel(ctk.CTkLabel):
    """
    Muted all-caps micro-label used as a section heading inside cards.
    e.g.  PROJECT DIRECTORY  |  FILES FOUND  |  OUTPUT
    """

    def __init__(self, master, text: str, **kw):
        super().__init__(
            master,
            text=text,
            font=FONT_LABEL,
            text_color=TEXT_MUTED,
            **kw,
        )


class StatCard(ctk.CTkFrame):
    """
    Metric card: micro-label + large value + optional sub-label.

    Public API:
        card.set(value)               — update value text
        card.set(value, color=X)      — update value + colour
        card.set_sub(text)            — update sub-label
        card.set_sub(text, color=X)   — update sub-label + colour
    """

    def __init__(
        self,
        master,
        label: str,
        value: str = "—",
        value_color: str = TEXT,
        sub: str = "",
        **kw,
    ):
        super().__init__(
            master,
            fg_color=INPUT,
            corner_radius=8,
            border_color=BORDER,
            border_width=1,
            **kw,
        )

        ctk.CTkLabel(
            self, text=label, font=FONT_LABEL, text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(10, 0))

        self._val = ctk.CTkLabel(
            self, text=value,
            font=("Segoe UI", 20, "bold"),
            text_color=value_color,
        )
        self._val.pack(anchor="w", padx=14, pady=(2, 0))

        self._sub = ctk.CTkLabel(
            self, text=sub, font=FONT_SMALL, text_color=TEXT_DIM,
        )
        self._sub.pack(anchor="w", padx=14, pady=(1, 10))

    def set(self, value: str, color: str | None = None) -> None:
        self._val.configure(text=value)
        if color:
            self._val.configure(text_color=color)

    def set_sub(self, text: str, color: str | None = None) -> None:
        self._sub.configure(text=text)
        if color:
            self._sub.configure(text_color=color)


class Logo(ctk.CTkFrame):
    """Square icon badge shown at the top of the sidebar."""

    def __init__(self, master, icon: str = "📦", **kw):
        super().__init__(
            master,
            fg_color=ACCENT_DIM,
            corner_radius=10,
            width=40,
            height=40,
            **kw,
        )
        self.pack_propagate(False)
        ctk.CTkLabel(self, text=icon, font=("Segoe UI", 18)).pack(
            expand=True, pady=6,
        )
