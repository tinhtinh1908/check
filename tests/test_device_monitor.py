import time

from bull_tool.core.adb import AdbClient, AdbServer
from bull_tool.core.device_monitor import DeviceMonitor
from bull_tool.core.events import DevicesEvent, EventBus, StatusEvent
from tests.fake_adb_server import FakeAdbServer
from tests.helpers import reset_first_send, unused_port


def wait_for(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_monitor_publishes_devices_pauses_and_stops():
    fake = FakeAdbServer()
    fake.track_updates = ["SER123 device model:M transport_id:1\n"]
    fake.track_hold = True
    client = AdbClient(port=fake.port)
    bus = EventBus()
    monitor = DeviceMonitor(client, AdbServer(client), bus, reconnect_delay=0.1)
    received = []
    bus.add_listener(received.append)
    monitor.start()
    try:
        assert wait_for(lambda: any(isinstance(e, DevicesEvent) and e.devices for e in received))
        devices = next(e.devices for e in received if isinstance(e, DevicesEvent) and e.devices)
        assert devices[0].serial == "SER123" and devices[0].ready
        assert any(isinstance(e, StatusEvent) and e.value == "up" for e in received)

        monitor.pause()
        assert wait_for(lambda: any(isinstance(e, DevicesEvent) and not e.devices for e in received))
        tracks = fake.services.count("host:track-devices-l")
        time.sleep(0.5)
        assert fake.services.count("host:track-devices-l") == tracks  # no reconnect while paused

        monitor.resume()
        assert wait_for(lambda: fake.services.count("host:track-devices-l") > tracks)
    finally:
        monitor.stop()
        fake.close()
    assert monitor._thread is not None and not monitor._thread.is_alive()


def test_monitor_reconnects_after_each_track_connection_ends():
    fake = FakeAdbServer()
    fake.track_updates = ["SER123 device model:M transport_id:1\n"]  # server ends the stream after this update
    client = AdbClient(port=fake.port)
    bus = EventBus()
    received = []
    bus.add_listener(received.append)
    monitor = DeviceMonitor(client, AdbServer(client), bus, reconnect_delay=0.05)
    monitor.start()
    try:
        assert wait_for(lambda: sum(isinstance(e, StatusEvent) and e.value == "up" for e in received) >= 2)
        assert any(isinstance(e, StatusEvent) and e.value == "down" for e in received)
        assert fake.services.count("host:track-devices-l") >= 2
    finally:
        monitor.stop()
        fake.close()


def test_monitor_reports_why_adb_is_down_and_keeps_retrying():
    client = AdbClient(port=unused_port())
    bus = EventBus()
    received = []
    bus.add_listener(received.append)
    monitor = DeviceMonitor(client, AdbServer(client, adb_exe=None), bus, reconnect_delay=0.05)
    monitor.start()
    try:
        assert wait_for(lambda: sum(isinstance(e, StatusEvent) and e.value == "down" for e in received) >= 2)
        downs = [e for e in received if isinstance(e, StatusEvent) and e.value == "down"]
        assert downs[0].detail == "adb.exe is not available"
        assert not any(isinstance(e, StatusEvent) and e.value == "up" for e in received)
    finally:
        monitor.stop()


def test_paused_monitor_stays_quiet_until_resumed():
    client = AdbClient(port=unused_port())
    bus = EventBus()
    received = []
    bus.add_listener(received.append)
    monitor = DeviceMonitor(client, AdbServer(client, adb_exe=None), bus, reconnect_delay=0.05)
    monitor.pause()
    monitor.start()
    try:
        time.sleep(0.3)
        assert monitor.paused
        assert not any(isinstance(e, StatusEvent) for e in received)
        monitor.resume()
        assert wait_for(lambda: any(isinstance(e, StatusEvent) and e.value == "down" for e in received))
    finally:
        monitor.stop()


def test_monitor_survives_socket_error_and_reconnects(monkeypatch):
    fake = FakeAdbServer()
    fake.track_updates = ["SER123 device model:M transport_id:1\n"]
    reset_first_send(monkeypatch, ConnectionResetError(10054, "connection reset by peer"))
    client = AdbClient(port=fake.port)
    bus = EventBus()
    received = []
    bus.add_listener(received.append)
    monitor = DeviceMonitor(client, AdbServer(client), bus, reconnect_delay=0.05)
    monitor.start()
    try:
        assert wait_for(lambda: any(isinstance(e, DevicesEvent) and e.devices for e in received))
    finally:
        monitor.stop()
        fake.close()
