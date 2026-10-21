"""Realtime device presence via ``host:track-devices-l`` (no polling), with automatic reconnect."""

from __future__ import annotations

import threading

from bull_tool.core.adb.client import AdbClient, DeviceTracker
from bull_tool.core.adb.protocol import AdbError
from bull_tool.core.adb.server import AdbServer
from bull_tool.core.events import DevicesEvent, EventBus, StatusEvent


class DeviceMonitor:
    def __init__(
        self, client: AdbClient, server: AdbServer, bus: EventBus, reconnect_delay: float = 1.5
    ) -> None:
        self.client = client
        self.server = server
        self.bus = bus
        self.reconnect_delay = reconnect_delay
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()
        self._tracker: DeviceTracker | None = None
        self._last: tuple | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="device-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
        self._close_tracker()
        if self._thread:
            self._thread.join(timeout=3)

    def pause(self) -> None:
        """Release the track connection and stop reconnecting (used while adb is being restarted)."""
        with self._lock:
            self._paused.set()
        self._close_tracker()

    def resume(self) -> None:
        self._paused.clear()

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def _close_tracker(self) -> None:
        with self._lock:
            tracker, self._tracker = self._tracker, None
        if tracker is not None:
            tracker.close()

    def _publish(self, devices: tuple) -> None:
        if devices != self._last:
            self._last = devices
            self.bus.emit(DevicesEvent(devices))

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._paused.is_set():
                self._stop.wait(0.2)
                continue
            detail = ""
            try:
                self.server.ensure_running()
                tracker = self.client.track_devices()
                with self._lock:
                    # stop()/pause() may have run while the connection was being opened: honour them now,
                    # otherwise this thread would block on a tracker nobody can close
                    if self._stop.is_set() or self._paused.is_set():
                        tracker.close()
                        continue
                    self._tracker = tracker
                self.bus.emit(StatusEvent("adb", "up"))
                for devices in tracker:
                    self._publish(tuple(devices))
                    if self._stop.is_set() or self._paused.is_set():
                        break
            except AdbError as exc:
                detail = str(exc)
            except Exception as exc:  # noqa: BLE001 - the monitor must never die; report and retry
                detail = f"{type(exc).__name__}: {exc}"
            finally:
                self._close_tracker()
            if self._stop.is_set():
                break
            if not self._paused.is_set():
                self.bus.emit(StatusEvent("adb", "down", detail))
            self._publish(())
            self._stop.wait(self.reconnect_delay)
