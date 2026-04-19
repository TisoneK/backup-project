#!/usr/bin/env python3
"""
install.py — Cross-platform installer for backup_project.

Windows : copies script to %USERPROFILE%\Scripts\ and adds it to PATH.
macOS   : copies script to ~/.local/bin/ (or /usr/local/bin/).
Linux   : copies script to ~/.local/bin/.

Usage:
    python install.py           install (default)
    python install.py uninstall remove installed files
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

SCRIPT_NAME = "backup_project"
SCRIPT_FILE = "backup_project.py"

# ---------------------------------------------------------------------------
# Colour helpers (duplicated here so the installer is self-contained)
# ---------------------------------------------------------------------------

_ANSI = sys.stdout.isatty()


def _c(code: str, t: str) -> str:
    return f"\033[{code}m{t}\033[0m" if _ANSI else t


def green(t: str) -> str:  return _c("32", t)
def yellow(t: str) -> str: return _c("33", t)
def red(t: str) -> str:    return _c("31", t)
def bold(t: str) -> str:   return _c("1",  t)
def dim(t: str) -> str:    return _c("2",  t)


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def _bin_dir() -> Path:
    """Return the best user-writable bin directory for this platform."""
    if os.name == "nt":
        return Path(os.environ.get("USERPROFILE", Path.home())) / "Scripts"
    # Unix-like
    local_bin = Path.home() / ".local" / "bin"
    local_bin.mkdir(parents=True, exist_ok=True)
    return local_bin


def _in_path(directory: Path) -> bool:
    path_env = os.environ.get("PATH", "")
    return str(directory) in path_env.split(os.pathsep)


def _add_to_path_windows(directory: Path) -> None:
    """Append *directory* to the current user's PATH (Windows registry)."""
    import winreg  # type: ignore[import]
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Environment",
        0,
        winreg.KEY_READ | winreg.KEY_WRITE,
    )
    try:
        current, _ = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        current = ""
    if str(directory) not in current.split(";"):
        new_val = f"{current};{directory}" if current else str(directory)
        winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new_val)
        print(yellow("  PATH updated (restart your terminal to pick it up)."))


# ---------------------------------------------------------------------------
# Install
# ---------------------------------------------------------------------------

def install() -> int:
    here = Path(__file__).resolve().parent
    source = here / SCRIPT_FILE
    if not source.is_file():
        print(red(f"Error: cannot find {SCRIPT_FILE} next to install.py"))
        return 1

    bin_dir = _bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)

    dest_script = bin_dir / SCRIPT_FILE
    shutil.copy2(source, dest_script)
    print(green(f"  Copied: {dest_script}"))

    if os.name == "nt":
        # Windows: create a .bat wrapper so the command works without 'python'
        bat = bin_dir / f"{SCRIPT_NAME}.bat"
        bat.write_text(
            f'@echo off\npython "%~dp0{SCRIPT_FILE}" %*\n',
            encoding="ascii",
        )
        print(green(f"  Wrapper: {bat}"))

        if not _in_path(bin_dir):
            try:
                _add_to_path_windows(bin_dir)
                print(green(f"  PATH:    {bin_dir} added"))
            except Exception as exc:  # noqa: BLE001
                print(yellow(f"  Could not update PATH automatically: {exc}"))
                print(yellow(f"  Add this to your PATH manually: {bin_dir}"))

    else:
        # Unix: create a thin shell wrapper (no 'python3 script.py' ceremony)
        wrapper = bin_dir / SCRIPT_NAME
        wrapper.write_text(
            f"#!/usr/bin/env python3\n"
            f'import runpy, sys\n'
            f'sys.argv[0] = "{dest_script}"\n'
            f'runpy.run_path("{dest_script}", run_name="__main__")\n',
            encoding="utf-8",
        )
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(green(f"  Wrapper: {wrapper}"))

        if not _in_path(bin_dir):
            shell = Path(os.environ.get("SHELL", "")).name
            rc_map = {"bash": ".bashrc", "zsh": ".zshrc", "fish": ".config/fish/config.fish"}
            rc = rc_map.get(shell, ".profile")
            print(yellow(f"\n  {bin_dir} is not on your PATH."))
            print(yellow(f"  Add this line to ~/{rc}:"))
            print(yellow(f'    export PATH="$HOME/.local/bin:$PATH"'))
            print(yellow("  Then run: source ~/" + rc))

    print()
    print(bold(green("Installation complete!")))
    print(f"  You can now run: {bold(SCRIPT_NAME)}")
    print(f"  Example:         {dim(SCRIPT_NAME + ' /path/to/project')}")
    return 0


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------

def uninstall() -> int:
    bin_dir = _bin_dir()
    removed = []

    for name in (SCRIPT_FILE, f"{SCRIPT_NAME}.bat", SCRIPT_NAME):
        candidate = bin_dir / name
        if candidate.is_file():
            candidate.unlink()
            removed.append(candidate)
            print(green(f"  Removed: {candidate}"))

    if not removed:
        print(yellow("Nothing to uninstall — no files found."))
    else:
        print(bold(green("\nUninstall complete.")))
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        return uninstall()
    return install()


if __name__ == "__main__":
    sys.exit(main())
