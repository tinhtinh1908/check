"""Lifecycle of the adb server process (the daemon on port 5037).

The app reuses any adb server that already answers (another tool's, any version: the host protocol
is compatible). It starts one with its own ``adb.exe`` only when none answers, and only kills the
server on shutdown when it started it (``owned``). All lifecycle calls share one lock so the device
monitor and the connection fixer never start the server twice at once. Once the app begins to exit
(``close``) the server is never started again: nobody would be left to stop it.
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

from bull_tool.core.adb.client import AdbClient
from bull_tool.core.adb.protocol import AdbConnectionError, AdbError

CREATE_NO_WINDOW = 0x08000000


class AdbServer:
    def __init__(self, client: AdbClient, adb_exe: Path | None = None) -> None:
        self.client = client
        self.adb_exe = adb_exe
        self.owned = False
        self._lock = threading.RLock()
        self._closed = threading.Event()

    @property
    def closed(self) -> bool:
        return self._closed.is_set()

    def close(self) -> None:
        """Refuse every later start. Lock-free: the UI loop calls it while a worker may hold the lock."""
        self._closed.set()

    def is_running(self) -> bool:
        try:
            self.client.server_version()
            return True
        except AdbError:
            return False

    def ensure_running(self, timeout: float = 15.0) -> int:
        """Return the server version, starting the server with our adb.exe when nothing answers."""
        with self._lock:
            if self._closed.is_set():
                raise AdbConnectionError("the app is shutting down")
            try:
                return self.client.server_version()
            except AdbError:
                pass
            if self.adb_exe is None or not self.adb_exe.exists():
                raise AdbConnectionError("adb.exe is not available")
            try:
                # stdio must not be pipes: the forked daemon inherits them and communicate() would hang.
                subprocess.run(
                    [str(self.adb_exe), "start-server"],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    cwd=str(self.adb_exe.parent), creationflags=CREATE_NO_WINDOW, timeout=timeout,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise AdbConnectionError(f"cannot start adb server: {exc}") from exc
            self.owned = True  # a daemon that answers only after the polling below is still ours to stop
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    return self.client.server_version()
                except AdbError:
                    time.sleep(0.25)
            raise AdbConnectionError("adb server did not start")

    def kill(self, wait: float = 5.0) -> None:
        """Stop whichever adb server answers on the port (connection fixer, platform-tools; also after close)."""
        with self._lock:
            try:
                self.client.kill_server()
            except AdbError:
                return
            deadline = time.monotonic() + wait
            while time.monotonic() < deadline and self.is_running():
                time.sleep(0.2)
            self.owned = False

    def restart(self) -> int:
        with self._lock:
            self.kill()
            return self.ensure_running()

    def shutdown(self) -> None:
        """App exit: refuse later starts, then stop the server only if this app started it.

        A start already in progress holds the lock, so it finishes first and its server is stopped here."""
        self.close()
        with self._lock:
            if self.owned:
                self.kill(wait=2.0)
