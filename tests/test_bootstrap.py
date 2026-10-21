import io
import os
from types import SimpleNamespace

import pytest

from bull_tool.core.adb import AdbClient, AdbServer
from bull_tool.core.bootstrap import AppServices, run_bootstrap
from bull_tool.core.driver_installer import DriverResult, install_driver
from bull_tool.core.events import EventBus, JobState, JobStateEvent, Level, LogEvent, ProgressEvent, StatusEvent
from bull_tool.core.payload import PLATFORM_TOOLS_ZIP, PayloadNotFoundError, ResourceStore
from bull_tool.core.settings import load_settings
from tests.fake_adb_server import FakeAdbServer
from tests.helpers import unused_port, zip_bytes


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BULL_TOOL_DATA_DIR", str(tmp_path / "data"))
    inner = zip_bytes({"platform-tools/adb.exe": os.urandom(2000), "platform-tools/source.properties":
                       b"Pkg.Revision=36.0.2\n"})
    payload = tmp_path / "payload.zip"
    payload.write_bytes(zip_bytes({PLATFORM_TOOLS_ZIP: inner}))
    fake = FakeAdbServer()
    fake.track_hold = True
    yield fake, (lambda: ResourceStore(open(payload, "rb"), str(payload)))
    fake.close()


def statuses(events):
    return {(e.key, e.value) for e in events if isinstance(e, StatusEvent)}


def test_bootstrap_ready_with_driver_installed(env):
    fake, open_store = env
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    try:
        assert run_bootstrap(services, open_store=open_store, driver_check=lambda: True)
        events = services.bus.drain(10_000)
        assert {("tools", "36.0.2"), ("driver", "ok"), ("bootstrap", "ready")} <= statuses(events)
        assert [e.state for e in events if isinstance(e, JobStateEvent)][-1] == JobState.SUCCESS
        assert services.ready and services.runner is not None and not services.server.owned
    finally:
        services.shutdown()
        services.shutdown()  # idempotent
    assert not fake.killed  # server was not started by the app, so it is left running


def test_bootstrap_first_run_installs_driver_and_remembers_decline(env):
    fake, open_store = env
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    calls = []

    def declined(store, log, progress):
        calls.append(store)
        return DriverResult(False, 1223, "Đã huỷ", cancelled=True)

    try:
        run_bootstrap(services, open_store=open_store, driver_check=lambda: False, driver_install=declined)
    finally:
        services.shutdown()
    assert len(calls) == 1
    assert ("driver", "missing") in statuses(services.bus.drain(10_000))
    assert load_settings().driver_auto_attempted is True

    again = AppServices(EventBus(), settings=load_settings(), client=AdbClient(port=fake.port))
    try:
        run_bootstrap(again, open_store=open_store, driver_check=lambda: False, driver_install=declined)
    finally:
        again.shutdown()
    assert len(calls) == 1  # not prompted again


def test_bootstrap_fatal_when_payload_missing(env):
    fake, _open_store = env

    def missing():
        raise PayloadNotFoundError("no payload")

    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    assert not run_bootstrap(services, open_store=missing)
    assert ("bootstrap", "fatal") in statuses(services.bus.drain())
    services.shutdown()


def test_platform_tools_without_adb_exe_is_fatal(tmp_path, monkeypatch):
    monkeypatch.setenv("BULL_TOOL_DATA_DIR", str(tmp_path / "data"))
    payload = tmp_path / "payload.zip"
    payload.write_bytes(zip_bytes({PLATFORM_TOOLS_ZIP: zip_bytes({"platform-tools/fastboot.exe": b"x"})}))
    fake = FakeAdbServer()
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    try:
        assert not run_bootstrap(services, open_store=lambda: ResourceStore(open(payload, "rb"), str(payload)))
        assert ("bootstrap", "fatal") in statuses(services.bus.drain(10_000))
        assert not services.ready and services.monitor is None
    finally:
        services.shutdown()
        fake.close()


def test_unreachable_adb_is_reported_and_bootstrap_still_becomes_ready(env):
    _fake, open_store = env
    services = AppServices(EventBus(), client=AdbClient(port=unused_port()))
    try:
        assert run_bootstrap(services, open_store=open_store, driver_check=lambda: True)
        events = services.bus.drain(10_000)
        assert ("adb", "down") in statuses(events) and services.ready
        assert not services.server.owned
        assert any(isinstance(e, LogEvent) and e.level == Level.ERROR and "ADB server" in e.text for e in events)
    finally:
        services.shutdown()


def test_driver_install_failure_is_a_warning_not_a_fatal_error(env):
    fake, open_store = env
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    failed = DriverResult(False, 1, "Lỗi cài driver (mã 1)")
    try:
        ok = run_bootstrap(
            services, open_store=open_store, driver_check=lambda: False,
            driver_install=lambda store, log, progress: failed,
        )
        assert ok and services.ready and services.driver_ok is False
        assert ("driver", "missing") in statuses(services.bus.drain(10_000))
        assert load_settings().driver_auto_attempted is True  # any failed first-run attempt stops the auto prompt
    finally:
        services.shutdown()


def test_driver_install_success_marks_driver_ok(env):
    fake, open_store = env
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    try:
        run_bootstrap(
            services, open_store=open_store, driver_check=lambda: False,
            driver_install=lambda store, log, progress: DriverResult(True, 0, "ok"),
        )
        assert services.driver_ok is True
        assert ("driver", "ok") in statuses(services.bus.drain(10_000))
    finally:
        services.shutdown()


def test_unreadable_payload_io_error_is_fatal(env):
    fake, _open_store = env

    def unreadable():
        raise OSError("disk read error")

    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    assert not run_bootstrap(services, open_store=unreadable)
    assert ("bootstrap", "fatal") in statuses(services.bus.drain())
    services.shutdown()


def test_shutdown_still_stops_an_owned_server_when_another_step_fails(env):
    fake, _open_store = env

    class BrokenMonitor:
        def stop(self):
            raise RuntimeError("monitor already gone")

    client = AdbClient(port=fake.port)
    services = AppServices(EventBus(), client=client)
    services.monitor = BrokenMonitor()
    services.server = AdbServer(client)
    services.server.owned = True
    services.shutdown()
    assert fake.killed


def test_bootstrap_starts_nothing_when_the_app_is_already_closing(env, monkeypatch):
    fake, open_store = env
    starts, driver_calls = [], []
    monkeypatch.setattr(AdbServer, "ensure_running", lambda self, timeout=15.0: starts.append(self))
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    services.begin_close()  # the window was closed before bootstrap got to the adb server
    try:
        ok = run_bootstrap(
            services, open_store=open_store, driver_check=lambda: driver_calls.append("check"),
            driver_install=lambda *args: driver_calls.append("install"),
        )
        assert ok is False and starts == [] and driver_calls == []
        assert services.monitor is None and services.server.closed
        assert ("bootstrap", "fatal") not in statuses(services.bus.drain(10_000))
    finally:
        services.shutdown()


def test_closing_while_adb_starts_skips_the_driver_prompt_and_the_monitor(env):
    fake, open_store = env
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    services.bus.add_listener(
        lambda e: isinstance(e, ProgressEvent) and e.label == "Khởi động ADB server…" and services.begin_close()
    )
    prompts = []
    try:
        ok = run_bootstrap(services, open_store=open_store, driver_check=lambda: False,
                           driver_install=lambda *args: prompts.append(args))
        assert ok is False and prompts == [] and services.monitor is None
        assert ("bootstrap", "fatal") not in statuses(services.bus.drain(10_000))
    finally:
        services.shutdown()


def test_closing_while_the_driver_prompt_is_up_starts_no_device_tracking(env):
    fake, open_store = env
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))

    def install_while_the_window_closes(store, log, progress):
        services.begin_close()  # the user closes the window while Windows shows the UAC prompt
        return DriverResult(False, 1223, "Đã huỷ", cancelled=True)

    try:
        ok = run_bootstrap(services, open_store=open_store, driver_check=lambda: False,
                           driver_install=install_while_the_window_closes)
        assert ok is False and services.monitor is None and services.runner is None
        assert ("bootstrap", "fatal") not in statuses(services.bus.drain(10_000))
        # an install cut short by closing the app is not a refusal: the next launch offers it again
        assert services.settings.driver_auto_attempted is False
        assert load_settings().driver_auto_attempted is False
    finally:
        services.shutdown()


def test_shutdown_closes_the_session_log_after_the_server_and_the_store():
    order = []
    services = AppServices(EventBus())
    services.monitor = SimpleNamespace(stop=lambda: order.append("monitor.stop"))
    services.server = SimpleNamespace(
        close=lambda: order.append("server.close"), shutdown=lambda: order.append("server.shutdown"),
    )
    services.store = SimpleNamespace(close=lambda: order.append("store.close"))
    services.session_log = SimpleNamespace(close=lambda: order.append("session_log.close"))
    services.shutdown()
    assert order == ["server.close", "monitor.stop", "server.shutdown", "store.close", "session_log.close"]
    assert services.closing.is_set()


def test_damaged_payload_container_is_fatal_not_a_crash(env):
    fake, _open_store = env

    def damaged():
        return ResourceStore(io.BytesIO(b"damaged container"), "damaged")

    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    try:
        assert not run_bootstrap(services, open_store=damaged)
        assert ("bootstrap", "fatal") in statuses(services.bus.drain(10_000))
    finally:
        services.shutdown()


def test_damaged_platform_tools_archive_is_fatal_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("BULL_TOOL_DATA_DIR", str(tmp_path / "data"))
    payload = tmp_path / "payload.zip"
    payload.write_bytes(zip_bytes({PLATFORM_TOOLS_ZIP: b"damaged platform-tools archive"}))
    fake = FakeAdbServer()
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))
    try:
        assert not run_bootstrap(services, open_store=lambda: ResourceStore(open(payload, "rb"), str(payload)))
        assert ("bootstrap", "fatal") in statuses(services.bus.drain(10_000))
    finally:
        services.shutdown()
        fake.close()


def test_corrupt_driver_member_is_a_warning_not_a_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("BULL_TOOL_DATA_DIR", str(tmp_path / "data"))
    driver_inf = b"; android winusb driver installation MARKER-0123456789"
    inner = zip_bytes({
        "platform-tools/adb.exe": os.urandom(2000),
        "platform-tools/source.properties": b"Pkg.Revision=36.0.2\n",
    })
    raw = zip_bytes({PLATFORM_TOOLS_ZIP: inner, "USB_DRIVER_XIAOMI/android_winusb.inf": driver_inf})
    index = raw.find(driver_inf[5:37])
    assert index > 0
    damaged = bytearray(raw)
    damaged[index] ^= 0xFF
    payload = tmp_path / "payload.zip"
    payload.write_bytes(bytes(damaged))
    fake = FakeAdbServer()
    services = AppServices(EventBus(), client=AdbClient(port=fake.port))

    def no_elevation(exe, params, cwd):
        raise AssertionError("pnputil must not run when the driver package is damaged")

    try:
        ok = run_bootstrap(
            services, open_store=lambda: ResourceStore(open(payload, "rb"), str(payload)),
            driver_check=lambda: False,
            driver_install=lambda store, log, progress: install_driver(
                store, log, progress, elevate=no_elevation, root=tmp_path / "store",
            ),
        )
        assert ok and services.ready and services.driver_ok is False
    finally:
        services.shutdown()
        fake.close()
