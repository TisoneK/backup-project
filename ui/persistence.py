"""
ui/persistence.py — Settings and history storage.

Handles all file I/O for app state. Nothing here touches the UI.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from backup_project import BackupConfig


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def _app_dir() -> Path:
    """Return (and create) the platform-appropriate app data directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path.home() / ".config"
    p = base / "backup_project"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _history_path() -> Path:
    return _app_dir() / "history.json"


def _settings_path() -> Path:
    return _app_dir() / "settings.json"


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

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
# Settings
# ---------------------------------------------------------------------------

_SETTINGS_DEFAULTS: dict = {
    "backup_dir": str(Path.home() / "Downloads" / "backup"),
    "compression": "deflated",
    "extra_dirs": "",
    "extra_extensions": "",
    "include_defaults": True,
}


def load_settings() -> dict:
    settings = dict(_SETTINGS_DEFAULTS)
    try:
        saved = json.loads(_settings_path().read_text())
        settings.update(saved)
    except Exception:
        pass
    return settings


def save_settings(s: dict) -> None:
    try:
        _settings_path().write_text(json.dumps(s, indent=2))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_size(size_bytes: int) -> str:
    """Human-readable file size string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024**2:.2f} MB"
    return f"{size_bytes / 1024**3:.2f} GB"


def build_config(settings: dict) -> BackupConfig:
    """Construct a BackupConfig from the current settings dict."""
    extra_dirs = [
        d.strip() for d in settings.get("extra_dirs", "").split(",")
        if d.strip()
    ]
    extra_exts = [
        e.strip() for e in settings.get("extra_extensions", "").split(",")
        if e.strip()
    ]
    return BackupConfig(
        extra_dirs=extra_dirs,
        extra_names=[],
        extra_extensions=extra_exts,
        extra_patterns=[],
        include_defaults=settings.get("include_defaults", True),
        backup_dir=settings.get("backup_dir") or None,
        compression=settings.get("compression", "deflated"),
    )
