"""AppController on a headless Flet page: device selection, profile suggestions, info reads, busy feedback and
the exit path. Device reads use the real JobRunner.read_info over a gated fake client; profile runs, the
connection fix and adb are fakes, so nothing touches a phone, adb or a window."""

import asyncio
import threading
import time
from dataclasses import dataclass, field

import flet as ft

from bull_tool.core.adb.client import DeviceEntry, ShellResult
from bull_tool.core.adb.protocol import AdbError
from bull_tool.core.bootstrap import BOOT_JOB, AppServices
from bull_tool.core.driver_installer import DriverResult
from bull_tool.core.events import (
    DevicesEvent,
    EventBus,
    JobState,
    JobStateEvent,
    LogEvent,
    Progress,
    StatusEvent,
)
from bull_tool.core.job_runner import PROFILE_JOB, JobRunner, Summary
from bull_tool.ui import controller as controller_module
from bull_tool.ui.controller import AppController
from tests.flet_harness import click, mount_page

PROPS = {
    "A111": "[ro.product.brand]: [Redmi]\n[ro.product.manufacturer]: [Xiaomi]\n"
            "[ro.product.model]: [23129RAA4G]\n[ro.product.marketname]: [Redmi Note 13]\n",
    "B222": "[ro.product.brand]: [OPPO]\n[ro.product.manufacturer]: [OPPO]\n[ro.product.model]: [CPH2581]\n",
}
A = DeviceEntry("A111", "device", model="23129RAA4G", transport_id="1")
B = DeviceEntry("B222", "device", model="CPH2581", transport_id="2")


class GatedClient:
    """Fake AdbClient for JobRunner.read_info: a serial's read blocks until its gate opens."""

    def __init__(self, auto_open: bool) -> None:
        self.auto_open = auto_open
        self.gates: dict[str, threading.Event] = {}
        self.fail: dict[str, str] = {}
        self.lock = threading.Lock()

    def gate(self, serial: str) -> threading.Event:
        with self.lock:
            if serial not in self.gates:
                self.gates[serial] = threading.Event()
                if self.auto_open:
                    self.gates[serial].set()
            return self.gates[serial]

    def hold(self, serial: str) -> None:
        self.gate(serial).clear()

    def release(self, serial: str, fail: str | None = None) -> None:
        if fail:
            self.fail[serial] = fail
        self.gate(serial).set()

    def features(self, serial: str) -> frozenset[str]:
        if not self.gate(serial).wait(10):
            raise AdbError("test gate timeout")
        if serial in self.fail:
            raise AdbError(self.fail[serial])
        return frozenset()

    def shell(self, serial: str, cmd: str, timeout: float = 60.0, features=None) -> ShellResult:
        return ShellResult(PROPS.get(serial, "") if cmd == "getprop" else "", "", 0)


class RecordingRunner:
    """read_info is the real JobRunner.read_info; run_profile records the call and runs until released or
    cancelled (it never touches a phone)."""

    def __init__(self, bus: EventBus, client: GatedClient, events: list[str]) -> None:
        self.real = JobRunner(client, None, bus)
        self.bus = bus
        self.events = events
        self.read_calls: list[str] = []
        self.read_done: list[threading.Event] = []
        self.profile_calls: list[tuple[str, str]] = []
        self.release_profile = threading.Event()
        self.release_profile.set()

    def read_info(self, serial: str):
        done = threading.Event()
        self.read_calls.append(serial)
        self.read_done.append(done)
        try:
            return self.real.read_info(serial)
        finally:
            done.set()

    def run_profile(self, serial, profile, cancel):
        progress = Progress(self.bus, PROFILE_JOB, profile.name)
        progress.state(JobState.RUNNING)
        self.profile_calls.append((serial, profile.id))
        summary = Summary(profile.id, profile.name, serial)
        while not self.release_profile.wait(0.02):
            if cancel.is_set():
                self.events.append("job stopped")
                summary.cancelled = True
                break
        progress.state(JobState.CANCELLED if summary.cancelled else JobState.SUCCESS, summary)
        return summary


class FakeServer:
    def close(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


class FakeStore:
    def close(self) -> None:
        pass


@dataclass
class App:
    page: ft.Page
    session: object
    controller: AppController
    runner: RecordingRunner
    client: GatedClient
    bus: EventBus
    events: list[str] = field(default_factory=list)


async def make_app(monkeypatch, auto_open: bool = True, ready: bool = True) -> App:
    page, session, _conn = mount_page()
    events: list[str] = []

    async def fake_destroy(_window) -> None:  # the real one waits for the desktop client to answer
        events.append("destroy")

    monkeypatch.setattr(type(page.window), "destroy", fake_destroy)
    bus = EventBus()
    services = AppServices(bus)
    client = GatedClient(auto_open)
    runner = RecordingRunner(bus, client, events)
    services.runner, services.server, services.store = runner, FakeServer(), FakeStore()
    real_shutdown = services.shutdown

    def recording_shutdown() -> None:
        events.append("shutdown")
        real_shutdown()

    services.shutdown = recording_shutdown
    controller = AppController(page, services, bootstrap=lambda _services: True)
    controller.pump.start = lambda: None  # the tests drive the pump themselves
    controller.apply_layout(1280, 800)
    page.add(controller.build())
    controller.start()
    bus.emit(JobStateEvent(BOOT_JOB, "Khởi động", JobState.SUCCESS))
    bus.emit(StatusEvent("adb", "up"))
    if ready:
        bus.emit(StatusEvent("bootstrap", "ready"))
    await controller.pump.tick()
    return App(page, session, controller, runner, client, bus, events)


async def tick(app: App) -> None:
    await app.controller.pump.tick()


async def devices(app: App, *entries: DeviceEntry) -> None:
    app.bus.emit(DevicesEvent(tuple(entries)))
    await tick(app)


async def finish_read(app: App, index: int) -> None:
    """Wait until read #index has emitted its events, then let the pump dispatch them."""
    deadline = time.monotonic() + 5
    while len(app.runner.read_done) <= index:  # the read thread registers itself once it is running
        assert time.monotonic() < deadline, f"read #{index} never started"
        await asyncio.sleep(0.005)
    assert await asyncio.to_thread(app.runner.read_done[index].wait, 5), f"read #{index} did not finish"
    await tick(app)


async def until(app: App, condition, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, "condition not reached"
        await asyncio.sleep(0.01)
        await tick(app)


def open_dialogs(app: App, kind=ft.AlertDialog) -> list:
    return [d for d in app.page._dialogs.controls if isinstance(d, kind) and d.open]


def open_confirms(app: App) -> list[ft.AlertDialog]:
    """Open questions (a cancel button plus an action), as opposed to the one-button summary/message dialogs."""
    return [d for d in open_dialogs(app) if len(d.actions) == 2]


def texts(control) -> list[str]:
    found: list[str] = []

    def walk(node) -> None:
        if isinstance(node, ft.Text) and isinstance(node.value, str):
            found.append(node.value)
        for attr in ("title", "content", "controls", "actions"):
            child = getattr(node, attr, None)
            for item in child if isinstance(child, list) else [child]:
                if isinstance(item, ft.Control):
                    walk(item)

    walk(control)
    return found


async def start_profile_run(app: App) -> None:
    """One ready phone (A, Xiaomi) and a profile run that keeps going until released or cancelled."""
    app.runner.release_profile.clear()
    await devices(app, A)
    await finish_read(app, 0)
    await app.controller._on_start_click(None)
    await until(app, lambda: app.controller.state.job == PROFILE_JOB and app.runner.profile_calls)


class FakeSelect:
    def __init__(self, value: str) -> None:
        self.control = type("Selector", (), {"value": value})()


def run(scenario) -> None:
    asyncio.run(scenario())


# -- device selection and profile suggestions -----------------------------------------------------------
def test_a_cable_blip_of_the_chosen_phone_does_not_move_start_to_the_other_phone(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A, B)
        await finish_read(app, 0)
        await devices(app, B)  # A's cable blips: B is shown meanwhile
        await finish_read(app, 1)
        await devices(app, B, A)
        await finish_read(app, 2)
        await app.controller._on_start_click(None)
        await until(app, lambda: app.runner.profile_calls)
        assert app.runner.profile_calls == [("A111", "xiaomi")]
        assert open_confirms(app) == []

    run(scenario)


def test_phones_returning_one_by_one_after_an_adb_restart_keep_the_chosen_phone(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A, B)
        await finish_read(app, 0)
        await app.controller._select_device(FakeSelect("B222"))  # the user works on B
        await finish_read(app, 1)
        await devices(app)  # adb restarted ("Sửa lỗi kết nối" or a hiccup)
        await devices(app, A)  # A comes back first
        await finish_read(app, 2)
        await devices(app, A, B)
        await finish_read(app, 3)
        assert app.controller.state.selected_serial == "B222"
        await app.controller._on_start_click(None)
        await until(app, lambda: app.runner.profile_calls)
        assert app.runner.profile_calls == [("B222", "oppo")]

    run(scenario)


def test_starting_on_a_phone_that_replaced_the_chosen_one_asks_first(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A, B)
        await finish_read(app, 0)
        await devices(app, B)  # the chosen phone A is gone
        await finish_read(app, 1)
        await app.controller._on_start_click(None)
        await tick(app)
        [confirm] = open_confirms(app)
        message = " ".join(texts(confirm))
        assert "A111" in message and "B222" in message
        assert app.runner.profile_calls == []

    run(scenario)


def test_suggestions_resume_for_the_next_phone_after_a_manual_pick(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A)
        await finish_read(app, 0)
        await app.controller._pick_profile("xiaomi")  # the operator clicks the highlighted card once
        await devices(app)
        await devices(app, B)
        await finish_read(app, 1)
        assert app.controller.state.selected_profile == "oppo"

    run(scenario)


def test_a_manual_pick_survives_replugging_the_same_phone(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A)
        await finish_read(app, 0)
        await app.controller._pick_profile("sony")
        await devices(app)
        await devices(app, A)
        await finish_read(app, 1)
        assert app.controller.state.selected_profile == "sony"

    run(scenario)


def test_a_late_read_failure_is_not_shown_on_another_phone(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch, auto_open=False)
        await devices(app, A, B)  # A's read is in flight
        await devices(app, B)  # A unplugged: B is selected and waits for its own read
        app.client.release("A111", fail="device 'A111' not found")
        await finish_read(app, 0)
        assert app.controller.device_panel.state == "reading"
        app.client.release("B222")
        await finish_read(app, 1)
        assert app.runner.read_calls == ["A111", "B222"]
        assert app.controller.device_panel.state == "ready"

    run(scenario)


def test_each_phone_is_read_once_when_the_selection_changes_mid_read(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch, auto_open=False)
        await devices(app, A, B)
        await app.controller._select_device(FakeSelect("B222"))
        app.client.release("A111")
        await finish_read(app, 0)
        await devices(app, A, B, DeviceEntry("Z9", "unauthorized"))  # any later re-render
        app.client.release("B222")
        for index in range(1, len(app.runner.read_calls)):
            await finish_read(app, index)
        assert app.runner.read_calls == ["A111", "B222"]

    run(scenario)


def test_confirming_after_the_phone_changed_runs_nothing(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A, B)
        await finish_read(app, 0)
        await app.controller._pick_profile("oppo")  # mismatch: the confirm opens for A
        await app.controller._on_start_click(None)
        [confirm] = open_confirms(app)
        await devices(app, B)  # A unplugged while the dialog is open
        await finish_read(app, 1)
        await click(app.session, confirm.actions[1])  # "Vẫn chạy"
        await until(app, lambda: open_dialogs(app, ft.SnackBar))
        assert app.runner.profile_calls == []

    run(scenario)


def test_start_waits_for_a_new_phones_details(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A)
        await finish_read(app, 0)
        await devices(app)
        app.client.hold("B222")
        await devices(app, B)  # the previous phone's profile is still selected while B is read
        await app.controller._on_start_click(None)
        assert open_confirms(app) == [] and app.runner.profile_calls == []
        [toast] = open_dialogs(app, ft.SnackBar)
        assert any("Đang đọc" in text for text in texts(toast))
        app.client.release("B222")
        await finish_read(app, 1)
        assert app.controller.state.selected_profile == "oppo"

    run(scenario)


# -- busy feedback ------------------------------------------------------------------------------------------
def test_a_confirmed_action_that_finds_the_tool_busy_says_so(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)

        def must_not_run(*_args, **_kwargs):
            raise AssertionError("no second job may start while another one is busy")

        monkeypatch.setattr(controller_module, "fix_connection", must_not_run)
        monkeypatch.setattr(controller_module, "install_driver", must_not_run)
        app.controller.state.job = PROFILE_JOB
        await app.controller._run_fix([])
        await app.controller._run_driver()
        toasts = open_dialogs(app, ft.SnackBar)
        assert [controller_module.BUSY_MESSAGE in texts(t) for t in toasts] == [True, True]
        assert app.controller.state.job == PROFILE_JOB  # neither job took over the running one

    run(scenario)


def test_a_double_click_on_the_connection_fix_opens_one_confirm(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        monkeypatch.setattr(controller_module, "find_running", lambda: (time.sleep(0.05), [])[1])
        await asyncio.gather(app.controller._on_fix_click(), app.controller._on_fix_click())
        assert len(open_confirms(app)) == 1

    run(scenario)


def test_refresh_after_a_failed_start_keeps_the_error_on_screen(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch, ready=False)
        app.bus.emit(StatusEvent("bootstrap", "fatal", "payload hỏng"))
        await tick(app)
        await app.controller._refresh_device(None)
        assert app.controller._panel_key == ("fatal",)
        assert app.controller.device_panel.state == "error"

    run(scenario)


# -- exit ---------------------------------------------------------------------------------------------------
def test_closing_while_idle_shuts_down_then_closes_the_window(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await app.controller._request_close()
        assert app.events == ["shutdown", "destroy"]
        assert app.controller.services.closing.is_set()

    run(scenario)


def test_closing_during_a_job_stops_it_before_shutting_down(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await start_profile_run(app)
        await app.controller._request_close()
        [confirm] = open_confirms(app)
        await click(app.session, confirm.actions[1])  # "Dừng và thoát"
        assert app.events == ["job stopped", "shutdown", "destroy"]
        logged = [e.text for e in app.bus.drain() if isinstance(e, LogEvent)]
        assert any("trước khi thoát" in text for text in logged)

    run(scenario)


def test_a_second_close_request_does_not_stack_another_question(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await start_profile_run(app)
        await app.controller._request_close()
        await app.controller._request_close()  # Alt+F4 while the question is on screen
        assert len(open_confirms(app)) == 1
        app.runner.release_profile.set()
        await until(app, lambda: app.controller.state.job is None)

    run(scenario)


def test_the_exit_question_goes_away_when_the_job_ends(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await start_profile_run(app)
        await app.controller._request_close()
        [question] = open_confirms(app)
        app.runner.release_profile.set()
        await until(app, lambda: app.controller.state.job is None)
        assert not question.open
        assert app.events == []  # the app keeps running

    run(scenario)


def test_losing_the_client_cancels_the_job_and_shuts_down(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await start_profile_run(app)
        await app.controller.on_session_closed()
        await until(app, lambda: "job stopped" in app.events)
        assert "shutdown" in app.events and "destroy" not in app.events

    run(scenario)


def test_closing_does_not_wait_forever_for_a_job_that_ignores_stop(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        monkeypatch.setattr(controller_module, "JOB_STOP_WAIT", 0.3)
        stuck = threading.Event()

        def stubborn_run(serial, profile, cancel):
            app.runner.profile_calls.append((serial, profile.id))
            stuck.wait(5)  # e.g. a shell command that does not poll the cancel event
            return Summary(profile.id, profile.name, serial)

        app.runner.run_profile = stubborn_run
        await devices(app, A)
        await finish_read(app, 0)
        await app.controller._on_start_click(None)
        await until(app, lambda: app.controller.state.job == PROFILE_JOB and app.runner.profile_calls)
        started = time.monotonic()
        await app.controller._shutdown_and_exit()
        assert app.events == ["shutdown", "destroy"]
        assert time.monotonic() - started < 2  # the bound, not the stuck step, decides
        stuck.set()

    run(scenario)


def test_closing_during_the_connection_fix_cancels_its_remaining_steps(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        started = threading.Event()

        def slow_fix(server, bus, to_kill, monitor=None, kill=None, cancel=None):
            started.set()
            assert cancel is not None and cancel.wait(5)  # the exit path must stop the fix
            app.events.append("job stopped")
            return False

        monkeypatch.setattr(controller_module, "fix_connection", slow_fix)
        app.page.run_task(app.controller._run_fix, [])
        await until(app, lambda: started.is_set() and app.controller.state.job is not None)
        await app.controller._request_close()
        [confirm] = open_confirms(app)
        await click(app.session, confirm.actions[1])  # "Dừng và thoát"
        assert app.events == ["job stopped", "shutdown", "destroy"]
        assert open_dialogs(app, ft.SnackBar) == []  # no "fix failed" toast while the window closes

    run(scenario)


def test_confirming_after_the_profile_changed_runs_nothing(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A)
        await finish_read(app, 0)  # Xiaomi: the xiaomi profile is selected
        await devices(app)
        app.client.hold("B222")
        await devices(app, B)
        app.client.release("B222", fail="closed")
        await finish_read(app, 1)  # B's brand could not be read: the previous profile is still selected
        await app.controller._on_start_click(None)
        [confirm] = open_confirms(app)  # "Chưa đọc được hãng của máy …, vẫn chạy cấu hình Xiaomi?"
        app.client.fail.pop("B222")
        await devices(app)  # B's cable blips while the question is open
        await devices(app, B)
        await finish_read(app, 2)  # now OPPO is detected and the grid switches to oppo behind the dialog
        assert app.controller.state.selected_profile == "oppo"
        await click(app.session, confirm.actions[1])  # "Vẫn chạy": the xiaomi profile it asked about
        await until(app, lambda: open_dialogs(app, ft.SnackBar))
        assert app.runner.profile_calls == []

    run(scenario)


def test_the_phone_a_job_ran_on_becomes_the_users_phone(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A, B)
        await finish_read(app, 0)
        await devices(app, B)  # the chosen phone A is gone: B is shown
        await finish_read(app, 1)
        await app.controller._on_start_click(None)
        [confirm] = open_confirms(app)
        await click(app.session, confirm.actions[1])  # the user confirms running on B
        await until(app, lambda: app.runner.profile_calls and app.controller.state.job is None)
        await devices(app, B, A)  # A comes back
        assert app.runner.profile_calls == [("B222", "oppo")]
        assert app.controller.state.selected_serial == "B222"  # B stays: it is now the user's phone

    run(scenario)


def test_jobs_run_on_daemon_threads_and_pass_back_results_and_errors():
    async def scenario():
        assert await controller_module.run_in_daemon("test", lambda: threading.current_thread().daemon) is True

        def boom():
            raise ValueError("job failed")

        try:
            await controller_module.run_in_daemon("test", boom)
        except ValueError as exc:
            return str(exc)

    assert asyncio.run(scenario()) == "job failed"


def test_the_other_hub_phone_coming_back_first_does_not_become_the_users_phone(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A, B)  # A is the user's phone
        await finish_read(app, 0)
        await devices(app, B)  # A's cable drops
        await finish_read(app, 1)
        await devices(app)  # "Sửa lỗi kết nối" restarts adb: the list empties ...
        await devices(app, B)  # ... and B comes back first
        await finish_read(app, 2)
        assert app.controller.state.preferred_serial == "A111"
        await devices(app, B, A)  # the user plugs A back in
        await finish_read(app, 3)
        await app.controller._on_start_click(None)
        await until(app, lambda: app.runner.profile_calls)
        assert app.runner.profile_calls == [("A111", "xiaomi")] and open_confirms(app) == []

    run(scenario)


def test_a_phone_read_during_a_driver_install_gets_its_profile_after_it(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        release = threading.Event()

        def slow_install(store, log, progress=None):
            release.wait(5)  # Windows is still asking for UAC
            return DriverResult(True, 0, "Đã cài driver")

        monkeypatch.setattr(controller_module, "install_driver", slow_install)
        app.page.run_task(app.controller._run_driver)
        await until(app, lambda: app.controller.state.job is not None)
        await devices(app, B)  # an OPPO is plugged in meanwhile and read
        await finish_read(app, 0)
        assert app.controller.state.selected_profile is None  # no auto pick while a job runs
        release.set()
        await until(app, lambda: app.controller.state.job is None)
        assert app.controller.state.selected_profile == "oppo"

    run(scenario)


def test_a_pick_does_not_carry_over_to_another_phone_reporting_the_same_serial(monkeypatch):
    async def scenario():
        app = await make_app(monkeypatch)
        await devices(app, A)  # a Redmi with the serial A111
        await finish_read(app, 0)
        await app.controller._pick_profile("xiaomi")  # habit click on the highlighted card
        await devices(app)
        monkeypatch.setitem(PROPS, "A111", PROPS["B222"])  # next phone: an OPPO reporting the same serial
        await devices(app, DeviceEntry("A111", "device", model="CPH2581", transport_id="5"))
        await finish_read(app, 1)
        assert app.controller.state.selected_profile == "oppo"

    run(scenario)
