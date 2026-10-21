"""Self-healing extraction of Android platform-tools (adb.exe) from the payload.

Files live in ``%LOCALAPPDATA%\\BULL-TOOL\\platform-tools`` (not the PyInstaller temp dir, because the adb
daemon outlives the app). Every start verifies size + CRC32 of each file against the embedded zip and
re-extracts anything missing or corrupt.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from bull_tool.core import paths
from bull_tool.core.events import Logger
from bull_tool.core.payload import (
    PLATFORM_TOOLS_ZIP,
    PayloadError,
    ResourceStore,
    extract_verified,
    file_matches,
    safe_join,
)

PREFIX = "platform-tools/"


@dataclass
class ToolsResult:
    adb: Path
    revision: str
    repaired: list[str] = field(default_factory=list)  # files re-extracted because they were corrupt
    extracted: list[str] = field(default_factory=list)  # files extracted because they were missing


def _read_revision(folder: Path) -> str:
    try:
        for line in (folder / "source.properties").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Pkg.Revision="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return "?"


def _extract_with_retry(zf, info, dest: Path, release_lock: Callable[[], None] | None) -> None:
    """Extract one file; when it is locked (adb.exe still running) stop the server and retry."""
    for attempt in range(4):
        try:
            extract_verified(zf, info, dest)
            return
        except PermissionError:
            if attempt == 3:
                raise
            if release_lock is not None:
                release_lock()
            time.sleep(0.3)


def ensure_platform_tools(
    store: ResourceStore,
    log: Logger,
    on_progress: Callable[[float, str], None] | None = None,
    release_lock: Callable[[], None] | None = None,
    target: Path | None = None,
) -> ToolsResult:
    target = target or paths.tools_dir()
    target.mkdir(parents=True, exist_ok=True)
    for stale in target.glob("*.tmp"):
        stale.unlink(missing_ok=True)

    extracted: list[str] = []
    repaired: list[str] = []
    with store.open_zip(PLATFORM_TOOLS_ZIP) as zf:
        members = [i for i in zf.infolist() if not i.is_dir() and i.filename.startswith(PREFIX)]
        if not any(i.filename == PREFIX + "adb.exe" for i in members):
            raise PayloadError("platform-tools zip has no adb.exe")
        for index, info in enumerate(members, start=1):
            dest = safe_join(target, info.filename, PREFIX)
            if not file_matches(dest, info):
                existed = dest.exists()
                _extract_with_retry(zf, info, dest, release_lock)
                (repaired if existed else extracted).append(info.filename[len(PREFIX) :])
            if on_progress is not None:
                on_progress(index / len(members), info.filename[len(PREFIX) :])

    if extracted:
        log.info(f"Đã giải nén platform-tools ({len(extracted)} file) → {target}")
    for name in repaired:
        log.warn(f"Tự sửa: {name} bị lỗi → đã giải nén lại từ bản gốc trong tool")
    return ToolsResult(target / "adb.exe", _read_revision(target), repaired, extracted)
