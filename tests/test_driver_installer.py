import pytest

from bull_tool.core.driver_installer import driver_store_root, extract_driver, install_driver, is_installed
from bull_tool.core.events import EventBus, Level, Logger
from bull_tool.core.payload import ResourceStore
from bull_tool.core.win32 import ElevationCancelled, ElevationError
from tests.helpers import zip_bytes

DRIVER_FILES = {
    "USB_DRIVER_XIAOMI/android_winusb.inf": b"; Android WinUsb driver installation.",
    "USB_DRIVER_XIAOMI/xiaomiwinusba64.cat": b"catalog",
    "USB_DRIVER_XIAOMI/amd64/WdfCoInstaller01009.dll": b"dll",
}


@pytest.fixture
def store(tmp_path):
    payload = tmp_path / "payload.zip"
    payload.write_bytes(zip_bytes(DRIVER_FILES))
    st = ResourceStore(open(payload, "rb"), str(payload))
    yield st
    st.close()


def make_driver_store(root, catalog):
    folder = root / "android_winusb.inf_amd64_0123456789abcdef"
    folder.mkdir(parents=True)
    (folder / catalog).write_bytes(b"x")


def test_is_installed_matches_xiaomi_catalog_only(tmp_path):
    google = tmp_path / "google"
    make_driver_store(google, "androidwinusba64.cat")
    assert not is_installed(google)
    xiaomi = tmp_path / "xiaomi"
    make_driver_store(xiaomi, "xiaomiwinusba64.cat")
    assert is_installed(xiaomi)
    assert not is_installed(tmp_path / "missing")


def test_extract_driver_is_idempotent(store, tmp_path):
    inf = extract_driver(store, tmp_path / "drv")
    assert inf == tmp_path / "drv" / "USB_DRIVER_XIAOMI" / "android_winusb.inf"
    assert inf.read_bytes() == DRIVER_FILES["USB_DRIVER_XIAOMI/android_winusb.inf"]
    mtime = inf.stat().st_mtime_ns
    extract_driver(store, tmp_path / "drv")
    assert inf.stat().st_mtime_ns == mtime  # verified, not rewritten


@pytest.mark.parametrize("code,reboot", [(0, False), (259, False), (3010, True)])
def test_install_success_codes(store, tmp_path, code, reboot):
    root = tmp_path / "store"
    calls = []

    def elevate(exe, params, cwd):
        calls.append((exe, params, cwd))
        make_driver_store(root, "xiaomiwinusba64.cat")
        return code

    result = install_driver(store, Logger(EventBus()), elevate=elevate, root=root, target=tmp_path / "drv")
    assert result.ok and result.reboot is reboot
    exe, params, _cwd = calls[0]
    assert exe.lower().endswith("pnputil.exe")
    assert params.startswith('/add-driver "') and params.endswith('android_winusb.inf" /install')


def test_install_cancelled_by_user(store, tmp_path):
    def elevate(exe, params, cwd):
        raise ElevationCancelled()

    bus = EventBus()
    result = install_driver(store, Logger(bus), elevate=elevate, root=tmp_path / "s", target=tmp_path / "drv")
    assert result.cancelled and not result.ok
    assert any(e.level == Level.WARN for e in bus.drain())


def test_install_failure_reports_manual_hint(store, tmp_path):
    bus = EventBus()
    result = install_driver(
        store, Logger(bus), elevate=lambda *a: 1, root=tmp_path / "s", target=tmp_path / "drv"
    )
    assert not result.ok and result.code == 1 and "mã 1" in result.message
    assert any("Device Manager" in e.text for e in bus.drain())


def test_elevation_error_is_a_failure_that_is_not_a_cancel(store, tmp_path):
    def broken(*_args):
        raise ElevationError("ShellExecuteEx failed (error 2)")

    bus = EventBus()
    result = install_driver(store, Logger(bus), elevate=broken, root=tmp_path / "s", target=tmp_path / "drv")
    assert not result.ok and not result.cancelled and result.code is None
    assert result.message == "ShellExecuteEx failed (error 2)"
    assert any(e.level == Level.ERROR for e in bus.drain())


def test_access_denied_exit_code_gets_the_admin_message(store, tmp_path):
    result = install_driver(
        store, Logger(EventBus()), elevate=lambda *args: 5, root=tmp_path / "s", target=tmp_path / "drv",
    )
    assert not result.ok and result.code == 5
    assert result.message == "Không đủ quyền quản trị (Admin)"


def test_zero_exit_without_catalog_is_still_a_failure_with_manual_hint(store, tmp_path):
    bus = EventBus()
    result = install_driver(
        store, Logger(bus), elevate=lambda *args: 0, root=tmp_path / "empty", target=tmp_path / "drv",
    )
    assert not result.ok
    assert any("Device Manager" in e.text for e in bus.drain())


def test_is_installed_reads_the_system_driver_store(tmp_path, monkeypatch):
    monkeypatch.setenv("SystemRoot", str(tmp_path))
    assert not is_installed()
    make_driver_store(driver_store_root(), "xiaomiwinusba64.cat")
    assert is_installed()


def test_extract_driver_repairs_a_modified_file(store, tmp_path):
    target = tmp_path / "drv"
    inf = extract_driver(store, target)
    inf.write_bytes(b"tampered")
    assert extract_driver(store, target) == inf
    assert inf.read_bytes() == DRIVER_FILES["USB_DRIVER_XIAOMI/android_winusb.inf"]
