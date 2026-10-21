"""User preferences persisted in ``settings.json`` (atomic writes; a corrupt file falls back to defaults)."""

from __future__ import annotations

import contextlib
import json
import os
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from bull_tool.core import paths

THEMES = ("dark", "light")
_SAVE_LOCK = threading.Lock()  # saves run on worker threads (theme toggles, driver flag) and share one tmp file


@dataclass
class Settings:
    theme: str = "dark"
    # The first-run automatic driver install was tried and did not succeed (UAC refused or pnputil
    # failed): do not prompt again on every launch; the manual "Driver USB Xiaomi" button remains.
    driver_auto_attempted: bool = False


def load_settings(path: Path | None = None) -> Settings:
    path = path or paths.settings_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    theme = data.get("theme")
    return Settings(
        theme=theme if theme in THEMES else "dark",
        driver_auto_attempted=bool(data.get("driver_auto_attempted", False)),
    )


def save_settings(settings: Settings, path: Path | None = None) -> bool:
    path = path or paths.settings_file()
    tmp = path.with_name(path.name + ".tmp")
    with _SAVE_LOCK:  # the snapshot is taken under the lock, so the last save writes the newest state
        try:
            tmp.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, path)
            return True
        except OSError:
            with contextlib.suppress(OSError):  # e.g. a virus scanner still holds the tmp file
                tmp.unlink(missing_ok=True)
            return False
