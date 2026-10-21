import asyncio

import flet as ft
from flet.controls.object_patch import Operation

from bull_tool.core.events import EventBus, JobState, JobStateEvent, Level, LogEvent, ProgressEvent, StatusEvent
from bull_tool.ui.ui_pump import LOGS, UiPump
from tests.flet_harness import mount_page


class FakePage:
    def run_task(self, handler, *args):
        return asyncio.ensure_future(handler(*args))


class FakeControl:
    """Duck-typed stand-in for an attached Flet control."""

    def __init__(self, fail: bool = False) -> None:
        self.updates = 0
        self.fail = fail

    @property
    def page(self):
        return "page"

    def update(self) -> None:
        if self.fail:
            raise ValueError("client rejected the patch")
        self.updates += 1


class DetachedControl(FakeControl):
    @property
    def page(self):
        raise RuntimeError("Control must be added to the page first")  # what flet's BaseControl.page does


def make_pump() -> tuple[UiPump, EventBus]:
    bus = EventBus()
    return UiPump(FakePage(), bus), bus


def ui_errors(bus: EventBus) -> list[LogEvent]:
    return [e for e in bus.drain() if isinstance(e, LogEvent) and e.level == Level.ERROR]


def test_failing_handler_does_not_stop_later_events_or_handlers():
    pump, bus = make_pump()
    seen = []

    def broken(event):
        if event.value == "first":
            raise RuntimeError("sink exploded")
        seen.append(("broken", event.value))

    pump.on(StatusEvent, broken)
    pump.on(StatusEvent, lambda e: seen.append(("ok", e.value)))
    bus.emit(StatusEvent("adb", "first"))
    bus.emit(StatusEvent("adb", "second"))
    asyncio.run(pump.tick())
    assert seen == [("ok", "first"), ("broken", "second"), ("ok", "second")]
    errors = ui_errors(bus)
    assert len(errors) == 1 and "sink exploded" in errors[0].text


def test_only_the_newest_progress_per_job_is_applied_and_logs_arrive_as_one_batch():
    pump, bus = make_pump()
    progress, batches, states = [], [], []
    pump.on(ProgressEvent, progress.append)
    pump.on(LOGS, batches.append)
    pump.on(JobStateEvent, states.append)
    for i in range(3):
        bus.emit(ProgressEvent("profile", "Xiaomi", i / 10))
        bus.emit(LogEvent(Level.INFO, f"line {i}"))
    bus.emit(ProgressEvent("info", "Đọc thông tin", 0.5))
    bus.emit(JobStateEvent("info", "Đọc thông tin", JobState.SUCCESS))
    asyncio.run(pump.tick())
    assert [(e.job, e.fraction) for e in progress] == [("profile", 0.2), ("info", 0.5)]
    assert len(batches) == 1 and [e.text for e in batches[0]] == ["line 0", "line 1", "line 2"]
    assert [s.state for s in states] == [JobState.SUCCESS]


def test_flush_updates_each_dirty_control_once_then_runs_after_flush_callbacks():
    pump, _bus = make_pump()
    control = FakeControl()
    calls = []

    async def async_callback():
        calls.append("async")

    pump.after_flush(lambda: calls.append("sync"))
    pump.after_flush(async_callback)
    pump.mark_dirty(control, None, control)
    asyncio.run(pump.flush())
    assert control.updates == 1 and calls == ["sync", "async"]
    asyncio.run(pump.flush())  # nothing dirty: no update, no callbacks
    assert control.updates == 1 and calls == ["sync", "async"]


def test_detached_controls_are_skipped_silently():
    pump, bus = make_pump()
    attached, detached = FakeControl(), DetachedControl()
    pump.mark_dirty(detached, attached)
    asyncio.run(pump.flush())
    assert attached.updates == 1 and detached.updates == 0
    assert ui_errors(bus) == []


def test_a_never_mounted_flet_control_is_skipped_while_mounted_ones_update():
    page, _session, conn = mount_page()
    mounted = ft.Text("trước")
    page.add(mounted)
    bus = EventBus()
    pump = UiPump(page, bus)
    mounted.value = "sau"
    pump.mark_dirty(ft.Text("chưa gắn vào trang"), mounted)
    asyncio.run(pump.flush())
    assert ui_errors(bus) == []
    assert conn.last_patch_ops() == [[Operation.Replace.value, 0, "value", "sau"]]


def test_a_control_removed_from_the_page_is_not_updated_any_more():
    page, _session, conn = mount_page()
    removed, kept = ft.Text("cũ"), ft.Text("giữ")
    column = ft.Column([removed, kept])
    page.add(column)
    column.controls.remove(removed)
    column.update()  # removed from the client; its old parent still exists, so .page still resolves
    sent = len(conn.sent)
    bus = EventBus()
    pump = UiPump(page, bus)
    removed.value = "không gửi"
    pump.mark_dirty(removed)
    asyncio.run(pump.flush())
    assert len(conn.sent) == sent and ui_errors(bus) == []


def test_a_failing_update_is_reported_and_the_other_controls_still_update():
    pump, bus = make_pump()
    broken, healthy = FakeControl(fail=True), FakeControl()
    pump.mark_dirty(broken, healthy)
    asyncio.run(pump.flush())
    assert healthy.updates == 1
    errors = ui_errors(bus)
    assert len(errors) == 1 and "client rejected the patch" in errors[0].text


def test_loop_survives_a_crashing_tick_and_stops_on_request():
    pump, bus = make_pump()
    pump.interval = 0.005
    seen = []
    original_drain = bus.drain
    crashes = [True]

    def flaky_drain(max_items=500):
        if crashes:
            crashes.pop()
            raise OSError("queue broke once")
        return original_drain(max_items)

    bus.drain = flaky_drain
    pump.on(StatusEvent, seen.append)

    async def scenario():
        pump.start()
        bus.emit(StatusEvent("driver", "ok"))
        for _ in range(200):
            if seen:
                break
            await asyncio.sleep(0.005)
        pump.stop()
        await asyncio.sleep(0.02)

    asyncio.run(scenario())
    assert [e.value for e in seen] == ["ok"]
    assert not pump._running
