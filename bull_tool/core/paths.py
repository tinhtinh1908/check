"""Filesystem locations for source-checkout (dev) and PyInstaller (frozen) runs.

All writable state lives under ``%LOCALAPPDATA%\\BULL-TOOL`` (override with ``BULL_TOOL_DATA_DIR``,
used by tests and the self-test so they never touch the real user data).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "BULL-TOOL"
DATA_DIR_ENV = "BULL_TOOL_DATA_DIR"


def is_frozen() -> bool:
    """True when running from the PyInstaller-built executable."""
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    """Source checkout root (the folder holding ``main.py`` and the input resources)."""
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path:
    """Root of bundled read-only files: ``sys._MEIPASS`` when frozen, else the repo root."""
    if is_frozen():
        return Path(sys._MEIPASS)  # set by the PyInstaller bootloader
    return repo_root()


def assets_dir() -> Path:
    """Flet assets folder (icons, logos, fonts)."""
    return bundle_dir() / "bull_tool" / "assets"


def app_data_dir() -> Path:
    """Per-user writable directory, created on demand."""
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        path = Path(override)
    else:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def _subdir(name: str) -> Path:
    path = app_data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def tools_dir() -> Path:
    """Extracted Android platform-tools (adb.exe lives here, outside the PyInstaller temp dir)."""
    return _subdir("platform-tools")


def driver_dir() -> Path:
    """Extracted Xiaomi USB driver package used by pnputil."""
    return _subdir("driver")


def logs_dir() -> Path:
    """Session log files."""
    return _subdir("logs")


def settings_file() -> Path:
    """User preferences (theme, driver prompt state)."""
    return app_data_dir() / "settings.json"


def dev_payload_path() -> Path:
    """Payload zip used when running from source (built by ``scripts/build_payload.py``)."""
    return repo_root() / ".build" / "payload.zip"
