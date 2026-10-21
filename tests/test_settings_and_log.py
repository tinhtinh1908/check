import pathlib
import threading
import time

import pytest

from bull_tool.core import settings as settings_module
from bull_tool.core.events import EventBus, Level, LogEvent, StatusEvent
from bull_tool.core.session_log import SessionLog
from bull_tool.core.settings import Settings, load_settings, save_settings


def test_settings_roundtrip_and_defaults(tmp_path):
    path = tmp_path / "settings.json"
    assert load_settings(path) == Settings()
    assert save_settings(Settings(theme="light", driver_auto_attempted=True), path)
    assert load_settings(path) == Settings(theme="light", driver_auto_attempted=True)
    path.write_text("{not json", encoding="utf-8")
    assert load_settings(path) == Settings()
    path.write_text('{"theme": "neon"}', encoding="utf-8")
    assert load_settings(path).theme == "dark"
    path.write_text("[1, 2]", encoding="utf-8")
    assert load_settings(path) == Settings()


def test_session_log_writes_only_log_events_and_prunes(tmp_path):
    for i in range(25):
        (tmp_path / f"20200101-0000{i:02d}.log").write_text("old", encoding="utf-8")
    log = SessionLog(folder=tmp_path, keep=5)
    log.write(LogEvent(Level.OK, "Đã gỡ com.a", ts=time.time()))
    log.write(StatusEvent("adb", "up"))
    log.close()
    assert len(list(tmp_path.glob("*.log"))) == 5
    content = log.path.read_text(encoding="utf-8")
    assert "[OK   ] Đã gỡ com.a" in content and "adb" not in content


def test_session_log_failure_is_reported_once_and_never_raises(tmp_path):
    bus = EventBus()
    log = SessionLog(bus=bus, folder=tmp_path / "missing" / "deeper")
    log.write(LogEvent(Level.INFO, "x"))  # no file: silently ignored
    statuses = [e for e in bus.drain() if isinstance(e, StatusEvent)]
    assert len(statuses) == 1 and statuses[0].key == "log"


def test_save_settings_returns_false_when_the_folder_is_missing(tmp_path):
    target = tmp_path / "missing" / "settings.json"
    assert save_settings(Settings(), target) is False
    assert not target.exists() and not (tmp_path / "missing").exists()


@pytest.mark.parametrize("stall_after_snapshot", [True, False], ids=["after-snapshot", "before-rename"])
def test_overlapping_saves_end_with_the_newest_settings(tmp_path, monkeypatch, stall_after_snapshot):
    path = tmp_path / "settings.json"
    shared = Settings(theme="light")
    stalled, release = threading.Event(), threading.Event()
    real_asdict, real_replace = settings_module.asdict, settings_module.os.replace

    def stall_the_first_save():  # e.g. a virus scanner holding the file
        if threading.current_thread().name == "first":
            stalled.set()
            release.wait(5)

    def asdict(obj):
        snapshot = real_asdict(obj)
        if stall_after_snapshot:
            stall_the_first_save()
        return snapshot

    def replace(src, dst):
        if not stall_after_snapshot:
            stall_the_first_save()
        real_replace(src, dst)

    monkeypatch.setattr(settings_module, "asdict", asdict)
    monkeypatch.setattr(settings_module.os, "replace", replace)
    results = {}
    first = threading.Thread(target=lambda: results.update(first=save_settings(shared, path)), name="first")
    first.start()
    assert stalled.wait(5)
    shared.theme = "dark"  # the user toggles the theme again while the first save is still in flight
    second = threading.Thread(target=lambda: results.update(second=save_settings(shared, path)), name="second")
    second.start()
    second.join(0.3)
    release.set()
    first.join(5)
    second.join(5)
    assert results == {"first": True, "second": True}
    assert load_settings(path).theme == "dark"


def test_save_settings_returns_false_instead_of_raising_when_the_tmp_file_stays_locked(tmp_path, monkeypatch):
    def locked(*_args, **_kwargs):
        raise PermissionError(32, "The process cannot access the file because it is being used by another process")

    monkeypatch.setattr(settings_module.os, "replace", locked)
    monkeypatch.setattr(pathlib.Path, "unlink", locked)
    assert save_settings(Settings(theme="light"), tmp_path / "settings.json") is False


def test_session_log_reports_a_dead_file_once_and_keeps_running(tmp_path):
    bus = EventBus()
    log = SessionLog(bus=bus, folder=tmp_path)
    log._fp.close()  # simulate the file handle dying under the logger
    log.write(LogEvent(Level.INFO, "first"))
    log.write(LogEvent(Level.INFO, "second"))
    statuses = [e for e in bus.drain() if isinstance(e, StatusEvent)]
    assert len(statuses) == 1 and statuses[0].key == "log"
    log.close()
