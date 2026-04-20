"""
ui/sidebar.py — Sidebar navigation panel.

Owns its layout and calls back to the app when the user switches pages.
Does not know about frame content or app state.
"""

from __future__ import annotations

import customtkinter as ctk

from ui.components import Logo
from ui.tokens import ACCENT, ACCENT_DIM, INPUT, TEXT_MUTED, CARD


class Sidebar(ctk.CTkFrame):
    """
    Vertical icon-and-label navigation strip.

    Parameters
    ----------
    on_navigate:
        Called with the page id string ("home", "history", "settings")
        whenever the user clicks a nav item.
    """

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
                self,
                text=f"{icon}\n{label}",
                font=("Segoe UI", 9),
                width=58,
                height=58,
                corner_radius=10,
                fg_color="transparent",
                hover_color=INPUT,
                text_color=TEXT_MUTED,
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
