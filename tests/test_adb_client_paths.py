import io
import os
import socket
import struct
import sys
import threading
import time
from pathlib import Path

import pytest

from bull_tool.core.adb import (
    AdbClient,
    AdbConnectionError,
    AdbError,
    AdbServer,
    Cancelled,
    DeviceGoneError,
    InstallError,
)
from tests.fake_adb_server import FakeAdbServer
from tests.helpers import reset_first_send, unused_port


@pytest.fixture
def fake():
    server = FakeAdbServer()
    yield server
    server.close()


@pytest.fixture
def client(fake):
    return AdbClient(port=fake.port)


def scripted_device_reply(monkeypatch, client, reply: bytes) -> None:
    """Next device service answers with ``reply`` and then ends, like a device that disappeared mid-command."""
    ours, theirs = socket.socketpair()
    theirs.sendall(reply)
    theirs.close()
    monkeypatch.setattr(client, "open_service", lambda *args, **kwargs: ours)


def test_features_of_unknown_serial_raise_adb_error(client):
    with pytest.raises(AdbError, match="not found"):
        client.features("NOPE")


def test_shell_v2_stream_cut_before_exit_packet_is_device_gone(monkeypatch, client):
    stdout_packet = struct.pack("<BI", 1, 3) + b"abc"
    scripted_device_reply(monkeypatch, client, stdout_packet)
    with pytest.raises(DeviceGoneError, match="exit status"):
        client.shell("SER123", "getprop", features=frozenset({"shell_v2"}))


def test_shell_v1_cut_before_marker_is_device_gone(monkeypatch, client):
    scripted_device_reply(monkeypatch, client, b"partial output\n")
    with pytest.raises(DeviceGoneError, match="exit status"):
        client.shell("SER123", "getprop", features=frozenset())


def test_shell_v1_normalizes_crlf_and_reads_the_exit_code(monkeypatch, client):
    scripted_device_reply(monkeypatch, client, b"line one\r\nline two\r\n__BULL_RC=7\r\n")
    result = client.shell("SER123", "false", features=frozenset())
    assert (result.stdout, result.stderr, result.exit_code) == ("line one\nline two\n", "", 7)


def test_shell_v1_unreadable_exit_status_counts_as_failure(monkeypatch, client):
    scripted_device_reply(monkeypatch, client, b"done\n__BULL_RC=\n")
    result = client.shell("SER123", "true", features=frozenset())
    assert result.exit_code == 1 and not result.ok


def test_legacy_install_failure_maps_the_code_and_removes_the_temp_file(client, fake):
    fake.features["SER123"] = "shell_v2"  # no "cmd" feature: push to /data/local/tmp, then pm install
    fake.shell_results["pm install /data/local/tmp/bull_a.apk"] = (
        "Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]\n",
        "",
        1,
    )
    data = b"apk" * 100
    with pytest.raises(InstallError) as exc:
        client.install("SER123", io.BytesIO(data), len(data), "a.apk")
    assert exc.value.code == "INSTALL_FAILED_USER_RESTRICTED"
    assert "shell,v2,raw:rm -f /data/local/tmp/bull_a.apk" in fake.services


def test_legacy_install_multiple_writes_each_split_through_pm(client, fake):
    fake.features["SER123"] = "shell_v2"
    base_write = "pm install-write -S 1000 77 0_base.apk /data/local/tmp/bull_0_base.apk"
    config_write = "pm install-write -S 500 77 1_config.hdpi.apk /data/local/tmp/bull_1_config.hdpi.apk"
    fake.shell_results["pm install-create -S 1500"] = ("Success: created install session [77]\n", "", 0)
    fake.shell_results[base_write] = ("Success: streamed 1000 bytes\n", "", 0)
    fake.shell_results[config_write] = ("Success: streamed 500 bytes\n", "", 0)
    fake.shell_results["pm install-commit 77"] = ("Success\n", "", 0)
    parts = [("base.apk", io.BytesIO(b"a" * 1000), 1000), ("config.hdpi.apk", io.BytesIO(b"b" * 500), 500)]
    progress = []
    result = client.install_multiple("SER123", parts, on_progress=lambda done, total: progress.append((done, total)))
    assert result == "Success"
    assert fake.pushed["/data/local/tmp/bull_0_base.apk"] == b"a" * 1000
    assert fake.pushed["/data/local/tmp/bull_1_config.hdpi.apk"] == b"b" * 500
    assert progress[-1] == (1500, 1500)
    assert "shell,v2,raw:rm -f /data/local/tmp/bull_0_base.apk" in fake.services


def test_legacy_install_multiple_reports_progress_while_a_part_streams(client, fake):
    fake.features["SER123"] = "shell_v2"
    fake.shell_results["pm install-create -S 200000"] = ("Success: created install session [77]\n", "", 0)
    write = "pm install-write -S 200000 77 0_big.apk /data/local/tmp/bull_0_big.apk"
    fake.shell_results[write] = ("Success: streamed 200000 bytes\n", "", 0)
    fake.shell_results["pm install-commit 77"] = ("Success\n", "", 0)
    data = os.urandom(200_000)
    progress = []
    client.install_multiple(
        "SER123", [("big.apk", io.BytesIO(data), len(data))], on_progress=lambda done, total: progress.append(done),
    )
    assert any(0 < done < len(data) for done in progress)


def test_legacy_install_push_failure_still_removes_the_temp_file(client, fake):
    fake.features["SER123"] = "shell_v2"
    fake.push_fail = "couldn't create file: No space left on device"
    data = b"apk" * 100
    with pytest.raises(AdbError):
        client.install("SER123", io.BytesIO(data), len(data), "a.apk")
    assert "shell,v2,raw:rm -f /data/local/tmp/bull_a.apk" in fake.services


def test_legacy_install_multiple_push_failure_removes_the_temp_file(client, fake):
    fake.features["SER123"] = "shell_v2"
    fake.shell_results["pm install-create -S 1000"] = ("Success: created install session [77]\n", "", 0)
    fake.push_fail = "couldn't create file: No space left on device"
    with pytest.raises(AdbError):
        client.install_multiple("SER123", [("base.apk", io.BytesIO(b"a" * 1000), 1000)])
    assert "shell,v2,raw:rm -f /data/local/tmp/bull_0_base.apk" in fake.services


def test_stop_while_the_phone_shows_its_install_prompt_cancels_the_commit_and_abandons(client, fake):
    fake.commit_hold = True  # nobody answers the install confirmation on the phone
    cancel, stopped_at = threading.Event(), []

    def press_stop_once_the_commit_waits():
        deadline = time.monotonic() + 5
        while "exec:cmd package install-commit 77" not in fake.services and time.monotonic() < deadline:
            time.sleep(0.01)
        stopped_at.append(time.monotonic())
        cancel.set()

    threading.Thread(target=press_stop_once_the_commit_waits, daemon=True).start()
    with pytest.raises(Cancelled):
        client.install_multiple("SER123", [("base.apk", io.BytesIO(b"a" * 1000), 1000)], cancel=cancel, timeout=10.0)
    assert time.monotonic() - stopped_at[0] < 2.0
    assert "exec:cmd package install-abandon 77" in fake.services


def test_socket_reset_while_sending_is_reported_as_adb_error(monkeypatch, client):
    reset_first_send(monkeypatch, ConnectionResetError(10054, "connection reset by peer"))
    with pytest.raises(AdbError):
        client.server_version()


def test_start_fails_with_connection_error_when_adb_cannot_execute(tmp_path):
    adb = tmp_path / "adb.exe"
    adb.write_bytes(b"this file is not a program")
    server = AdbServer(AdbClient(port=unused_port()), adb_exe=adb)
    with pytest.raises(AdbConnectionError, match="cannot start adb server"):
        server.ensure_running(timeout=2.0)
    assert not server.owned


def test_start_gives_up_when_the_server_never_answers():
    # The interpreter exits at once on "start-server" (no such script), so nothing ever listens on the port.
    server = AdbServer(AdbClient(port=unused_port()), adb_exe=Path(sys.executable))
    with pytest.raises(AdbConnectionError, match="did not start"):
        server.ensure_running(timeout=1.0)
    assert server.owned  # our start-server ran: a daemon that answers later is still ours to stop on exit


def test_start_refuses_when_adb_exe_is_missing(tmp_path):
    server = AdbServer(AdbClient(port=unused_port()), adb_exe=tmp_path / "gone" / "adb.exe")
    with pytest.raises(AdbConnectionError, match="not available"):
        server.ensure_running()


def test_shutdown_stops_a_server_this_app_started(client, fake):
    server = AdbServer(client)
    server.owned = True
    server.shutdown()
    assert fake.killed and not server.owned
