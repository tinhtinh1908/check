"""Scripted in-process adb server for protocol tests (no real adb.exe or device needed)."""

from __future__ import annotations

import socket
import struct
import threading

U32 = struct.Struct("<I")


def _recv_exact(conn: socket.socket, size: int) -> bytes | None:
    buf = bytearray()
    while len(buf) < size:
        chunk = conn.recv(size - len(buf))
        if not chunk:
            return None
        buf += chunk
    return bytes(buf)


def _read_request(conn: socket.socket) -> str | None:
    head = _recv_exact(conn, 4)
    if head is None:
        return None
    body = _recv_exact(conn, int(head, 16))
    return None if body is None else body.decode()


def _send_block(conn: socket.socket, data: bytes) -> None:
    conn.sendall(b"%04x" % len(data) + data)


def _fail(conn: socket.socket, message: str) -> None:
    conn.sendall(b"FAIL")
    _send_block(conn, message.encode())


class FakeAdbServer:
    def __init__(self) -> None:
        self.version = 41
        self.devices_text = (
            "SER123          device product:sapphire model:Redmi_Note_13 device:sapphire transport_id:3\n"
        )
        self.track_updates: list[str] = []
        self.track_hold = False  # keep the track connection open until the client closes it
        self.features: dict[str, str] = {"SER123": "shell_v2,cmd,stat_v2,ls_v2"}
        self.shell_results: dict[str, tuple[str, str, int]] = {}
        self.shell_hook = None  # optional callable(cmd) -> (stdout, stderr, rc) | None
        self.drop_on: set[str] = set()  # shell commands answered by closing the stream (device gone)
        self.on_drop = None  # optional callable run when a drop happens (e.g. unplug the device)
        self.install_reply = "Success\n"
        self.commit_reply = "Success\n"
        self.commit_hold = False  # leave install-commit unanswered, like a phone showing its install prompt
        self.write_reply = "Success: streamed {n} bytes\n"
        self.push_fail: str | None = None
        self.pushed: dict[str, bytes] = {}
        self.push_modes: dict[str, int] = {}
        self.data_chunk_sizes: list[int] = []
        self.installed: list[bytes] = []
        self.session_parts: dict[str, list[tuple[str, bytes]]] = {}
        self.services: list[str] = []
        self.killed = False
        self._sock = socket.socket()
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(32)
        self.port = self._sock.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def _serve(self) -> None:
        while True:
            try:
                conn, _addr = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle_safe, args=(conn,), daemon=True).start()

    def _handle_safe(self, conn: socket.socket) -> None:
        try:
            self._handle(conn)
        except OSError:
            pass
        finally:
            conn.close()

    def _shell_result(self, cmd: str) -> tuple[str, str, int]:
        if self.shell_hook is not None:
            result = self.shell_hook(cmd)
            if result is not None:
                return result
        return self.shell_results.get(cmd, ("", "", 0))

    def _handle(self, conn: socket.socket) -> None:
        service = _read_request(conn)
        if service is None:
            return
        self.services.append(service)
        if service == "host:version":
            conn.sendall(b"OKAY")
            _send_block(conn, b"%04x" % self.version)
        elif service == "host:devices-l":
            conn.sendall(b"OKAY")
            _send_block(conn, self.devices_text.encode())
        elif service == "host:track-devices-l":
            conn.sendall(b"OKAY")
            for update in self.track_updates:
                _send_block(conn, update.encode())
            if self.track_hold:
                conn.recv(1)  # blocks until the client closes the connection
        elif service.startswith("host-serial:") and service.endswith(":features"):
            serial = service[len("host-serial:") : -len(":features")]
            if serial not in self.features:
                _fail(conn, f"device '{serial}' not found")
                return
            conn.sendall(b"OKAY")
            _send_block(conn, self.features[serial].encode())
        elif service == "host:kill":
            self.killed = True
            conn.sendall(b"OKAY")
            self.close()
        elif service.startswith("host:transport:"):
            serial = service[len("host:transport:") :]
            if serial not in self.features:
                _fail(conn, f"device '{serial}' not found")
                return
            conn.sendall(b"OKAY")
            device_service = _read_request(conn)
            if device_service is not None:
                self.services.append(device_service)
                self._device(conn, device_service)
        else:
            _fail(conn, "unknown host service")

    def _device(self, conn: socket.socket, service: str) -> None:
        if service.startswith("shell,v2,raw:"):
            cmd = service[len("shell,v2,raw:") :]
            conn.sendall(b"OKAY")
            if cmd in self.drop_on:
                if self.on_drop is not None:
                    self.on_drop()
                return
            out, err, code = self._shell_result(cmd)
            for packet_id, data in ((1, out.encode()), (2, err.encode())):
                if data:
                    conn.sendall(struct.pack("<BI", packet_id, len(data)) + data)
            conn.sendall(struct.pack("<BI", 3, 1) + bytes([code]))
        elif service.startswith("shell:"):
            cmd = service[len("shell:") :].split(" ; echo __BULL_RC=")[0]
            out, err, code = self._shell_result(cmd)
            conn.sendall(b"OKAY" + (out + err).encode() + f"__BULL_RC={code}\n".encode())
        elif service == "sync:":
            conn.sendall(b"OKAY")
            self._sync(conn)
        elif service.startswith("exec:cmd package install -S "):
            size = int(service.rsplit(" ", 1)[1])
            conn.sendall(b"OKAY")
            data = _recv_exact(conn, size)
            if data is None:
                return
            self.installed.append(data)
            conn.sendall(self.install_reply.encode())
        elif service.startswith("exec:cmd package install-create"):
            self.session_parts["77"] = []
            conn.sendall(b"OKAY" + b"Success: created install session [77]\n")
        elif service.startswith("exec:cmd package install-write"):
            # exec:cmd package install-write -S <size> <session> <name> -
            parts = service.split()
            size, session, name = int(parts[4]), parts[5], parts[6]
            conn.sendall(b"OKAY")
            data = _recv_exact(conn, size)
            if data is None:
                return
            self.session_parts[session].append((name, data))
            conn.sendall(self.write_reply.format(n=size).encode())
        elif service.startswith("exec:cmd package install-commit"):
            if self.commit_hold:
                conn.sendall(b"OKAY")
                conn.recv(1)  # blocks until the client gives up and closes the connection
                return
            conn.sendall(b"OKAY" + self.commit_reply.encode())
        elif service.startswith("exec:cmd package install-abandon"):
            conn.sendall(b"OKAY" + b"Success\n")
        else:
            _fail(conn, f"unknown device service {service}")

    def _sync(self, conn: socket.socket) -> None:
        while True:
            head = _recv_exact(conn, 8)
            if head is None:
                return
            ident, size = head[:4], U32.unpack(head[4:])[0]
            if ident != b"SEND":
                return
            spec = _recv_exact(conn, size)
            if spec is None:
                return
            path, mode = spec.decode().rsplit(",", 1)
            buf = bytearray()
            while True:
                frame = _recv_exact(conn, 8)
                if frame is None:
                    return
                kind, length = frame[:4], U32.unpack(frame[4:])[0]
                if kind == b"DATA":
                    chunk = _recv_exact(conn, length)
                    if chunk is None:
                        return
                    self.data_chunk_sizes.append(length)
                    buf += chunk
                elif kind == b"DONE":
                    break
                else:
                    return
            if self.push_fail:
                message = self.push_fail.encode()
                conn.sendall(b"FAIL" + U32.pack(len(message)) + message)
            else:
                self.pushed[path] = bytes(buf)
                self.push_modes[path] = int(mode)
                conn.sendall(b"OKAY" + U32.pack(0))
