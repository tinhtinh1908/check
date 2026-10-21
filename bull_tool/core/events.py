"""Thread-safe event bus between workers (ADB jobs, device monitor, bootstrap) and the UI pump.

Workers only ``emit``; the UI drains the queue on the page event loop, so controls are never touched
from worker threads. Synchronous listeners (e.g. the session log file) run in the emitting thread.
"""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Level(StrEnum):
    INFO = "info"
    OK = "ok"
    SKIP = "skip"
    WARN = "warn"
    ERROR = "error"
    CMD = "cmd"
    STEP = "step"


class JobState(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class LogEvent:
    level: Level
    text: str
    job: str = ""
    ts: float = field(default_factory=time.time)


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    job: str
    title: str
    fraction: float | None  # None = indeterminate
    label: str = ""
    step: int = 0
    steps: int = 0
    sub_fraction: float | None = None  # progress of the file being transferred
    rate_bps: float = 0.0
    eta_s: float | None = None
    elapsed_s: float = 0.0


@dataclass(frozen=True, slots=True)
class JobStateEvent:
    job: str
    title: str
    state: JobState
    summary: Any = None
    message: str = ""


@dataclass(frozen=True, slots=True)
class DevicesEvent:
    devices: tuple  # tuple[DeviceEntry, ...]


@dataclass(frozen=True, slots=True)
class DeviceInfoEvent:
    serial: str
    info: Any  # DeviceInfo


@dataclass(frozen=True, slots=True)
class StatusEvent:
    key: str  # "adb" | "driver" | "bootstrap" | "tools" | "log"
    value: str
    detail: str = ""


Event = LogEvent | ProgressEvent | JobStateEvent | DevicesEvent | DeviceInfoEvent | StatusEvent


class EventBus:
    def __init__(self) -> None:
        self._queue: queue.SimpleQueue[Event] = queue.SimpleQueue()
        self._listeners: list[Callable[[Event], None]] = []
        self._lock = threading.Lock()

    def add_listener(self, listener: Callable[[Event], None]) -> None:
        with self._lock:
            self._listeners.append(listener)

    def emit(self, event: Event) -> None:
        self._queue.put(event)
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:  # noqa: BLE001 - a broken listener must never break the emitter
                pass

    def drain(self, max_items: int = 500) -> list[Event]:
        items: list[Event] = []
        while len(items) < max_items:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return items


class Logger:
    """Shorthand for emitting console lines tagged with a job id."""

    def __init__(self, bus: EventBus, job: str = "") -> None:
        self.bus = bus
        self.job = job

    def _emit(self, level: Level, text: str) -> None:
        self.bus.emit(LogEvent(level, text, self.job))

    def info(self, text: str) -> None:
        self._emit(Level.INFO, text)

    def ok(self, text: str) -> None:
        self._emit(Level.OK, text)

    def skip(self, text: str) -> None:
        self._emit(Level.SKIP, text)

    def warn(self, text: str) -> None:
        self._emit(Level.WARN, text)

    def error(self, text: str) -> None:
        self._emit(Level.ERROR, text)

    def cmd(self, text: str) -> None:
        self._emit(Level.CMD, text)

    def step(self, text: str) -> None:
        self._emit(Level.STEP, text)


class Progress:
    """Emits ``ProgressEvent``s for one job, throttled to ``min_interval`` unless forced."""

    def __init__(self, bus: EventBus, job: str, title: str, min_interval: float = 0.05) -> None:
        self.bus = bus
        self.job = job
        self.title = title
        self.min_interval = min_interval
        self.started = time.monotonic()
        self._last = 0.0

    def update(
        self,
        fraction: float | None,
        label: str = "",
        step: int = 0,
        steps: int = 0,
        sub_fraction: float | None = None,
        rate_bps: float = 0.0,
        eta_s: float | None = None,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        if not force and now - self._last < self.min_interval:
            return
        self._last = now
        if fraction is not None:
            fraction = min(1.0, max(0.0, fraction))
        self.bus.emit(
            ProgressEvent(
                self.job, self.title, fraction, label, step, steps, sub_fraction, rate_bps, eta_s,
                now - self.started,
            )
        )

    def state(self, state: JobState, summary: Any = None, message: str = "") -> None:
        self.bus.emit(JobStateEvent(self.job, self.title, state, summary, message))
