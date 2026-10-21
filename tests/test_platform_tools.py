import os

import pytest

from bull_tool.core import platform_tools
from bull_tool.core.events import EventBus, Level, Logger
from bull_tool.core.payload import PLATFORM_TOOLS_ZIP, PayloadError, ResourceStore
from bull_tool.core.platform_tools import ensure_platform_tools
from tests.helpers import zip_bytes

FILES = {
    "adb.exe": os.urandom(5000),
    "AdbWinApi.dll": os.urandom(3000),
    "source.properties": b"Pkg.UserSrc=false\nPkg.Revision=36.0.2\n",
}


def make_store(tmp_path, files):
    inner = zip_bytes({f"platform-tools/{name}": data for name, data in files.items()})
    outer = tmp_path / "payload.zip"
    outer.write_bytes(zip_bytes({PLATFORM_TOOLS_ZIP: inner}))
    return ResourceStore(open(outer, "rb"), str(outer))


def test_extract_then_noop_then_self_heal(tmp_path):
    store = make_store(tmp_path, FILES)
    bus = EventBus()
    log = Logger(bus, "boot")
    target = tmp_path / "tools"

    first = ensure_platform_tools(store, log, target=target)
    assert first.revision == "36.0.2"
    assert sorted(first.extracted) == sorted(FILES) and first.repaired == []
    assert (target / "adb.exe").read_bytes() == FILES["adb.exe"]

    second = ensure_platform_tools(store, log, target=target)
    assert second.extracted == [] and second.repaired == []

    corrupted = bytearray((target / "adb.exe").read_bytes())
    corrupted[100] ^= 0xFF
    (target / "adb.exe").write_bytes(bytes(corrupted))
    (target / "AdbWinApi.dll.tmp").write_bytes(b"stale")
    bus.drain()

    third = ensure_platform_tools(store, log, target=target)
    assert third.repaired == ["adb.exe"]
    assert (target / "adb.exe").read_bytes() == FILES["adb.exe"]
    assert not (target / "AdbWinApi.dll.tmp").exists()
    warnings = [e for e in bus.drain() if e.level == Level.WARN]
    assert warnings and "adb.exe" in warnings[0].text
    store.close()


def test_progress_reaches_one(tmp_path):
    store = make_store(tmp_path, FILES)
    seen = []
    ensure_platform_tools(
        store, Logger(EventBus()), on_progress=lambda f, n: seen.append(f), target=tmp_path / "t"
    )
    assert seen[-1] == 1.0 and len(seen) == len(FILES)
    store.close()


def test_missing_adb_is_an_error(tmp_path):
    store = make_store(tmp_path, {"fastboot.exe": b"x"})
    with pytest.raises(PayloadError):
        ensure_platform_tools(store, Logger(EventBus()), target=tmp_path / "t")
    store.close()


def test_locked_adb_triggers_one_release_and_a_retry(tmp_path, monkeypatch):
    store = make_store(tmp_path, FILES)
    real_extract = platform_tools.extract_verified
    attempts = {"n": 0}

    def locked_once(zf, info, dest, on_bytes=None):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise PermissionError(13, "adb.exe is in use")
        return real_extract(zf, info, dest, on_bytes)

    monkeypatch.setattr(platform_tools, "extract_verified", locked_once)
    released = []
    result = ensure_platform_tools(
        store, Logger(EventBus()), release_lock=lambda: released.append(1), target=tmp_path / "t",
    )
    assert released == [1]
    assert result.revision == "36.0.2"
    assert (tmp_path / "t" / "adb.exe").read_bytes() == FILES["adb.exe"]
    store.close()


def test_adb_locked_on_every_attempt_raises_after_three_releases(tmp_path, monkeypatch):
    store = make_store(tmp_path, FILES)

    def always_locked(zf, info, dest, on_bytes=None):
        raise PermissionError(13, "adb.exe is in use")

    monkeypatch.setattr(platform_tools, "extract_verified", always_locked)
    released = []
    with pytest.raises(PermissionError):
        ensure_platform_tools(
            store, Logger(EventBus()), release_lock=lambda: released.append(1), target=tmp_path / "t",
        )
    assert len(released) == 3
    store.close()


def test_revision_is_unknown_without_source_properties(tmp_path):
    store = make_store(tmp_path, {"adb.exe": b"x"})
    assert ensure_platform_tools(store, Logger(EventBus()), target=tmp_path / "t").revision == "?"
    store.close()
