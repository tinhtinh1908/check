"""Low-level framing for the adb host protocol (AOSP ``SERVICES.TXT`` / ``SYNC.TXT``).

Host request:  4 hex digits (payload length) + payload; reply ``OKAY`` or ``FAIL`` + hex4 length + message.
Sync protocol: 4-byte id + little-endian u32 length (+ data).  Shell v2: u8 id + u32le length + data.
"""

from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Callable, Iterator
from typing import BinaryIO

HOST = "127.0.0.1"
PORT = 5037
SYNC_DATA_MAX = 64 * 1024

SHELL_STDOUT = 1
SHELL_STDERR = 2
SHELL_EXIT = 3

_U32 = struct.Struct("<I")
_SHELL_HEADER = struct.Struct("<BI")


class AdbError(Exception):
    """The adb server or device answered FAIL (or an unexpected reply)."""


class AdbConnectionError(AdbError):
    """The adb server is not reachable."""


class DeviceGoneError(AdbError):
    """The device or connection disappeared in the middle of an operation."""


class Cancelled(Exception):
    """The operation was cancelled by the user."""


CONNECT_TIMEOUT = 0.75  # loopback: a live server answers in ~1 ms; Windows needs ~2 s to report "refused"


def connect(host: str = HOST, port: int = PORT, timeout: float | None = 3.0) -> socket.socket:
    try:
        sock = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
    except OSError as exc:
        raise AdbConnectionError(f"cannot connect to adb server at {host}:{port}: {exc}") from exc
    sock.settimeout(timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


def send_all(sock: socket.socket, data: bytes) -> None:
    """``sendall`` that reports socket failures as adb errors (callers only need to handle AdbError)."""
    try:
        sock.sendall(data)
    except TimeoutError as exc:
        raise DeviceGoneError("timed out sending to the device") from exc
    except OSError as exc:
        raise DeviceGoneError(f"connection lost: {exc}") from exc


def send_request(sock: socket.socket, service: str) -> None:
    data = service.encode("utf-8")
    send_all(sock, b"%04x" % len(data) + data)


def recv_exact(sock: socket.socket, size: int) -> bytes:
    buf = bytearray()
    while len(buf) < size:
        try:
            chunk = sock.recv(size - len(buf))
        except TimeoutError as exc:
            raise DeviceGoneError("timed out waiting for the device") from exc
        except OSError as exc:
            raise DeviceGoneError(f"connection lost: {exc}") from exc
        if not chunk:
            raise DeviceGoneError("connection closed")
        buf += chunk
    return bytes(buf)


CANCEL_POLL = 0.5


def read_all(sock: socket.socket, cancel: threading.Event | None = None) -> bytes:
    """Read until the peer closes the stream.

    With ``cancel``, the wait is sliced so a Stop request is honoured even while the phone sits on an
    install confirmation prompt; the socket's own timeout still bounds how long it may stay silent.
    """
    buf = bytearray()
    limit = sock.gettimeout()
    if cancel is not None:
        sock.settimeout(CANCEL_POLL if limit is None else min(CANCEL_POLL, limit))
    idle = 0.0
    while True:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        try:
            chunk = sock.recv(65536)
        except TimeoutError as exc:
            if cancel is not None:
                idle += sock.gettimeout() or CANCEL_POLL
                if limit is None or idle < limit:
                    continue
            raise DeviceGoneError("timed out waiting for the device") from exc
        except OSError as exc:
            raise DeviceGoneError(f"connection lost: {exc}") from exc
        if not chunk:
            return bytes(buf)
        idle = 0.0
        buf += chunk


def drain_quietly(sock: socket.socket, wait: float = 1.0) -> str:
    """Best effort: whatever the peer already sent (e.g. ``Failure [...]`` before it reset the stream)."""
    buf = bytearray()
    try:
        sock.settimeout(wait)
        while chunk := sock.recv(65536):
            buf += chunk
    except OSError:
        pass
    return buf.decode("utf-8", "replace")


def read_hex_block(sock: socket.socket) -> bytes:
    size = int(recv_exact(sock, 4), 16)
    return recv_exact(sock, size)


def read_status(sock: socket.socket) -> None:
    status = recv_exact(sock, 4)
    if status == b"OKAY":
        return
    if status == b"FAIL":
        raise AdbError(read_hex_block(sock).decode("utf-8", "replace"))
    raise AdbError(f"unexpected adb reply {status!r}")


def iter_shell_v2(sock: socket.socket) -> Iterator[tuple[int, bytes]]:
    """Yield ``(packet_id, data)`` until the stream ends."""
    while True:
        try:
            header = recv_exact(sock, _SHELL_HEADER.size)
        except DeviceGoneError:
            return
        packet_id, size = _SHELL_HEADER.unpack(header)
        yield packet_id, recv_exact(sock, size) if size else b""


def stream_to_socket(
    sock: socket.socket,
    stream: BinaryIO,
    size: int,
    on_bytes: Callable[[int], None] | None = None,
    cancel: threading.Event | None = None,
    framing: Callable[[bytes], bytes] | None = None,
) -> None:
    """Copy exactly ``size`` bytes from ``stream`` to ``sock`` in ≤64 KiB chunks."""
    sent = 0
    while sent < size:
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        chunk = stream.read(min(SYNC_DATA_MAX, size - sent))
        if not chunk:
            raise AdbError(f"source ended early ({sent}/{size} bytes)")
        send_all(sock, framing(chunk) if framing else chunk)
        sent += len(chunk)
        if on_bytes is not None:
            on_bytes(len(chunk))


def sync_send(
    sock: socket.socket,
    remote_path: str,
    mode: int,
    stream: BinaryIO,
    size: int,
    mtime: int,
    on_bytes: Callable[[int], None] | None = None,
    cancel: threading.Event | None = None,
) -> None:
    """Push one file over an open ``sync:`` connection (SEND / DATA... / DONE)."""
    spec = f"{remote_path},{mode}".encode()
    send_all(sock, b"SEND" + _U32.pack(len(spec)) + spec)
    stream_to_socket(sock, stream, size, on_bytes, cancel, framing=lambda c: b"DATA" + _U32.pack(len(c)) + c)
    send_all(sock, b"DONE" + _U32.pack(mtime & 0xFFFFFFFF))
    reply = recv_exact(sock, 8)
    ident, length = reply[:4], _U32.unpack(reply[4:])[0]
    if ident == b"OKAY":
        return
    if ident == b"FAIL":
        raise AdbError(recv_exact(sock, length).decode("utf-8", "replace"))
    raise AdbError(f"unexpected sync reply {ident!r}")


def sync_quit(sock: socket.socket) -> None:
    try:
        sock.sendall(b"QUIT" + _U32.pack(0))
    except OSError:
        pass
