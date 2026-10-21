import threading

from bull_tool.core.events import EventBus, JobState, JobStateEvent, Level, LogEvent, Logger, Progress


def test_emit_and_drain_preserve_order_and_limit():
    bus = EventBus()
    log = Logger(bus, "job")
    for i in range(10):
        log.info(f"line {i}")
    first = bus.drain(max_items=4)
    rest = bus.drain()
    assert [e.text for e in first] == [f"line {i}" for i in range(4)]
    assert len(rest) == 6 and all(isinstance(e, LogEvent) and e.job == "job" for e in rest)
    assert bus.drain() == []


def test_listener_errors_do_not_break_emit():
    bus = EventBus()
    received = []
    bus.add_listener(lambda e: (_ for _ in ()).throw(RuntimeError("broken")))
    bus.add_listener(received.append)
    Logger(bus).warn("still delivered")
    assert received[0].level == Level.WARN
    assert len(bus.drain()) == 1


def test_concurrent_emitters():
    bus = EventBus()

    def worker():
        log = Logger(bus)
        for _ in range(1000):
            log.ok("x")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    total = 0
    while batch := bus.drain(max_items=700):
        total += len(batch)
    assert total == 4000


def test_progress_throttle_force_and_clamp():
    bus = EventBus()
    progress = Progress(bus, "job", "Title", min_interval=60.0)
    progress.update(0.1, "a", force=True)
    progress.update(0.2, "b")  # throttled
    progress.update(1.7, "c", force=True)  # clamped
    progress.update(None, "indeterminate", force=True)
    progress.state(JobState.SUCCESS, summary={"ok": 1})
    events = bus.drain()
    fractions = [e.fraction for e in events if not isinstance(e, JobStateEvent)]
    assert fractions == [0.1, 1.0, None]
    assert isinstance(events[-1], JobStateEvent) and events[-1].state == JobState.SUCCESS
