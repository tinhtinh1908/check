"""AdbServer once the app begins to exit: no adb is started any more, and a start already in progress is
stopped by ``shutdown``. ``adb start-server`` is replaced by an in-process fake daemon."""

import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from bull_tool.core.adb import AdbClient, AdbConnectionError, AdbServer
from bull_tool.core.adb import server as server_module
from tests.fake_adb_server import FakeAdbServer
from tests.helpers import unused_port


@pytest.fixture
def adb(monkeypatch):
    """``adb start-server`` brings up a fake daemon and points ``adb.client`` at it; every start is recorded."""
    adb = SimpleNamespace(client=AdbClient(port=unused_port()), started=[])

    def start_server(args, **kwargs):
        fake = FakeAdbServer()
        adb.started.append(fake)
        adb.client.port = fake.port

    monkeypatch.setattr(server_module.subprocess, "run", start_server)
    yield adb
    for fake in adb.started:
        fake.close()


def our_server(adb) -> AdbServer:
    return AdbServer(adb.client, adb_exe=Path(sys.executable))  # any existing file passes the adb.exe check


def test_no_adb_is_started_after_shutdown(adb):
    server = our_server(adb)
    server.shutdown()
    assert server.closed
    with pytest.raises(AdbConnectionError, match="shutting down"):
        server.ensure_running()
    assert adb.started == [] and not server.owned


def test_close_does_not_wait_for_a_start_in_progress_and_shutdown_stops_that_server(adb, monkeypatch):
    server = our_server(adb)
    start_server, inside, release = server_module.subprocess.run, threading.Event(), threading.Event()

    def slow_start(args, **kwargs):  # the start holds the server lock until released
        inside.set()
        release.wait(5)
        start_server(args, **kwargs)

    monkeypatch.setattr(server_module.subprocess, "run", slow_start)
    starter = threading.Thread(target=server.ensure_running)
    starter.start()
    assert inside.wait(5)
    began = time.monotonic()
    server.close()  # the UI loop closing the window must never block on the server lock
    assert time.monotonic() - began < 1.0 and server.closed
    release.set()
    server.shutdown()  # waits for the start in progress, then stops the server it brought up
    starter.join(5)
    assert len(adb.started) == 1 and adb.started[0].killed and not server.owned
    with pytest.raises(AdbConnectionError, match="shutting down"):
        server.ensure_running()
    assert len(adb.started) == 1


def test_a_daemon_that_answers_only_after_the_start_gave_up_is_still_stopped_on_shutdown(monkeypatch):
    client, late = AdbClient(port=unused_port()), []
    monkeypatch.setattr(server_module.subprocess, "run", lambda args, **kwargs: late.append(FakeAdbServer()))
    server = AdbServer(client, adb_exe=Path(sys.executable))
    with pytest.raises(AdbConnectionError, match="did not start"):
        server.ensure_running(timeout=0.5)
    assert server.owned  # our start-server ran: whatever answers on the port later is our daemon
    client.port = late[0].port  # the daemon finally answers
    try:
        server.shutdown()
        assert late[0].killed and not server.owned
    finally:
        late[0].close()


def test_kill_still_stops_the_server_after_close():
    fake = FakeAdbServer()
    server = AdbServer(AdbClient(port=fake.port))
    server.close()
    try:
        server.kill()  # the connection fixer and the platform-tools self-heal still release adb this way
        assert fake.killed
    finally:
        fake.close()
