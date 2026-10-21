import os
import sys
import zipfile

import pytest

from bull_tool.core import payload as pl
from bull_tool.core.payload import (
    PAYLOAD_MAGIC,
    PYI_COOKIE,
    PYI_MAGIC,
    TRAILER,
    CorruptMemberError,
    PayloadError,
    PayloadNotFoundError,
    ResourceStore,
    SubFile,
    extract_verified,
    file_matches,
    locate_payload,
    safe_join,
)
from tests.helpers import fake_exe, zip_bytes


def test_subfile_window_semantics(tmp_path):
    data = bytes(range(256)) * 4
    src = tmp_path / "data.bin"
    src.write_bytes(data)
    with SubFile(src, 10, 100) as sub:
        assert sub.read(5) == data[10:15]
        assert sub.tell() == 5
        assert sub.seek(0, os.SEEK_END) == 100
        assert sub.read() == b""
        sub.seek(-10, os.SEEK_END)
        assert sub.read() == data[100:110]
        sub.seek(2)
        buf = bytearray(4)
        assert sub.readinto(buf) == 4 and bytes(buf) == data[12:16]
        sub.seek(50, os.SEEK_CUR)
        assert sub.tell() == 56
        assert sub.read(1000) == data[66:110]


def test_locate_payload_and_read_members(tmp_path):
    members = {"APK/a.apk": os.urandom(4096), "platform-tools-latest-windows.zip": b"zipdata"}
    payload = zip_bytes(members)
    exe = tmp_path / "app.exe"
    offset = fake_exe(exe, payload)
    assert locate_payload(exe) == (offset, len(payload))
    store = ResourceStore.from_exe(exe)
    try:
        assert store.names("APK/") == ["APK/a.apk"]
        assert store.size("APK/a.apk") == 4096
        with store.open("APK/a.apk") as fp:
            assert fp.read() == members["APK/a.apk"]
        assert store.testzip() is None
        with pytest.raises(PayloadError):
            store.info("missing.apk")
    finally:
        store.close()


def test_locate_payload_rejects_missing_trailer(tmp_path):
    exe = tmp_path / "plain.exe"
    fake_exe(exe, None)
    with pytest.raises(PayloadNotFoundError):
        locate_payload(exe)
    bad = tmp_path / "bad.exe"
    fake_exe(bad, zip_bytes({"x": b"1"}), trailer_magic=b"NOTPAY!!")
    with pytest.raises(PayloadNotFoundError):
        locate_payload(bad)


def test_locate_payload_rejects_non_pyinstaller_file(tmp_path):
    other = tmp_path / "other.exe"
    other.write_bytes(b"MZ" + os.urandom(10000))
    with pytest.raises(PayloadNotFoundError):
        locate_payload(other)


def test_open_nested_zip(tmp_path):
    inner = zip_bytes({"platform-tools/adb.exe": b"adb-binary"})
    outer = tmp_path / "payload.zip"
    outer.write_bytes(zip_bytes({"platform-tools-latest-windows.zip": inner}))
    store = ResourceStore(open(outer, "rb"), str(outer))
    try:
        with store.open_zip("platform-tools-latest-windows.zip") as nested:
            assert nested.read("platform-tools/adb.exe") == b"adb-binary"
    finally:
        store.close()


def test_extract_verified_and_file_matches(tmp_path):
    data = os.urandom(200_000)
    zpath = tmp_path / "p.zip"
    zpath.write_bytes(zip_bytes({"dir/file.bin": data}))
    dest = tmp_path / "out" / "file.bin"
    seen = []
    with zipfile.ZipFile(zpath) as zf:
        info = zf.getinfo("dir/file.bin")
        extract_verified(zf, info, dest, on_bytes=seen.append)
        assert dest.read_bytes() == data
        assert sum(seen) == len(data)
        assert file_matches(dest, info)
        dest.write_bytes(data[:-1] + bytes([data[-1] ^ 0xFF]))  # same size, different CRC
        assert not file_matches(dest, info)
        dest.write_bytes(data[:10])
        assert not file_matches(dest, info)
        assert not file_matches(tmp_path / "missing.bin", info)


def test_extract_verified_detects_corrupt_member(tmp_path):
    data = os.urandom(65536)
    raw = bytearray(zip_bytes({"a.bin": data}))
    idx = bytes(raw).find(data[1000:1032])
    raw[idx] ^= 0xFF
    zpath = tmp_path / "corrupt.zip"
    zpath.write_bytes(bytes(raw))
    dest = tmp_path / "a.bin"
    with zipfile.ZipFile(zpath) as zf:
        with pytest.raises(CorruptMemberError):
            extract_verified(zf, "a.bin", dest)
    assert not dest.exists()
    assert not (tmp_path / "a.bin.tmp").exists()


@pytest.mark.parametrize("name", ["../evil.txt", "/abs/path", "a/../../b", "C:/x", ""])
def test_safe_join_rejects_unsafe_names(tmp_path, name):
    with pytest.raises(PayloadError):
        safe_join(tmp_path, name)


def test_safe_join_strips_prefix(tmp_path):
    assert safe_join(tmp_path, "platform-tools/adb.exe", "platform-tools/") == tmp_path / "adb.exe"


def test_open_default_dev_and_frozen(tmp_path, monkeypatch):
    dev_zip = tmp_path / "payload.zip"
    dev_zip.write_bytes(zip_bytes({"APK/dev.apk": b"dev"}))
    monkeypatch.setattr(pl.paths, "dev_payload_path", lambda: dev_zip)
    store = ResourceStore.open_default()
    assert store.names() == ["APK/dev.apk"]
    store.close()

    monkeypatch.setattr(pl.paths, "dev_payload_path", lambda: tmp_path / "nope.zip")
    with pytest.raises(PayloadNotFoundError):
        ResourceStore.open_default()

    exe = tmp_path / "frozen.exe"
    fake_exe(exe, zip_bytes({"APK/frozen.apk": b"f"}))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    store = ResourceStore.open_default()
    assert store.names() == ["APK/frozen.apk"]
    store.close()


def test_cookie_with_archive_length_before_file_start_is_rejected(tmp_path):
    exe = tmp_path / "bad-length.exe"
    exe.write_bytes(b"MZ" + bytes(100) + PYI_COOKIE.pack(PYI_MAGIC, 10**6, 0, 0, 314, b"python314.dll"))
    with pytest.raises(PayloadNotFoundError, match="archive length"):
        locate_payload(exe)


def test_truncated_cookie_is_rejected(tmp_path):
    exe = tmp_path / "short-cookie.exe"
    exe.write_bytes(b"MZ" + bytes(500) + PYI_MAGIC)
    with pytest.raises(PayloadNotFoundError, match="cookie"):
        locate_payload(exe)


def test_archive_starting_at_file_head_has_no_payload_trailer(tmp_path):
    exe = tmp_path / "cookie-only.exe"
    exe.write_bytes(PYI_COOKIE.pack(PYI_MAGIC, PYI_COOKIE.size, 0, 0, 314, b"python314.dll"))
    with pytest.raises(PayloadNotFoundError, match="trailer"):
        locate_payload(exe)


def test_payload_placed_inside_pe_headers_is_rejected(tmp_path):
    payload = zip_bytes({"APK/a.apk": b"x"})
    pkg_body = b"PKGDATA" * 64
    cookie = PYI_COOKIE.pack(PYI_MAGIC, len(pkg_body) + PYI_COOKIE.size, 0, 0, 314, b"python314.dll")
    exe = tmp_path / "tiny-head.exe"
    exe.write_bytes(b"MZ" + payload + TRAILER.pack(PAYLOAD_MAGIC, len(payload)) + pkg_body + cookie)
    with pytest.raises(PayloadNotFoundError, match="out of range"):
        locate_payload(exe)


def test_resource_store_close_releases_the_payload_file(tmp_path):
    payload = tmp_path / "payload.zip"
    payload.write_bytes(zip_bytes({"APK/a.apk": b"a"}))
    handle = open(payload, "rb")
    try:
        store = ResourceStore(handle, str(payload))
        store.close()
        assert handle.closed
    finally:
        handle.close()


def test_safe_join_rejects_backslash_traversal(tmp_path):
    with pytest.raises(PayloadError):
        safe_join(tmp_path, "..\\evil.txt")
