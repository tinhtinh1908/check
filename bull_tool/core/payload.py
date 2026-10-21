"""Embedded resource payload (APKs, platform-tools zip, USB driver).

Frozen exe layout (the payload is inserted by ``scripts/inject_payload.py`` after PyInstaller builds):

    [PE bootloader + resources][payload.zip][trailer <8sQ: b"BULLPAY1", len>][PyInstaller PKG ... cookie]

The PyInstaller bootloader locates its PKG from the cookie at the end of the file
(``pkg_start = cookie_end - archive_length``), so bytes placed before ``pkg_start`` are ignored by it.
When running from source the same payload is read from ``.build/payload.zip``.
"""

from __future__ import annotations

import io
import os
import struct
import sys
import threading
import zipfile
import zlib
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from bull_tool.core import paths

PYI_MAGIC = b"MEI\014\013\012\013\016"
PYI_COOKIE = struct.Struct("!8sIIII64s")
TRAILER = struct.Struct("<8sQ")
PAYLOAD_MAGIC = b"BULLPAY1"

APK_PREFIX = "APK/"
PLATFORM_TOOLS_ZIP = "platform-tools-latest-windows.zip"
DRIVER_PREFIX = "USB_DRIVER_XIAOMI/"
DRIVER_INF = DRIVER_PREFIX + "android_winusb.inf"

_TAIL_SCAN = 64 * 1024
_CHUNK = 1024 * 1024


class PayloadError(Exception):
    """Base error for payload problems."""


class PayloadNotFoundError(PayloadError):
    """The executable (or dev build) carries no readable payload."""


class CorruptMemberError(PayloadError):
    """A payload member failed its CRC check."""

    def __init__(self, name: str, reason: str) -> None:
        super().__init__(f"{name}: {reason}")
        self.name = name


def pyinstaller_pkg_start(fp: BinaryIO) -> int:
    """Return the offset where the PyInstaller PKG archive starts, using its trailing cookie."""
    fp.seek(0, os.SEEK_END)
    size = fp.tell()
    scan = min(size, _TAIL_SCAN)
    fp.seek(size - scan)
    tail = fp.read(scan)
    idx = tail.rfind(PYI_MAGIC)
    if idx < 0 or len(tail) - idx < PYI_COOKIE.size:
        raise PayloadNotFoundError("PyInstaller archive cookie not found")
    _magic, archive_len, _toc_off, _toc_len, _pyver, _pylib = PYI_COOKIE.unpack_from(tail, idx)
    start = (size - scan + idx + PYI_COOKIE.size) - archive_len
    if start < 0:
        raise PayloadNotFoundError("invalid PyInstaller archive length")
    return start


def locate_payload(exe: Path) -> tuple[int, int]:
    """Return ``(offset, length)`` of the payload zip embedded in a frozen executable."""
    with open(exe, "rb") as fp:
        pkg_start = pyinstaller_pkg_start(fp)
        if pkg_start < TRAILER.size:
            raise PayloadNotFoundError("no payload trailer")
        fp.seek(pkg_start - TRAILER.size)
        magic, length = TRAILER.unpack(fp.read(TRAILER.size))
    if magic != PAYLOAD_MAGIC:
        raise PayloadNotFoundError("payload trailer missing")
    offset = pkg_start - TRAILER.size - length
    if offset < 64:  # the PE headers always come first
        raise PayloadNotFoundError("payload offset out of range")
    return offset, length


class SubFile(io.RawIOBase):
    """Read-only, seekable window ``[start, start + length)`` over a file (own handle per instance)."""

    def __init__(self, path: Path | str, start: int, length: int) -> None:
        super().__init__()
        self._fp = open(path, "rb")
        self._start = start
        self._length = length
        self._pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        base = {os.SEEK_SET: 0, os.SEEK_CUR: self._pos, os.SEEK_END: self._length}[whence]
        self._pos = max(0, base + offset)
        return self._pos

    def read(self, size: int = -1) -> bytes:
        remaining = self._length - self._pos
        if size is None or size < 0 or size > remaining:
            size = max(0, remaining)
        if size == 0:
            return b""
        self._fp.seek(self._start + self._pos)
        data = self._fp.read(size)
        self._pos += len(data)
        return data

    def readinto(self, buffer) -> int:  # type: ignore[override]
        data = self.read(len(buffer))
        buffer[: len(data)] = data
        return len(data)

    def close(self) -> None:
        if not self.closed:
            self._fp.close()
        super().close()


class ResourceStore:
    """Read access to payload members. Member streams are created under a lock (``ZipFile.open`` keeps a
    non-atomic reference count); reads afterwards are serialized by ``zipfile`` itself."""

    def __init__(self, fileobj: BinaryIO, source: str) -> None:
        self._fileobj = fileobj
        try:
            self._zip = zipfile.ZipFile(fileobj)
        except (zipfile.BadZipFile, EOFError, ValueError) as exc:
            fileobj.close()
            raise PayloadError(f"payload is damaged ({source}): {exc}") from exc
        self._lock = threading.Lock()
        self.source = source
        self._infos = {i.filename: i for i in self._zip.infolist() if not i.is_dir()}

    @classmethod
    def open_default(cls) -> ResourceStore:
        """Frozen: payload inside ``sys.executable``. Source checkout: ``.build/payload.zip``."""
        if paths.is_frozen():
            exe = Path(sys.executable)
            offset, length = locate_payload(exe)
            return cls(SubFile(exe, offset, length), f"{exe.name}@{offset}")
        dev = paths.dev_payload_path()
        if not dev.exists():
            raise PayloadNotFoundError(f"missing {dev}; run: python scripts/build_payload.py")
        return cls(open(dev, "rb"), str(dev))

    @classmethod
    def from_exe(cls, exe: Path) -> ResourceStore:
        offset, length = locate_payload(exe)
        return cls(SubFile(exe, offset, length), f"{exe.name}@{offset}")

    def __enter__(self) -> ResourceStore:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def names(self, prefix: str = "") -> list[str]:
        return sorted(n for n in self._infos if n.startswith(prefix))

    def exists(self, name: str) -> bool:
        return name in self._infos

    def info(self, name: str) -> zipfile.ZipInfo:
        try:
            return self._infos[name]
        except KeyError:
            raise PayloadError(f"missing payload member: {name}") from None

    def size(self, name: str) -> int:
        return self.info(name).file_size

    def open(self, name: str) -> BinaryIO:
        """Stream a member; ``zipfile`` raises ``BadZipFile`` at EOF when its CRC does not match."""
        info = self.info(name)
        with self._lock:
            return self._zip.open(info)  # type: ignore[return-value]

    def open_zip(self, name: str) -> zipfile.ZipFile:
        """Open a nested (stored) zip member as a ``ZipFile`` (closing it also closes the member stream)."""
        member = self.open(name)
        try:
            return _NestedZip(member)
        except (zipfile.BadZipFile, EOFError, ValueError) as exc:
            member.close()
            raise PayloadError(f"{name} is damaged: {exc}") from exc

    def extract(self, name: str, dest: Path, on_bytes: Callable[[int], None] | None = None) -> None:
        """Extract one member with CRC verification (for small files: holds the store lock throughout)."""
        with self._lock:
            extract_verified(self._zip, self.info(name), dest, on_bytes)

    def testzip(self) -> str | None:
        """Read every member and return the first one with a bad CRC, or None."""
        with self._lock:
            return self._zip.testzip()

    def close(self) -> None:
        self._zip.close()
        self._fileobj.close()  # zipfile never closes a file object it was handed


class _NestedZip(zipfile.ZipFile):
    """ZipFile over a member stream of another zip; owns that stream."""

    def __init__(self, member: BinaryIO) -> None:
        self._member = member
        super().__init__(member)

    def close(self) -> None:
        try:
            super().close()
        finally:
            self._member.close()


def safe_join(root: Path, member_name: str, strip_prefix: str = "") -> Path:
    """Map a zip member name to a path under ``root``, rejecting absolute paths, ``..`` and drive or
    backslash forms that Windows would interpret as separators (zip-slip)."""
    name = member_name
    if strip_prefix and name.startswith(strip_prefix):
        name = name[len(strip_prefix) :]
    rel = PurePosixPath(name)
    unsafe = rel.is_absolute() or not rel.parts or ":" in name or "\\" in name
    if unsafe or any(part in ("..", "") for part in rel.parts):
        raise PayloadError(f"unsafe member path: {member_name}")
    return root.joinpath(*rel.parts)


def file_crc32(path: Path) -> int:
    crc = 0
    with open(path, "rb") as fp:
        while chunk := fp.read(_CHUNK):
            crc = zlib.crc32(chunk, crc)
    return crc


def file_matches(path: Path, info: zipfile.ZipInfo) -> bool:
    """True when ``path`` exists with the member's exact size and CRC32."""
    try:
        size = path.stat().st_size
    except OSError:
        return False
    return size == info.file_size and file_crc32(path) == info.CRC


def extract_verified(
    zf: zipfile.ZipFile,
    member: zipfile.ZipInfo | str,
    dest: Path,
    on_bytes: Callable[[int], None] | None = None,
) -> None:
    """Extract one member to ``dest`` via a temp file; replace ``dest`` only when the CRC matches."""
    info = member if isinstance(member, zipfile.ZipInfo) else zf.getinfo(member)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    crc = 0
    try:
        with zf.open(info) as src, open(tmp, "wb") as out:
            while chunk := src.read(_CHUNK):
                out.write(chunk)
                crc = zlib.crc32(chunk, crc)
                if on_bytes:
                    on_bytes(len(chunk))
        if crc != info.CRC or tmp.stat().st_size != info.file_size:
            raise CorruptMemberError(info.filename, "CRC mismatch")
        os.replace(tmp, dest)
    except zipfile.BadZipFile as exc:
        raise CorruptMemberError(info.filename, str(exc)) from exc
    finally:
        tmp.unlink(missing_ok=True)
