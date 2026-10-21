"""JobRunner end-to-end against the scripted adb server (real AdbClient, real ResourceStore)."""

import os
import threading

import pytest

from bull_tool.core.adb import AdbClient
from bull_tool.core.events import DeviceInfoEvent, EventBus, JobState, JobStateEvent, LogEvent, ProgressEvent
from bull_tool.core.job_runner import CORRUPT_HINT, INSTALL_HINTS, JobRunner, install_hint
from bull_tool.core.payload import CorruptMemberError, ResourceStore
from bull_tool.core.profiles import (
    DEV_OFF,
    GBOARD_IME,
    IME_ENABLE,
    Disable,
    Install,
    InstallMulti,
    Profile,
    Push,
    Uninstall,
)
from tests.fake_adb_server import FakeAdbServer
from tests.helpers import zip_bytes

APKS = {name: os.urandom(size) for name, size in {
    "APK/x.apk": 300_000, "APK/y.apk": 120_000, "APK/s1.apk": 90_000, "APK/s2.apk": 10_000,
}.items()}

PROFILE = Profile(
    id="test",
    name="Test",
    subtitle="",
    brands=("test",),
    accent="#fff",
    steps=(
        Uninstall("com.a"),
        Uninstall("com.zzz"),
        Disable("com.b"),
        Install("APK/x.apk"),
        Push("APK/y.apk"),
        InstallMulti(("APK/s1.apk", "APK/s2.apk"), "Split"),
        IME_ENABLE,
        DEV_OFF,
    ),
)


def default_shell(cmd: str):
    answers = {
        "pm list packages --user 0": ("package:com.a\npackage:com.b\npackage:com.c\n", "", 0),
        "pm list packages -d --user 0": ("", "", 0),
        "pm uninstall -k --user 0 com.a": ("Success\n", "", 0),
        "pm disable-user --user 0 com.b": ("Package com.b new state: disabled-user\n", "", 0),
        "pm path com.google.android.inputmethod.latin": ("", "", 1),
    }
    return answers.get(cmd, ("", "", 0))


@pytest.fixture
def env(tmp_path):
    fake = FakeAdbServer()
    fake.shell_hook = default_shell
    fake.drop_on.add(DEV_OFF.cmd)
    payload = tmp_path / "payload.zip"
    payload.write_bytes(zip_bytes(APKS))
    store = ResourceStore(open(payload, "rb"), str(payload))
    bus = EventBus()
    runner = JobRunner(AdbClient(port=fake.port), store, bus)
    yield fake, runner, bus
    store.close()
    fake.close()


def test_profile_run_counts_transfers_and_progress(env):
    fake, runner, bus = env
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert summary.ok, summary.failures
    assert (summary.removed, summary.disabled, summary.installed, summary.pushed) == (1, 1, 2, 1)
    assert summary.configured == 1 and summary.skipped == 2 and summary.disconnected_ok
    assert fake.installed == [APKS["APK/x.apk"]]
    assert fake.pushed["/sdcard/Download/y.apk"] == APKS["APK/y.apk"]
    assert fake.session_parts["77"] == [("0_s1.apk", APKS["APK/s1.apk"]), ("1_s2.apk", APKS["APK/s2.apk"])]
    assert not any("com.zzz" in s for s in fake.services)  # skipped without a device round-trip

    events = bus.drain(max_items=10_000)
    fractions = [e.fraction for e in events if isinstance(e, ProgressEvent) and e.fraction is not None]
    assert fractions == sorted(fractions) and fractions[-1] == 1.0
    states = [e.state for e in events if isinstance(e, JobStateEvent)]
    assert states == [JobState.RUNNING, JobState.SUCCESS]
    texts = [e.text for e in events if isinstance(e, LogEvent)]
    assert any("Bỏ qua com.zzz" in t for t in texts)
    assert any("Bỏ qua: Bật bàn phím Gboard" in t for t in texts)


def test_cancel_stops_before_next_step(env):
    fake, runner, bus = env
    cancel = threading.Event()
    bus.add_listener(lambda e: isinstance(e, LogEvent) and "Đã gỡ com.a" in e.text and cancel.set())
    summary = runner.run_profile("SER123", PROFILE, cancel)
    assert summary.cancelled and summary.removed == 1
    assert not any(s.startswith("shell,v2,raw:pm disable-user") for s in fake.services)
    assert [e.state for e in bus.drain(10_000) if isinstance(e, JobStateEvent)][-1] == JobState.CANCELLED


def test_install_failure_is_reported_with_hint_and_run_continues(env):
    fake, runner, _bus = env
    fake.install_reply = "Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]\n"
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert summary.failed == 1 and not summary.aborted
    assert "Cài đặt qua USB" in summary.failures[0].hint
    assert summary.pushed == 1  # later steps still ran


def test_device_lost_mid_run_aborts(env):
    fake, runner, bus = env
    fake.drop_on.add("pm disable-user --user 0 com.b")

    def unplug():
        fake.devices_text = ""
        fake.features.pop("SER123", None)

    fake.on_drop = unplug
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert summary.aborted.startswith("Mất kết nối")
    assert summary.installed == 0
    assert [e.state for e in bus.drain(10_000) if isinstance(e, JobStateEvent)][-1] == JobState.FAILED


def test_dropped_stream_while_phone_still_connected_fails_only_that_step(env):
    fake, runner, _bus = env
    fake.drop_on.add("pm disable-user --user 0 com.b")  # stream closes, but the phone stays listed
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert not summary.aborted
    assert [f.label for f in summary.failures] == ["Tắt com.b"]
    assert summary.installed == 2 and summary.pushed == 1  # later steps still ran, like the batch file


def test_final_adb_off_step_is_not_success_when_phone_already_gone(env):
    fake, runner, _bus = env
    original = fake._shell_result

    def unplug_before_last_step(cmd):
        if cmd == "pm path com.google.android.inputmethod.latin":
            fake.devices_text = ""  # phone unplugged right before DEV_OFF
        return original(cmd)

    fake.shell_hook = None
    fake._shell_result = unplug_before_last_step
    fake.shell_results.update({
        "pm list packages --user 0": ("package:com.a\npackage:com.b\n", "", 0),
        "pm uninstall -k --user 0 com.a": ("Success\n", "", 0),
        "pm disable-user --user 0 com.b": ("Package com.b new state: disabled-user\n", "", 0),
        "pm path com.google.android.inputmethod.latin": ("", "", 1),
    })
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert summary.aborted.startswith("Mất kết nối") and not summary.disconnected_ok


def test_unknown_package_list_runs_every_command(env):
    fake, runner, _bus = env

    def shell(cmd):
        if cmd.startswith("pm list packages"):
            return ("", "", 0)
        if cmd == "pm uninstall -k --user 0 com.zzz":
            return ("Failure [not installed for 0]\n", "", 1)
        return default_shell(cmd)

    fake.shell_hook = shell
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert any("pm uninstall -k --user 0 com.zzz" in s for s in fake.services)
    assert summary.failed == 0 and summary.removed == 1


def test_read_info_emits_device_info(env):
    fake, runner, bus = env

    def shell(cmd):
        if cmd == "getprop":
            return ("[ro.product.brand]: [OPPO]\n[ro.product.model]: [CPH2581]\n"
                    "[ro.build.version.release]: [14]\n[ro.build.version.oplusrom]: [V14.0.0]\n", "", 0)
        return ("", "", 0)

    fake.shell_hook = shell
    info = runner.read_info("SER123")
    assert info is not None and info.rom == "ColorOS 14.0.0" and info.display_name == "CPH2581"
    events = bus.drain()
    assert any(isinstance(e, DeviceInfoEvent) and e.info.brand == "OPPO" for e in events)
    assert runner.read_info("MISSING") is None


def corrupted(raw: bytes, member: bytes) -> bytes:
    """Flip one byte inside a stored member so that its CRC-32 no longer matches."""
    index = raw.find(member[1000:1032])
    assert index > 0
    damaged = bytearray(raw)
    damaged[index] ^= 0xFF
    return bytes(damaged)


def run_over_damaged_payload(fake, bus, tmp_path, member, profile):
    payload = tmp_path / "damaged.zip"
    payload.write_bytes(corrupted(zip_bytes(APKS), APKS[member]))
    handle = open(payload, "rb")
    store = ResourceStore(handle, str(payload))
    try:
        runner = JobRunner(AdbClient(port=fake.port), store, bus)
        return runner.run_profile("SER123", profile, threading.Event())
    finally:
        store.close()
        handle.close()  # ResourceStore.close() leaves the caller's file object open


def test_requires_pkg_present_runs_the_step(env):
    fake, runner, bus = env

    def shell(cmd):
        if cmd == "pm path com.google.android.inputmethod.latin":
            return ("package:/system/app/Gboard/Gboard.apk\n", "", 0)
        return default_shell(cmd)

    fake.shell_hook = shell
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert summary.ok, summary.failures
    assert summary.configured == 2 and summary.skipped == 1  # Gboard enable + debugging off; only com.zzz skipped
    assert f"shell,v2,raw:ime enable {GBOARD_IME}" in fake.services
    assert "Bật bàn phím Gboard" in [e.text for e in bus.drain(10_000) if isinstance(e, LogEvent)]


def test_preflight_falls_back_to_the_full_package_list_when_user_listing_is_empty(env):
    fake, runner, _bus = env

    def shell(cmd):
        if cmd == "pm list packages --user 0":
            return ("", "", 0)
        if cmd == "pm list packages":
            return ("package:com.a\n", "", 0)
        return default_shell(cmd)

    fake.shell_hook = shell
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert summary.removed == 1 and summary.failed == 0
    assert not any("com.zzz" in s for s in fake.services)  # missing from the fallback list, so skipped


def test_push_failure_is_recorded_and_run_continues(env):
    fake, runner, _bus = env
    fake.push_fail = "couldn't create file: Read-only file system"
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert [f.label for f in summary.failures] == ["Chép y.apk"]
    assert "Read-only" in summary.failures[0].reason
    assert summary.pushed == 0 and summary.installed == 2 and not summary.aborted
    assert "/sdcard/Download/y.apk" not in fake.pushed


def test_uninstall_failure_is_recorded_and_run_continues(env):
    fake, runner, _bus = env

    def shell(cmd):
        if cmd == "pm uninstall -k --user 0 com.a":
            return ("Failure [DELETE_FAILED_INTERNAL_ERROR]\n", "", 1)
        return default_shell(cmd)

    fake.shell_hook = shell
    summary = runner.run_profile("SER123", PROFILE, threading.Event())
    assert summary.removed == 0 and not summary.aborted
    assert [f.label for f in summary.failures] == ["Gỡ com.a"]
    assert "DELETE_FAILED_INTERNAL_ERROR" in summary.failures[0].reason
    assert summary.installed == 2  # later steps still ran


def test_cancel_set_before_start_runs_no_steps(env):
    fake, runner, bus = env
    cancel = threading.Event()
    cancel.set()
    summary = runner.run_profile("SER123", PROFILE, cancel)
    assert summary.cancelled and summary.removed == 0 and summary.installed == 0 and summary.pushed == 0
    assert not any(s.startswith("shell,v2,raw:pm uninstall") for s in fake.services)
    assert [e.state for e in bus.drain(10_000) if isinstance(e, JobStateEvent)][-1] == JobState.CANCELLED


def test_unknown_device_aborts_with_failed_state(env):
    _fake, runner, bus = env
    summary = runner.run_profile("MISSING", PROFILE, threading.Event())
    assert summary.aborted and "không tìm thấy điện thoại" in summary.aborted
    assert summary.removed == 0 and not summary.ok
    assert [e.state for e in bus.drain(10_000) if isinstance(e, JobStateEvent)][-1] == JobState.FAILED


def test_corrupt_apk_is_reported_with_hint_and_run_continues(env, tmp_path):
    fake, _runner, bus = env
    summary = run_over_damaged_payload(fake, bus, tmp_path, "APK/x.apk", PROFILE)
    assert [f.hint for f in summary.failures] == [CORRUPT_HINT]
    assert summary.installed == 1 and summary.pushed == 1 and not summary.aborted
    assert fake.installed == []  # the device never received the damaged bytes


def test_corrupt_split_part_abandons_the_install_session(env, tmp_path):
    fake, _runner, bus = env
    summary = run_over_damaged_payload(fake, bus, tmp_path, "APK/s1.apk", PROFILE)
    assert [f.hint for f in summary.failures] == [CORRUPT_HINT]
    assert summary.installed == 1 and summary.pushed == 1 and not summary.aborted
    assert fake.installed == [APKS["APK/x.apk"]]
    assert "exec:cmd package install-abandon 77" in fake.services


def test_store_reporting_a_corrupt_member_gets_the_corrupt_hint(env, monkeypatch):
    _fake, runner, _bus = env
    profile = Profile(id="t", name="T", subtitle="", brands=(), accent="", steps=(Install("APK/x.apk"),))

    def refuse(name):
        raise CorruptMemberError(name, "CRC mismatch")

    monkeypatch.setattr(runner.store, "open", refuse)
    summary = runner.run_profile("SER123", profile, threading.Event())
    assert [f.hint for f in summary.failures] == [CORRUPT_HINT]
    assert not summary.aborted


def test_empty_install_reply_has_a_visible_reason(env):
    fake, runner, _bus = env
    fake.install_reply = ""
    profile = Profile(id="t", name="T", subtitle="", brands=(), accent="", steps=(Install("APK/x.apk"),))
    summary = runner.run_profile("SER123", profile, threading.Event())
    assert summary.failed == 1
    assert summary.failures[0].reason.strip()


def test_missing_payload_member_ends_the_job_in_failed_state(env):
    _fake, runner, bus = env
    profile = Profile(id="t", name="T", subtitle="", brands=(), accent="", steps=(Install("APK/missing.apk"),))
    summary = runner.run_profile("SER123", profile, threading.Event())
    assert summary.aborted
    assert [e.state for e in bus.drain(10_000) if isinstance(e, JobStateEvent)][-1] == JobState.FAILED


@pytest.mark.parametrize("code", sorted(INSTALL_HINTS))
def test_each_known_install_code_has_a_hint(code):
    assert install_hint(code) == INSTALL_HINTS[code] != ""


def test_install_hint_covers_parse_failures_and_unknown_codes():
    assert install_hint("INSTALL_PARSE_FAILED_NO_CERTIFICATES") == "File APK bị hỏng hoặc không hợp lệ."
    assert install_hint("INSTALL_FAILED_SOMETHING_NEW") == ""
