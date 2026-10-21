"""Bridges worker threads to the UI: drains the EventBus on the page event loop every 50 ms.

Only the newest ``ProgressEvent`` per job is applied in a tick (natural 20 fps throttle), log lines are
handed over in one batch, and only controls marked dirty are updated. A failing handler is reported and
skipped; the loop itself never exits until ``stop()``.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import traceback
from collections.abc import Callable

import flet as ft

from bull_tool.core.events import EventBus, Level, LogEvent, ProgressEvent

LOGS = "logs"  # handler key receiving list[LogEvent]
MAX_REPORTED_ERRORS = 5


def is_attached(control: ft.Control) -> bool:
    """Whether ``control`` is currently on the page.

    Flet 1.0's ``control.page`` raises RuntimeError for a control that was never added, and a control removed from
    a parent that still exists keeps resolving its old page, so the session's index of mounted controls decides.
    """
    try:
        page = control.page
    except RuntimeError:
        return False
    if page is None:
        return False
    index = getattr(getattr(page, "session", None), "index", None)
    return index is None or index.get(getattr(control, "_i", None)) is control


class UiPump:
    def __init__(self, page: ft.Page, bus: EventBus, interval: float = 0.05) -> None:
        self.page = page
        self.bus = bus
        self.interval = interval
        self._handlers: dict[object, list[Callable]] = {}
        self._after_flush: list[Callable] = []
        self._dirty: dict[int, ft.Control] = {}
        self._running = False
        self._errors = 0

    def on(self, key: object, handler: Callable) -> None:
        """Register a handler for an event class (or ``LOGS`` for batched log lines)."""
        self._handlers.setdefault(key, []).append(handler)

    def after_flush(self, callback: Callable) -> None:
        """Run ``callback()`` (sync or async) after each flush that updated something."""
        self._after_flush.append(callback)

    def mark_dirty(self, *controls: ft.Control) -> None:
        for control in controls:
            if control is not None:
                self._dirty[id(control)] = control

    def start(self) -> None:
        if not self._running:
            self._running = True
            self.page.run_task(self._loop)

    def stop(self) -> None:
        self._running = False

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.interval)
            try:
                await self.tick()
            except Exception:  # noqa: BLE001 - the pump must survive anything
                self._report(sys.exc_info()[1])

    async def tick(self) -> None:
        events = self.bus.drain(500)
        if events:
            latest_progress = {}
            for event in events:
                if isinstance(event, ProgressEvent):
                    latest_progress[event.job] = event
            logs = [e for e in events if isinstance(e, LogEvent)]
            if logs:
                await self._dispatch(LOGS, logs)
            for event in events:
                if isinstance(event, LogEvent):
                    continue
                if isinstance(event, ProgressEvent) and latest_progress.get(event.job) is not event:
                    continue
                await self._dispatch(type(event), event)
        await self.flush()

    async def flush(self) -> None:
        dirty, self._dirty = list(self._dirty.values()), {}
        if not dirty:
            return
        for control in dirty:
            try:
                if is_attached(control):  # outside the page tree: skipped silently; update failures are reported
                    control.update()
            except Exception as exc:  # noqa: BLE001
                self._report(exc)
        for callback in self._after_flush:
            try:
                result = callback()
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                self._report(exc)

    async def _dispatch(self, key: object, payload: object) -> None:
        for handler in self._handlers.get(key, ()):
            try:
                result = handler(payload)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # noqa: BLE001 - one broken handler must not stop the others
                self._report(exc)

    def _report(self, exc: BaseException | None) -> None:
        self._errors += 1
        traceback.print_exception(exc, file=sys.stderr)
        if self._errors <= MAX_REPORTED_ERRORS:
            self.bus.emit(LogEvent(Level.ERROR, f"Lỗi giao diện (đã bỏ qua): {exc!r}"))
