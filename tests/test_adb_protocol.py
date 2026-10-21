import hashlib
import io
import os
import socket
import threading

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
from bull_tool.core.adb.client import parse_devices
from tests.fake_adb_server import FakeAdbServer


@pytest.fixture
def fake():
    server = FakeAdbServer()
    yield server
    server.close()


@pytest.fixture
def client(fake):
    return AdbClient(port=fake.port)


def _unused_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def test_server_version(client):
    assert client.server_version() == 41


def test_devices_parse_states(client, fake):
    fake.devices_text = (
        "SER123          device product:p model:Redmi_13 device:d transport_id:3\n"
        "ABC123          unauthorized usb:1-1 transport_id:4\n"
    )
    devices = client.devices()
    assert [d.serial for d in devices] == ["SER123", "ABC123"]
    assert devices[0].ready and devices[0].model == "Redmi_13" and devices[0].transport_id == "3"
    assert devices[1].state == "unauthorized" and not devices[1].ready


def test_parse_devices_ignores_banner_lines():
    assert parse_devices("* daemon started successfully\nList of devices attached\n\n") == []


def test_track_devices_streams_updates(client, fake):
    fake.track_updates = ["", "SER123 device model:X transport_id:1\n"]
    updates = list(client.track_devices())
    assert updates[0] == []
    assert updates[1][0].serial == "SER123" and updates[1][0].model == "X"


def test_track_devices_close_from_other_thread(client, fake):
    fake.track_updates = ["SER123 device transport_id:1\n"]
    fake.track_hold = True
    tracker = client.track_devices()
    first_update = threading.Event()
    seen = []

    def consume():
        for update in tracker:
            seen.append(update)
            first_update.set()

    worker = threading.Thread(target=consume)
    worker.start()
    assert first_update.wait(timeout=5)
    tracker.close()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert seen[0][0].serial == "SER123"


def test_features(client):
    assert {"cmd", "shell_v2"} <= client.features("SER123")


def test_unknown_device_is_device_gone(client):
    with pytest.raises(DeviceGoneError):
        client.shell("NOPE", "echo hi", features=frozenset({"shell_v2"}))


def test_shell_v2_exit_code_and_stderr(client, fake):
    fake.shell_results["getprop ro.product.model"] = ("Redmi\n", "", 0)
    fake.shell_results["false"] = ("", "boom\n", 1)
    result = client.shell("SER123", "getprop ro.product.model")
    assert result.ok and result.stdout == "Redmi\n"
    failed = client.shell("SER123", "false")
    assert failed.exit_code == 1 and failed.stderr == "boom\n" and failed.output == "boom"


def test_shell_v1_fallback_parses_marker(client, fake):
    fake.features["SER123"] = "cmd"
    fake.shell_results["pm path x"] = ("package:/data/app/x.apk\n", "", 0)
    fake.shell_results["exit 3"] = ("", "", 3)
    assert client.shell("SER123", "pm path x").stdout.strip() == "package:/data/app/x.apk"
    assert client.shell("SER123", "exit 3").exit_code == 3


def test_push_integrity_progress_and_mode(client, fake):
    data = os.urandom(300_000)
    progress = []
    client.push(
        "SER123", io.BytesIO(data), len(data), "/sdcard/Download/a.apk",
        on_progress=lambda done, total: progress.append((done, total)),
    )
    assert hashlib.sha256(fake.pushed["/sdcard/Download/a.apk"]).digest() == hashlib.sha256(data).digest()
    assert max(fake.data_chunk_sizes) <= 64 * 1024
    assert progress[-1] == (len(data), len(data))
    assert all(a[0] < b[0] for a, b in zip(progress, progress[1:], strict=False))
    assert fake.push_modes["/sdcard/Download/a.apk"] == 0o100644


def test_push_failure_message(client, fake):
    fake.push_fail = "couldn't create file: Read-only file system"
    with pytest.raises(AdbError, match="Read-only"):
        client.push("SER123", io.BytesIO(b"x" * 10), 10, "/system/x")


def test_push_source_shorter_than_declared_size(client):
    with pytest.raises(AdbError, match="source ended early"):
        client.push("SER123", io.BytesIO(b"x" * 10), 20, "/sdcard/x")


def test_install_streams_bytes(client, fake):
    data = os.urandom(200_000)
    progress = []
    out = client.install(
        "SER123", io.BytesIO(data), len(data), "a.apk", on_progress=lambda d, t: progress.append(d)
    )
    assert out == "Success" and fake.installed == [data]
    assert "exec:cmd package install -S 200000" in fake.services
    assert progress[-1] == len(data)


def test_install_failure_code(client, fake):
    fake.install_reply = "Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]\n"
    with pytest.raises(InstallError) as exc:
        client.install("SER123", io.BytesIO(b"x" * 100), 100, "a.apk")
    assert exc.value.code == "INSTALL_FAILED_USER_RESTRICTED"


def test_install_legacy_path_without_cmd(client, fake):
    fake.features["SER123"] = "shell_v2"
    fake.shell_results["pm install /data/local/tmp/bull_a.apk"] = ("Success\n", "", 0)
    data = b"apk" * 1000
    client.install("SER123", io.BytesIO(data), len(data), "a.apk")
    assert fake.pushed["/data/local/tmp/bull_a.apk"] == data
    assert any(s.startswith("shell,v2,raw:rm -f /data/local/tmp/bull_a.apk") for s in fake.services)


def test_install_multiple_session(client, fake):
    parts = [("base.apk", io.BytesIO(b"a" * 1000), 1000), ("config.hdpi.apk", io.BytesIO(b"b" * 500), 500)]
    progress = []
    client.install_multiple("SER123", parts, on_progress=lambda d, t: progress.append((d, t)))
    assert fake.session_parts["77"] == [("0_base.apk", b"a" * 1000), ("1_config.hdpi.apk", b"b" * 500)]
    assert progress[-1] == (1500, 1500)
    assert any(s.startswith("exec:cmd package install-create -S 1500") for s in fake.services)
    assert any(s.startswith("exec:cmd package install-commit 77") for s in fake.services)


def test_install_multiple_abandons_on_failure(client, fake):
    fake.commit_reply = "Failure [INSTALL_FAILED_INVALID_APK: Split null was defined multiple times]\n"
    parts = [("base.apk", io.BytesIO(b"a" * 10), 10)]
    with pytest.raises(InstallError) as exc:
        client.install_multiple("SER123", parts)
    assert exc.value.code == "INSTALL_FAILED_INVALID_APK"
    assert any(s.startswith("exec:cmd package install-abandon 77") for s in fake.services)


def test_cancel_during_push(client, fake):
    cancel = threading.Event()
    data = os.urandom(1_000_000)

    def on_progress(done, _total):
        if done >= 200_000:
            cancel.set()

    with pytest.raises(Cancelled):
        client.push(
            "SER123", io.BytesIO(data), len(data), "/sdcard/x", on_progress=on_progress, cancel=cancel
        )
    assert "/sdcard/x" not in fake.pushed


def test_connection_error_when_no_server():
    with pytest.raises(AdbConnectionError):
        AdbClient(port=_unused_port()).server_version()


def test_server_reuses_running_server_and_only_kills_when_owned(client, fake):
    server = AdbServer(client, adb_exe=None)
    assert server.ensure_running() == 41
    assert not server.owned
    server.shutdown()
    assert not fake.killed
    server.kill()
    assert fake.killed


def test_server_without_adb_exe_raises():
    server = AdbServer(AdbClient(port=_unused_port()), adb_exe=None)
    with pytest.raises(AdbConnectionError):
        server.ensure_running()
