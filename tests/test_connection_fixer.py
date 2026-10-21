import re
import sys
import threading
from pathlib import Path

from bull_tool.core import connection_fixer
from bull_tool.core.adb import AdbClient, AdbServer
from bull_tool.core.adb import server as server_module
from bull_tool.core.adb.protocol import AdbConnectionError
from bull_tool.core.connection_fixer import KILL_LIST, find_running, fix_connection
from bull_tool.core.events import EventBus, JobState, JobStateEvent, LogEvent, ProgressEvent
from tests.helpers import unused_port

BAT = Path(__file__).resolve().parents[1] / "@ANDROID.bat"


class FakeServer:
    def __init__(self, calls, fail=False):
        self.calls = calls
        self.fail = fail

    def kill(self):
        self.calls.append("server.kill")

    def ensure_running(self):
        self.calls.append("server.ensure_running")
        if self.fail:
            raise AdbConnectionError("boom")
        return 41


class FakeMonitor:
    def __init__(self, calls):
        self.calls = calls

    def pause(self):
        self.calls.append("monitor.pause")

    def resume(self):
        self.calls.append("monitor.resume")


def test_kill_list_matches_batch_file():
    text = BAT.read_text(encoding="utf-8")
    batch_list = re.search(r'set "KILL_LIST=([^"]+)"', text).group(1).split()
    assert list(KILL_LIST) == batch_list
    assert len(KILL_LIST) == 29


def test_find_running_is_case_insensitive():
    assert find_running(["explorer.exe", "hisuite.EXE", "scrcpy.exe"]) == ["HiSuite.exe", "scrcpy.exe"]
    assert find_running([]) == []


def test_fix_connection_runs_batch_steps_in_order():
    calls = []
    bus = EventBus()

    def kill(name):
        calls.append(f"kill {name}")
        return name == "scrcpy.exe"

    ok = fix_connection(FakeServer(calls), bus, ["scrcpy.exe"], monitor=FakeMonitor(calls), kill=kill)
    assert ok
    assert calls == [
        "kill scrcpy.exe", "monitor.pause", "server.kill", "kill adb.exe", "server.ensure_running", "monitor.resume",
    ]
    events = bus.drain()
    texts = [e.text for e in events if isinstance(e, LogEvent)]
    assert "-> Đã tắt scrcpy.exe" in texts
    assert "-> Không còn tiến trình adb.exe nào đang chạy." in texts
    steps = [e.step for e in events if isinstance(e, ProgressEvent)]
    assert steps[:4] == [1, 2, 3, 4]
    assert [e.state for e in events if isinstance(e, JobStateEvent)][-1] == JobState.SUCCESS


def test_fix_connection_reports_restart_failure_and_still_resumes():
    calls = []
    bus = EventBus()
    ok = fix_connection(FakeServer(calls, fail=True), bus, [], monitor=FakeMonitor(calls), kill=lambda n: False)
    assert not ok
    assert calls[-1] == "monitor.resume"
    texts = [e.text for e in bus.drain() if isinstance(e, LogEvent)]
    assert "-> Không thấy Xiaomi PC Suite / app truyền màn hình nào đang chạy." in texts


def test_fix_connection_without_monitor_only_restarts_the_server():
    calls = []
    ok = fix_connection(FakeServer(calls), EventBus(), [], monitor=None, kill=lambda name: False)
    assert ok
    assert calls == ["server.kill", "server.ensure_running"]


def test_fix_connection_reports_when_adb_processes_are_killed():
    calls = []
    bus = EventBus()
    ok = fix_connection(
        FakeServer(calls), bus, [], monitor=FakeMonitor(calls), kill=lambda name: name == "adb.exe",
    )
    assert ok
    texts = [e.text for e in bus.drain() if isinstance(e, LogEvent)]
    assert "-> Đã tắt các tiến trình adb.exe." in texts
    assert calls == ["monitor.pause", "server.kill", "server.ensure_running", "monitor.resume"]


def test_fix_connection_failed_restart_ends_in_failed_state():
    calls = []
    bus = EventBus()
    ok = fix_connection(
        FakeServer(calls, fail=True), bus, [], monitor=FakeMonitor(calls), kill=lambda name: False,
    )
    assert not ok
    states = [e.state for e in bus.drain() if isinstance(e, JobStateEvent)]
    assert states[-1] == JobState.FAILED


def test_cancel_while_closing_apps_stops_before_adb_is_touched():
    calls = []
    bus = EventBus()
    cancel = threading.Event()

    def kill(name):  # the app starts closing while step 1 closes the first app
        calls.append(f"kill {name}")
        cancel.set()
        return True

    ok = fix_connection(
        FakeServer(calls), bus, ["scrcpy.exe", "Vysor.exe"], monitor=FakeMonitor(calls), kill=kill, cancel=cancel,
    )
    assert ok is False
    assert calls == ["kill scrcpy.exe", "monitor.resume"]
    events = bus.drain()
    assert "Đã dừng sửa kết nối." in [e.text for e in events if isinstance(e, LogEvent)]
    final = [e for e in events if isinstance(e, JobStateEvent)][-1]
    assert (final.state, final.message) == (JobState.CANCELLED, "Đã dừng")


def test_cancel_after_adb_was_stopped_skips_the_restart_and_resumes_tracking():
    calls = []
    cancel = threading.Event()
    server = FakeServer(calls)

    def kill_server():  # the app starts closing while step 2 stops the adb server
        calls.append("server.kill")
        cancel.set()

    server.kill = kill_server
    ok = fix_connection(
        server, EventBus(), [], monitor=FakeMonitor(calls), kill=lambda name: calls.append(f"kill {name}"),
        cancel=cancel,
    )
    assert ok is False
    assert calls[:2] == ["monitor.pause", "server.kill"] and calls[-1] == "monitor.resume"
    assert "kill adb.exe" not in calls and "server.ensure_running" not in calls


def test_server_closed_during_the_fix_is_not_restarted(monkeypatch):
    starts = []
    monkeypatch.setattr(server_module.subprocess, "run", lambda args, **kwargs: starts.append(args))
    server = AdbServer(AdbClient(port=unused_port()), adb_exe=Path(sys.executable))
    bus = EventBus()

    def kill(name):  # the window closes while step 1 closes apps
        server.close()
        return False

    assert fix_connection(server, bus, ["scrcpy.exe"], kill=kill) is False
    assert starts == [] and not server.owned
    events = bus.drain()
    assert any(isinstance(e, LogEvent) and e.text.startswith("-> Không khởi động lại được ADB") for e in events)
    assert [e.state for e in events if isinstance(e, JobStateEvent)][-1] == JobState.FAILED


def test_find_running_defaults_to_the_live_process_list(monkeypatch):
    monkeypatch.setattr(connection_fixer, "list_processes", lambda: ["explorer.exe", "scrcpy.exe"])
    assert find_running() == ["scrcpy.exe"]
