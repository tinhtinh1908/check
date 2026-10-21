"""Windows integration via ctypes and built-in tools: UAC elevation of one command, single-instance mutex,
window focus, process listing/killing and the logical work area used to size the window."""

from __future__ import annotations

import csv
import ctypes
import io
import subprocess
from ctypes import wintypes

CREATE_NO_WINDOW = 0x08000000
ERROR_ALREADY_EXISTS = 183
ERROR_CANCELLED = 1223
SEE_MASK_NOCLOSEPROCESS = 0x00000040
SEE_MASK_NOASYNC = 0x00000100
SW_HIDE = 0
SW_RESTORE = 9
INFINITE = 0xFFFFFFFF
SPI_GETWORKAREA = 0x0030

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_user32 = ctypes.WinDLL("user32", use_last_error=True)


class SHELLEXECUTEINFOW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


_shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(SHELLEXECUTEINFOW)]
_shell32.ShellExecuteExW.restype = wintypes.BOOL
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_kernel32.GetExitCodeProcess.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowW.restype = wintypes.HWND
_user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.SystemParametersInfoW.argtypes = [wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT]
_user32.SystemParametersInfoW.restype = wintypes.BOOL


class ElevationCancelled(Exception):
    """The user answered No on the UAC prompt."""


class ElevationError(Exception):
    """The elevated process could not be started."""


FLUTTER_WINDOW_CLASS = "FLUTTER_RUNNER_WIN32_WINDOW"


def find_app_window(title: str) -> int | None:
    """The Flet (Flutter) window with this title; plain title match only as a fallback."""
    return _user32.FindWindowW(FLUTTER_WINDOW_CLASS, title) or _user32.FindWindowW(None, title) or None


def run_elevated(exe: str, params: str, cwd: str | None = None, owner_title: str | None = "BULL TOOL") -> int:
    """Run ``exe params`` elevated (UAC prompt), hidden, wait for it and return its exit code.

    ``params`` go straight to CreateProcess (no shell), so no command interpreter parses the paths.
    The prompt is parented to the app window so it does not open behind it (the Python process that
    asks has no window of its own).
    """
    info = SHELLEXECUTEINFOW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_NOCLOSEPROCESS | SEE_MASK_NOASYNC
    info.hwnd = find_app_window(owner_title) if owner_title else None
    info.lpVerb = "runas"
    info.lpFile = exe
    info.lpParameters = params
    info.lpDirectory = cwd
    info.nShow = SW_HIDE
    if not _shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == ERROR_CANCELLED:
            raise ElevationCancelled()
        raise ElevationError(f"ShellExecuteEx failed (error {error})")
    if not info.hProcess:
        return 0
    try:
        _kernel32.WaitForSingleObject(info.hProcess, INFINITE)
        code = wintypes.DWORD()
        _kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
        return int(code.value)
    finally:
        _kernel32.CloseHandle(info.hProcess)


_mutex: int | None = None


def acquire_single_instance(name: str) -> bool:
    """Create the named mutex; False when another instance already holds it."""
    global _mutex
    handle = _kernel32.CreateMutexW(None, False, name)
    error = ctypes.get_last_error()
    if not handle:
        return True  # cannot tell; never block startup because of this
    if error == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return False
    _mutex = handle
    return True


def release_single_instance() -> None:
    global _mutex
    if _mutex:
        _kernel32.CloseHandle(_mutex)
        _mutex = None


def focus_window(title: str) -> bool:
    """Bring the running app's window to the front (Flutter window class first, so an Explorer folder
    that happens to have the same name is not picked)."""
    hwnd = _user32.FindWindowW(FLUTTER_WINDOW_CLASS, title)
    if not hwnd:
        return False
    _user32.ShowWindow(hwnd, SW_RESTORE)
    _user32.SetForegroundWindow(hwnd)
    return True


def list_processes() -> list[str]:
    """Image names of running processes (``tasklist`` CSV; image names are never localized)."""
    result = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, encoding="oem", errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )
    return [row[0] for row in csv.reader(io.StringIO(result.stdout)) if row]


def taskkill(image: str) -> bool:
    """Force-kill every process with this image name (and its children); True when something was killed."""
    result = subprocess.run(
        ["taskkill", "/F", "/T", "/IM", image], capture_output=True, creationflags=CREATE_NO_WINDOW
    )
    return result.returncode == 0


def work_area_logical() -> tuple[int, int] | None:
    """Primary monitor work area (excluding the taskbar) in logical (96-DPI) pixels."""
    rect = wintypes.RECT()
    if not _user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
        return None
    try:
        dpi = _user32.GetDpiForSystem()
    except AttributeError:
        dpi = 96
    scale = (dpi or 96) / 96
    return int((rect.right - rect.left) / scale), int((rect.bottom - rect.top) / scale)
