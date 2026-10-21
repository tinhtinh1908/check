"""Menu item 7 of ``@ANDROID.bat``: fix "the PC does not see the phone".

Same steps as the batch file (close apps that grab ADB/USB, ``adb kill-server``, kill every leftover
``adb.exe``) plus a final step the GUI needs: restart this tool's adb server and resume device tracking.
A ``cancel`` event (e.g. the app is closing) stops it before the next app kill or step.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable

from bull_tool.core.adb.protocol import AdbError, Cancelled
from bull_tool.core.adb.server import AdbServer
from bull_tool.core.events import EventBus, JobState, Logger, Progress
from bull_tool.core.win32 import list_processes, taskkill

FIX_JOB = "fix"
KILL_LIST = (
    "HiSuite.exe", "HiSuiteService.exe", "HiSuiteService64.exe", "HiSuiteDownloader.exe", "hdb.exe",
    "HonorSuite.exe", "HonorSuiteService.exe", "HonorSuiteService64.exe", "PhoneExperienceHost.exe",
    "YourPhone.exe", "CrossDeviceService.exe", "scrcpy.exe", "sndcpy.exe", "Vysor.exe", "AirDroid.exe",
    "AirDroidCast.exe", "Mobizen.exe", "ApowerMirror.exe", "LetsView.exe", "MirrorTo.exe", "360MobileMgr.exe",
    "360sd.exe", "360se.exe", "wandoujia.exe", "pea.exe", "Kies.exe", "KiesTrayAgent.exe", "SmartSwitchPC.exe",
    "SideSync.exe",
)


def find_running(processes: Iterable[str] | None = None) -> list[str]:
    """Names from ``KILL_LIST`` that are currently running (case-insensitive)."""
    running = {name.lower() for name in (processes if processes is not None else list_processes())}
    return [name for name in KILL_LIST if name.lower() in running]


def fix_connection(
    server: AdbServer,
    bus: EventBus,
    to_kill: Iterable[str],
    monitor=None,
    kill: Callable[[str], bool] = taskkill,
    cancel: threading.Event | None = None,
) -> bool:
    log = Logger(bus, FIX_JOB)
    progress = Progress(bus, FIX_JOB, "Sửa lỗi kết nối")
    progress.state(JobState.RUNNING)
    log.step("SỬA LỖI MÁY TÍNH KHÔNG NHẬN ĐIỆN THOẠI")
    try:
        return _fix(server, to_kill, monitor, kill, cancel, log, progress)
    except Cancelled:
        if monitor is not None:
            monitor.resume()
        log.warn("Đã dừng sửa kết nối.")
        progress.state(JobState.CANCELLED, message="Đã dừng")
        return False
    except Exception as exc:  # noqa: BLE001 - always end with a state the UI can show
        if monitor is not None:
            monitor.resume()
        log.error(f"Lỗi khi sửa kết nối: {type(exc).__name__}: {exc}")
        progress.state(JobState.FAILED, message=str(exc))
        return False


def _safe_kill(kill: Callable[[str], bool], name: str) -> bool:
    try:
        return kill(name)
    except OSError:
        return False


def _check_cancel(cancel: threading.Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def _fix(server: AdbServer, to_kill: Iterable[str], monitor, kill, cancel, log: Logger, progress: Progress) -> bool:
    progress.update(0.0, "[1/4] Đóng các ứng dụng chiếm ADB/USB…", 1, 4, force=True)
    log.info("[1/4] Đóng các ứng dụng có thể chiếm ADB/USB…")
    killed_any = False
    for name in to_kill:
        _check_cancel(cancel)
        if _safe_kill(kill, name):
            killed_any = True
            log.ok(f"-> Đã tắt {name}")
    if not killed_any:
        log.info("-> Không thấy Xiaomi PC Suite / app truyền màn hình nào đang chạy.")

    _check_cancel(cancel)
    progress.update(0.25, "[2/4] Dừng ADB server…", 2, 4, force=True)
    log.info("[2/4] Sửa lỗi máy tính không nhận điện thoại…")
    if monitor is not None:
        monitor.pause()
    ok = True
    try:
        server.kill()
        log.ok("-> Hoàn tất")

        _check_cancel(cancel)
        progress.update(0.5, "[3/4] Tắt tiến trình adb.exe còn sót…", 3, 4, force=True)
        log.info("[3/4] Tắt tất cả tiến trình adb.exe còn sót lại…")
        if _safe_kill(kill, "adb.exe"):
            log.ok("-> Đã tắt các tiến trình adb.exe.")
        else:
            log.info("-> Không còn tiến trình adb.exe nào đang chạy.")

        _check_cancel(cancel)
        progress.update(0.75, "[4/4] Khởi động lại ADB…", 4, 4, force=True)
        log.info("[4/4] Khởi động lại ADB của tool…")
        try:
            server.ensure_running()
            log.ok("-> ADB đã sẵn sàng. Rút ra cắm lại cáp nếu điện thoại vẫn chưa hiện.")
        except AdbError as exc:
            ok = False
            log.error(f"-> Không khởi động lại được ADB: {exc}")
    finally:
        if monitor is not None:
            monitor.resume()
    progress.update(1.0, "Hoàn tất" if ok else "Lỗi", 4, 4, force=True)
    progress.state(JobState.SUCCESS if ok else JobState.FAILED)
    return ok
