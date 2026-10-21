"""Shared test helpers."""

import io
import socket
import zipfile

from bull_tool.core.adb import protocol
from bull_tool.core.payload import PAYLOAD_MAGIC, PYI_COOKIE, PYI_MAGIC, TRAILER


def zip_bytes(entries: dict[str, bytes], compress: int = zipfile.ZIP_STORED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=compress) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def fake_exe(path, payload: bytes | None, trailer_magic: bytes = PAYLOAD_MAGIC) -> int:
    """Write ``MZ head + payload + trailer + fake PKG + cookie``; return the payload offset."""
    head = b"MZ" + b"\0" * 998
    pkg_body = b"PKGDATA" * 64
    cookie = PYI_COOKIE.pack(PYI_MAGIC, len(pkg_body) + PYI_COOKIE.size, 0, 0, 314, b"python314.dll")
    blob = head
    if payload is not None:
        blob += payload + TRAILER.pack(trailer_magic, len(payload))
    path.write_bytes(blob + pkg_body + cookie)
    return len(head)


def unused_port() -> int:
    """A loopback port that nothing listens on (bound, read, then released)."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def reset_first_send(monkeypatch, error: BaseException) -> None:
    """Make the first send on the next adb connection raise ``error``, as if the server had reset the socket."""
    real_connect = protocol.connect
    armed = [True]

    class ResetOnFirstSend:
        def __init__(self, sock):
            self._sock = sock

        def __getattr__(self, name):
            return getattr(self._sock, name)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            self._sock.close()

        def sendall(self, data):
            if armed[0]:
                armed[0] = False
                raise error
            self._sock.sendall(data)

    def connect(*args, **kwargs):
        return ResetOnFirstSend(real_connect(*args, **kwargs))

    monkeypatch.setattr("bull_tool.core.adb.client.connect", connect)
