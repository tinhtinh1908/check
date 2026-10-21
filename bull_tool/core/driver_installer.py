"""Xiaomi USB driver: detection in the Windows driver store and elevated installation with pnputil.

Detection is language-independent: an installed copy of this package leaves
``DriverStore\\FileRepository\\android_winusb.inf_amd64_*\\xiaomiwinusba64.cat`` behind (Google's own
android_winusb package ships ``androidwinusba64.cat`` instead).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from bull_tool.core import paths
from bull_tool.core.events import Logger, Progress
from bull_tool.core.payload import DRIVER_INF, DRIVER_PREFIX, ResourceStore, file_matches, safe_join
from bull_tool.core.win32 import ElevationCancelled, ElevationError, run_elevated

DRIVER_CATALOG = "xiaomiwinusba64.cat"
PNPUTIL_OK = {
    0: "Đã cài driver USB Xiaomi",
    259: "Đã thêm driver USB Xiaomi (chưa có thiết bị phù hợp đang cắm)",
    3010: "Đã cài driver USB Xiaomi — cần khởi động lại máy tính",
}
PNPUTIL_ERRORS = {5: "Không đủ quyền quản trị (Admin)", 1223: "Đã huỷ cấp quyền"}
MANUAL_HINT = (
    "Có thể cài tay: Device Manager → chuột phải thiết bị Android → Update driver → "
    "Browse my computer → chọn thư mục {folder}"
)


@dataclass
class DriverResult:
    ok: bool
    code: int | None
    message: str
    reboot: bool = False
    cancelled: bool = False


def _system_root() -> Path:
    return Path(os.environ.get("SystemRoot", r"C:\Windows"))


def driver_store_root() -> Path:
    return _system_root() / "System32" / "DriverStore" / "FileRepository"


def is_installed(root: Path | None = None) -> bool:
    root = root or driver_store_root()
    try:
        return any((folder / DRIVER_CATALOG).is_file() for folder in root.glob("android_winusb.inf_amd64_*"))
    except OSError:
        return False


def extract_driver(store: ResourceStore, target: Path | None = None) -> Path:
    """Extract (or re-verify) the driver package and return the path of ``android_winusb.inf``."""
    target = target or paths.driver_dir()
    for name in store.names(DRIVER_PREFIX):
        dest = safe_join(target, name)
        if not file_matches(dest, store.info(name)):
            store.extract(name, dest)
    return safe_join(target, DRIVER_INF)


def install_driver(
    store: ResourceStore,
    log: Logger,
    progress: Progress | None = None,
    elevate: Callable[[str, str, str | None], int] = run_elevated,
    root: Path | None = None,
    target: Path | None = None,
) -> DriverResult:
    if progress:
        progress.update(0.7, "Giải nén driver USB Xiaomi…", force=True)
    inf = extract_driver(store, target)
    if progress:
        progress.update(None, "Đang chờ cấp quyền Admin (UAC)…", force=True)
    log.info("Cài driver USB Xiaomi — hãy bấm Yes (Có) trên hộp thoại quyền Admin")
    system32 = _system_root() / "System32"
    pnputil = system32 / "pnputil.exe"
    try:
        # working directory = System32, not the user-writable driver folder (nothing gets loaded from it)
        code = elevate(str(pnputil), f'/add-driver "{inf}" /install', str(system32))
    except ElevationCancelled:
        log.warn("Đã huỷ cài driver (không cấp quyền Admin). Có thể cài lại bằng nút “Cài driver”.")
        return DriverResult(False, 1223, PNPUTIL_ERRORS[1223], cancelled=True)
    except ElevationError as exc:
        log.error(f"Không chạy được trình cài driver: {exc}")
        return DriverResult(False, None, str(exc))
    installed = is_installed(root)
    if installed:
        message = PNPUTIL_OK.get(code, f"Driver USB Xiaomi đã có trên máy (pnputil mã {code})")
        log.ok(message)
        return DriverResult(True, code, message, reboot=code == 3010)
    message = PNPUTIL_ERRORS.get(code, f"Lỗi cài driver (mã {code})")
    log.error(message)
    log.warn(MANUAL_HINT.format(folder=inf.parent))
    return DriverResult(False, code, message)
