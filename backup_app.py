"""
backup_app.py — GUI entry point for Backup Project.

Launches a modern desktop UI built with CustomTkinter.
For CLI users, pass -c as the first argument to bypass the GUI entirely:

    backup_project.exe -c [DIR] [--dry-run] [--output PATH] ...

All other CLI flags are identical to backup_project.py.
"""

from __future__ import annotations

import sys

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

from PIL import Image, ImageDraw, ImageTk
import customtkinter as ctk

from ui.persistence import load_settings
from ui.sidebar import Sidebar
from ui.views.home import HomeFrame
from ui.views.history import HistoryFrame
from ui.views.settings import SettingsFrame
from ui.tokens import BG, CARD


# ---------------------------------------------------------------------------
# Window icon
# ---------------------------------------------------------------------------

def _create_logo_image(size: int = 64) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill=(88, 166, 255, 255))
    box_size = int(size * 0.5)
    bx = (size - box_size) // 2
    by = (size - box_size) // 2
    draw.rectangle([bx, by, bx + box_size, by + box_size],
                   outline=(255, 255, 255, 255), width=2)
    lid = int(box_size * 0.3)
    draw.line([bx, by + lid, bx + box_size, by + lid],
              fill=(255, 255, 255, 255), width=2)
    draw.line([bx + box_size // 2, by, bx + box_size // 2, by + box_size],
              fill=(255, 255, 255, 255), width=2)
    return img


# ---------------------------------------------------------------------------
# Application root
# ---------------------------------------------------------------------------

class BackupApp(ctk.CTk):
    """
    Root window. Owns the settings dict and the frame registry.

    Responsibilities:
    - Bootstrap CTk theme and geometry
    - Instantiate and grid the sidebar + content frames
    - Route navigation requests from the sidebar
    - Expose refresh_history() so HomeFrame can trigger a history reload
      after a successful backup without importing HistoryFrame directly
    """

    def __init__(self):
        super().__init__()
        self.settings = load_settings()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("Backup Project")
        self.geometry("1020x720")
        self.minsize(820, 580)
        self.configure(fg_color=CARD)

        try:
            self.iconphoto(True, ImageTk.PhotoImage(_create_logo_image(64)))
        except Exception:
            pass

        self._frames: dict[str, ctk.CTkFrame] = {}
        self._build()
        self._center()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        Sidebar(self, on_navigate=self._navigate).grid(
            row=0, column=0, sticky="nsew",
        )

        content = ctk.CTkFrame(self, corner_radius=0, fg_color=BG)
        content.grid(row=0, column=1, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)

        self._frames["home"]     = HomeFrame(content, self)
        self._frames["history"]  = HistoryFrame(content)
        self._frames["settings"] = SettingsFrame(content, self)

        self._navigate("home")

    def _navigate(self, page_id: str) -> None:
        for fid, frame in self._frames.items():
            if fid == page_id:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()

    def refresh_history(self) -> None:
        self._frames["history"].refresh()

    def _center(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")


def main() -> None:
    BackupApp().mainloop()


if __name__ == "__main__":
    main()
