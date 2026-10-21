import os

from bull_tool.core import win32


def test_single_instance_mutex():
    name = f"Local\\BULL-TOOL-test-{os.getpid()}"
    assert win32.acquire_single_instance(name)
    try:
        assert not win32.acquire_single_instance(name)
    finally:
        win32.release_single_instance()
    assert win32.acquire_single_instance(name)
    win32.release_single_instance()


def test_list_processes_contains_current_interpreter():
    names = {n.lower() for n in win32.list_processes()}
    assert "python.exe" in names or "pythonw.exe" in names


def test_taskkill_unknown_image_returns_false():
    assert win32.taskkill("bull-tool-no-such-process.exe") is False


def test_work_area_is_positive():
    area = win32.work_area_logical()
    assert area is not None and area[0] > 300 and area[1] > 200


def test_focus_missing_window_returns_false():
    assert win32.focus_window("BULL TOOL test window that does not exist") is False
