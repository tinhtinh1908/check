"""Session log file: every console line is appended to ``logs/YYYYMMDD-HHMMSS.log`` (newest 20 kept).

Writing never raises; the first failure is reported once through the bus.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from bull_tool.core import paths
from bull_tool.core.events import Event, EventBus, LogEvent, StatusEvent

KEEP_FILES = 20


class SessionLog:
    def __init__(self, bus: EventBus | None = None, folder: Path | None = None, keep: int = KEEP_FILES) -> None:
        self.bus = bus
        self._lock = threading.Lock()
        self._fp = None
        self.path: Path | None = None
        try:
            folder = folder or paths.logs_dir()
            self.path = folder / time.strftime("%Y%m%d-%H%M%S.log")
            self._fp = open(self.path, "a", encoding="utf-8", buffering=1)
            self._prune(folder, keep)
        except OSError as exc:
            self._report(exc)

    def write(self, event: Event) -> None:
        """Bus listener: append LogEvents, ignore everything else."""
        if not isinstance(event, LogEvent) or self._fp is None:
            return
        stamp = time.strftime("%H:%M:%S", time.localtime(event.ts))
        line = f"{stamp} [{event.level.value.upper():5}] {event.text}\n"
        with self._lock:
            try:
                self._fp.write(line)
            except (OSError, ValueError) as exc:
                self._close_quietly()
                self._report(exc)

    def close(self) -> None:
        with self._lock:
            self._close_quietly()

    def _close_quietly(self) -> None:
        if self._fp is not None:
            try:
                self._fp.close()
            except OSError:
                pass
            self._fp = None

    def _report(self, exc: Exception) -> None:
        if self.bus is not None:
            self.bus.emit(StatusEvent("log", "error", str(exc)))

    @staticmethod
    def _prune(folder: Path, keep: int) -> None:
        for old in sorted(folder.glob("*.log"))[:-keep]:
            try:
                old.unlink()
            except OSError:
                pass
