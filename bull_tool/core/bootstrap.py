"""Startup sequence (worker thread): payload → platform-tools self-heal → adb server → USB driver →
device tracking. Every step reports logs and progress; ``AppServices.shutdown`` undoes what was started.
Once the app begins to exit (``AppServices.begin_close``) the sequence stops before its next step."""

from __future__ import annotations

import threading
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field

from bull_tool import app_info
from bull_tool.core.adb.client import AdbClient
from bull_tool.core.adb.protocol import AdbError
from bull_tool.core.adb.server import AdbServer
from bull_tool.core.device_monitor import DeviceMonitor
from bull_tool.core.driver_installer import DriverResult, install_driver, is_installed
from bull_tool.core.events import EventBus, JobState, Logger, Progress, StatusEvent
from bull_tool.core.job_runner import JobRunner
from bull_tool.core.payload import PayloadError, ResourceStore
from bull_tool.core.platform_tools import ensure_platform_tools
from bull_tool.core.session_log import SessionLog
from bull_tool.core.settings import Settings, save_settings

BOOT_JOB = "bootstrap"


@dataclass
class AppServices:
    bus: EventBus
    settings: Settings = field(default_factory=Settings)
    client: AdbClient = field(default_factory=AdbClient)
    store: ResourceStore | None = None
    server: AdbServer | None = None
    monitor: DeviceMonitor | None = None
    runner: JobRunner | None = None
    session_log: SessionLog | None = None
    tools_revision: str = ""
    driver_ok: bool | None = None
    ready: bool = False
    closing: threading.Event = field(default_factory=threading.Event)
    _shutdown_lock: threading.Lock = field(default_factory=threading.Lock)
    _shut_down: bool = False

    def begin_close(self) -> None:
        """The app begins to exit: from now on nothing starts adb, a driver prompt or device tracking.

        Idempotent and lock-free, so the UI loop may call it while workers still hold their locks."""
        self.closing.set()
        server = self.server
        if server is not None:
            server.close()

    def shutdown(self) -> None:
        """Idempotent: stop tracking, stop the adb server only if this app started it, close files.

        The session log closes last: a job that is still stopping logs its final lines while the server
        and the store go away under it."""
        self.begin_close()
        with self._shutdown_lock:
            if self._shut_down:
                return
            self._shut_down = True
        for action in (
            lambda: self.monitor and self.monitor.stop(),
            lambda: self.server and self.server.shutdown(),
            lambda: self.store and self.store.close(),
            lambda: self.session_log and self.session_log.close(),
        ):
            try:
                action()
            except Exception:  # noqa: BLE001 - shutdown must always run every step
                pass


def run_bootstrap(
    services: AppServices,
    open_store: Callable[[], ResourceStore] = ResourceStore.open_default,
    driver_check: Callable[[], bool] = is_installed,
    driver_install: Callable[..., DriverResult] = install_driver,
) -> bool:
    bus = services.bus
    log = Logger(bus, BOOT_JOB)
    progress = Progress(bus, BOOT_JOB, "Khởi động")
    progress.state(JobState.RUNNING)
    log.step(f"{app_info.APP_NAME} v{app_info.VERSION} — khởi động")
    try:
        return _run_steps(services, log, progress, open_store, driver_check, driver_install)
    except _Closing:
        return False  # the window is already going away: no fatal dialog, and nothing more gets started
    except Exception as exc:  # noqa: BLE001 - the UI must always learn how startup ended
        return _fatal(bus, log, progress, f"Lỗi không mong đợi khi khởi động: {type(exc).__name__}: {exc}")


def _run_steps(services, log, progress, open_store, driver_check, driver_install) -> bool:
    bus = services.bus
    progress.update(0.02, "Mở dữ liệu của tool…", force=True)
    try:
        services.store = open_store()
    except (PayloadError, OSError, zipfile.BadZipFile) as exc:
        return _fatal(bus, log, progress, f"Không đọc được dữ liệu bên trong tool ({exc}). Hãy tải lại file tool.")

    services.server = AdbServer(services.client)
    _stop_if_closing(services)  # a close that began before the server existed must still close it
    try:
        tools = ensure_platform_tools(
            services.store, log,
            on_progress=lambda frac, name: progress.update(0.05 + 0.4 * frac, f"Kiểm tra platform-tools: {name}"),
            release_lock=services.server.kill,
        )
    except (PayloadError, OSError, zipfile.BadZipFile) as exc:
        return _fatal(bus, log, progress, f"Không chuẩn bị được ADB ({exc}). Hãy tải lại file tool.")
    services.server.adb_exe = tools.adb
    services.tools_revision = tools.revision
    bus.emit(StatusEvent("tools", tools.revision))
    log.ok(f"Platform-tools {tools.revision} đã sẵn sàng")

    progress.update(0.5, "Khởi động ADB server…", force=True)
    try:
        version = services.server.ensure_running()
        origin = "tool tự khởi động" if services.server.owned else "dùng server đang chạy sẵn"
        log.ok(f"ADB server đang chạy (giao thức {version}, {origin})")
        bus.emit(StatusEvent("adb", "up"))
    except AdbError as exc:
        log.error(f"Chưa khởi động được ADB server: {exc} — tool sẽ tự thử lại")
        bus.emit(StatusEvent("adb", "down", str(exc)))

    progress.update(0.65, "Kiểm tra driver USB…", force=True)
    _stop_if_closing(services)  # never raise a UAC prompt after the window is gone
    services.driver_ok = driver_check()
    if services.driver_ok:
        log.ok("Driver USB Xiaomi: đã cài trên máy này")
    elif services.settings.driver_auto_attempted:
        log.warn("Driver USB Xiaomi chưa cài — bấm “Driver USB Xiaomi” trong Công cụ khi cần")
    else:
        log.info("Lần đầu chạy trên máy này: cài driver USB Xiaomi")
        try:
            result = driver_install(services.store, log, progress)
        except Exception as exc:  # noqa: BLE001 - a driver problem is a warning, never fatal
            log.warn(f"Không cài được driver USB Xiaomi: {exc}")
            result = DriverResult(False, None, str(exc))
        services.driver_ok = result.ok
        if not result.ok and not services.closing.is_set():
            # refused UAC or any other failure: never prompt again on every launch; the button stays.
            # A failure caused by closing the app mid-install does not count: the next launch tries again.
            services.settings.driver_auto_attempted = True
            save_settings(services.settings)
    bus.emit(StatusEvent("driver", "ok" if services.driver_ok else "missing"))

    progress.update(0.97, "Theo dõi thiết bị…", force=True)
    _stop_if_closing(services)  # a monitor started now might never be stopped
    services.runner = JobRunner(services.client, services.store, bus)
    services.monitor = DeviceMonitor(services.client, services.server, bus)
    services.monitor.start()
    services.ready = True
    progress.update(1.0, "Sẵn sàng", force=True)
    progress.state(JobState.SUCCESS)
    bus.emit(StatusEvent("bootstrap", "ready"))
    log.ok("Sẵn sàng — cắm điện thoại đã bật gỡ lỗi USB để bắt đầu")
    return True


class _Closing(Exception):
    """The app began to exit while bootstrap was still running."""


def _stop_if_closing(services: AppServices) -> None:
    if services.closing.is_set():
        services.begin_close()  # also closes a server created after the close began
        raise _Closing


def _fatal(bus: EventBus, log: Logger, progress: Progress, message: str) -> bool:
    log.error(message)
    bus.emit(StatusEvent("bootstrap", "fatal", message))
    progress.state(JobState.FAILED, message=message)
    return False
