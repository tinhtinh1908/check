"""High-level adb operations used by the app: devices, realtime tracking, shell, push and streamed installs.

Every operation opens its own socket to the adb server, so one ``AdbClient`` is safe to share between
threads. APK bytes are streamed from any binary stream (the payload inside the exe) with byte progress.
"""

from __future__ import annotations

import re
import shlex
import socket
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import BinaryIO

from bull_tool.core.adb.protocol import (
    HOST,
    PORT,
    SHELL_EXIT,
    SHELL_STDERR,
    SHELL_STDOUT,
    AdbError,
    DeviceGoneError,
    connect,
    drain_quietly,
    iter_shell_v2,
    read_all,
    read_hex_block,
    read_status,
    send_request,
    stream_to_socket,
    sync_quit,
    sync_send,
)

SHELL_RC_MARKER = "__BULL_RC="
INSTALL_TIMEOUT = 300.0  # waits for on-device confirmation prompts
S_IFREG = 0o100000

ProgressFn = Callable[[int, int], None]  # (bytes_done, bytes_total)


@dataclass(frozen=True, slots=True)
class DeviceEntry:
    serial: str
    state: str  # device | unauthorized | offline | recovery | sideload | authorizing | ...
    model: str = ""
    product: str = ""
    device: str = ""
    transport_id: str = ""

    @property
    def ready(self) -> bool:
        return self.state == "device"


@dataclass(frozen=True, slots=True)
class ShellResult:
    stdout: str
    stderr: str
    exit_code: int

    @property
    def output(self) -> str:
        return (self.stdout + self.stderr).strip()

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class InstallError(AdbError):
    """Package manager refused the install; ``code`` is e.g. ``INSTALL_FAILED_USER_RESTRICTED``."""

    def __init__(self, raw: str) -> None:
        self.raw = (raw or "").strip()
        match = re.search(r"\[([A-Z][A-Z0-9_]+)", self.raw)
        self.code = match.group(1) if match else ""
        super().__init__(self.raw or "no response from package manager")


def parse_devices(text: str) -> list[DeviceEntry]:
    """Parse ``devices -l`` output: ``serial state key:value ...`` per line."""
    entries = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2 or line.startswith(("*", "List of devices")):
            continue
        props = dict(p.split(":", 1) for p in parts[2:] if ":" in p)
        entries.append(
            DeviceEntry(
                parts[0], parts[1], props.get("model", ""), props.get("product", ""),
                props.get("device", ""), props.get("transport_id", ""),
            )
        )
    return entries


def _check_install(output: str) -> None:
    if any(line.strip().startswith("Success") for line in output.splitlines()):
        return
    raise InstallError(output)


def _stream_or_report(sock, stream: BinaryIO, size: int, on_bytes, cancel) -> None:
    """Stream APK bytes; when the package manager aborts early (e.g. storage full) it answers
    ``Failure [...]`` and closes the stream. Surface that answer instead of a misleading "device gone"."""
    try:
        stream_to_socket(sock, stream, size, on_bytes, cancel)
    except DeviceGoneError as exc:
        answer = drain_quietly(sock)
        if "Failure" in answer:
            raise InstallError(answer) from exc
        raise


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _counter(total: int, on_progress: ProgressFn | None) -> Callable[[int], None]:
    done = 0

    def on_bytes(count: int) -> None:
        nonlocal done
        done += count
        if on_progress is not None:
            on_progress(done, total)

    return on_bytes


class DeviceTracker:
    """Iterates complete device lists pushed by ``host:track-devices-l``.

    ``close()`` may be called from another thread to unblock the iteration.
    """

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock

    def __iter__(self) -> Iterator[list[DeviceEntry]]:
        try:
            while True:
                yield parse_devices(read_hex_block(self._sock).decode("utf-8", "replace"))
        except (DeviceGoneError, OSError, ValueError):
            return

    def close(self) -> None:
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._sock.close()


class AdbClient:
    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        self.host = host
        self.port = port

    # -- host services -------------------------------------------------------------------------------
    def _connect(self, timeout: float | None = 10.0) -> socket.socket:
        return connect(self.host, self.port, timeout)

    def _host_query(self, service: str) -> bytes:
        with self._connect() as sock:
            send_request(sock, service)
            read_status(sock)
            return read_hex_block(sock)

    def server_version(self) -> int:
        return int(self._host_query("host:version"), 16)

    def devices(self) -> list[DeviceEntry]:
        return parse_devices(self._host_query("host:devices-l").decode("utf-8", "replace"))

    def track_devices(self) -> DeviceTracker:
        sock = self._connect(timeout=None)
        try:
            send_request(sock, "host:track-devices-l")
            read_status(sock)
        except BaseException:
            sock.close()
            raise
        return DeviceTracker(sock)

    def features(self, serial: str) -> frozenset[str]:
        raw = self._host_query(f"host-serial:{serial}:features").decode("utf-8", "replace")
        return frozenset(f.strip() for f in raw.split(",") if f.strip())

    def kill_server(self) -> None:
        with self._connect() as sock:
            send_request(sock, "host:kill")
            try:
                read_status(sock)
            except DeviceGoneError:
                pass

    # -- device services -----------------------------------------------------------------------------
    def open_service(self, serial: str, service: str, timeout: float | None = 60.0) -> socket.socket:
        sock = self._connect(timeout)
        try:
            send_request(sock, f"host:transport:{serial}")
            try:
                read_status(sock)
            except AdbError as exc:  # device not found / offline / unauthorized
                raise DeviceGoneError(str(exc)) from exc
            send_request(sock, service)
            read_status(sock)
            return sock
        except BaseException:
            sock.close()
            raise

    def shell(
        self, serial: str, cmd: str, timeout: float = 60.0, features: frozenset[str] | None = None
    ) -> ShellResult:
        feats = features if features is not None else self.features(serial)
        if "shell_v2" in feats:
            out, err, code = bytearray(), bytearray(), None
            with self.open_service(serial, f"shell,v2,raw:{cmd}", timeout) as sock:
                for packet_id, data in iter_shell_v2(sock):
                    if packet_id == SHELL_STDOUT:
                        out += data
                    elif packet_id == SHELL_STDERR:
                        err += data
                    elif packet_id == SHELL_EXIT:
                        code = data[0] if data else 0
                        break
            if code is None:
                raise DeviceGoneError("shell ended without an exit status")
            return ShellResult(out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), code)
        with self.open_service(serial, f"shell:{cmd} ; echo {SHELL_RC_MARKER}$?", timeout) as sock:
            raw = read_all(sock).decode("utf-8", "replace").replace("\r\n", "\n")
        text, marker, tail = raw.rpartition(SHELL_RC_MARKER)
        if not marker:
            raise DeviceGoneError("shell ended without an exit status")
        match = re.match(r"\d+", tail.strip())
        return ShellResult(text, "", int(match.group()) if match else 1)

    def exec_text(
        self, serial: str, cmd: str, timeout: float = 60.0, cancel: threading.Event | None = None
    ) -> str:
        with self.open_service(serial, f"exec:{cmd}", timeout) as sock:
            return read_all(sock, cancel).decode("utf-8", "replace")

    def push(
        self,
        serial: str,
        stream: BinaryIO,
        size: int,
        remote_path: str,
        mode: int = 0o644,
        on_progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
        timeout: float = 120.0,
    ) -> None:
        with self.open_service(serial, "sync:", timeout) as sock:
            sync_send(
                sock, remote_path, S_IFREG | mode, stream, size, int(time.time()),
                _counter(size, on_progress), cancel,
            )
            sync_quit(sock)

    def install(
        self,
        serial: str,
        stream: BinaryIO,
        size: int,
        name: str,
        on_progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
        features: frozenset[str] | None = None,
        timeout: float = INSTALL_TIMEOUT,
    ) -> str:
        """Equivalent of ``adb install <apk>`` (streamed on Android 7+, push + ``pm install`` before)."""
        feats = features if features is not None else self.features(serial)
        if "cmd" in feats:
            with self.open_service(serial, f"exec:cmd package install -S {size}", timeout) as sock:
                _stream_or_report(sock, stream, size, _counter(size, on_progress), cancel)
                output = read_all(sock, cancel).decode("utf-8", "replace")
            _check_install(output)
            return output.strip()
        remote = f"/data/local/tmp/bull_{_safe_name(name)}"
        try:  # the temp file is removed even when the push itself fails half-way
            self.push(serial, stream, size, remote, on_progress=on_progress, cancel=cancel)
            result = self.shell(serial, f"pm install {shlex.quote(remote)}", timeout=timeout, features=feats)
            _check_install(result.output)
            return result.output
        finally:
            self._quiet_rm(serial, remote, feats)

    def install_multiple(
        self,
        serial: str,
        parts: Sequence[tuple[str, BinaryIO, int]],
        on_progress: ProgressFn | None = None,
        cancel: threading.Event | None = None,
        features: frozenset[str] | None = None,
        timeout: float = INSTALL_TIMEOUT,
    ) -> str:
        """Equivalent of ``adb install-multiple base.apk split.apk ...`` using an install session."""
        feats = features if features is not None else self.features(serial)
        streamed = "cmd" in feats
        total = sum(size for _name, _stream, size in parts)
        on_bytes = _counter(total, on_progress)
        if streamed:
            created = self.exec_text(serial, f"cmd package install-create -S {total}", timeout)
        else:
            created = self.shell(serial, f"pm install-create -S {total}", features=feats).output
        match = re.search(r"\[(\d+)\]", created)
        if not match:
            raise InstallError(created)
        session = match.group(1)
        try:
            for index, (name, stream, size) in enumerate(parts):
                split = f"{index}_{_safe_name(name)}"
                if streamed:
                    service = f"exec:cmd package install-write -S {size} {session} {split} -"
                    with self.open_service(serial, service, timeout) as sock:
                        _stream_or_report(sock, stream, size, on_bytes, cancel)
                        written = read_all(sock, cancel).decode("utf-8", "replace")
                else:
                    remote = f"/data/local/tmp/bull_{split}"
                    pushed = [0]

                    def part_progress(done: int, _total: int, pushed=pushed) -> None:
                        on_bytes(done - pushed[0])  # convert this part's running total into deltas
                        pushed[0] = done

                    try:
                        self.push(serial, stream, size, remote, on_progress=part_progress, cancel=cancel)
                        written = self.shell(
                            serial, f"pm install-write -S {size} {session} {split} {shlex.quote(remote)}",
                            features=feats,
                        ).output
                    finally:
                        self._quiet_rm(serial, remote, feats)
                _check_install(written)
            if streamed:
                # the phone may sit on its install confirmation prompt here: Stop must not wait for it
                committed = self.exec_text(serial, f"cmd package install-commit {session}", timeout, cancel)
            else:
                commit_cmd = f"pm install-commit {session}"
                committed = self.shell(serial, commit_cmd, timeout=timeout, features=feats).output
            _check_install(committed)
            return committed.strip()
        except BaseException:
            self._abandon(serial, session, streamed, feats)
            raise

    def _abandon(self, serial: str, session: str, streamed: bool, feats: frozenset[str]) -> None:
        try:
            if streamed:
                self.exec_text(serial, f"cmd package install-abandon {session}", 30.0)
            else:
                self.shell(serial, f"pm install-abandon {session}", timeout=30.0, features=feats)
        except Exception:  # noqa: BLE001 - best effort cleanup; the original error matters more
            pass

    def _quiet_rm(self, serial: str, remote: str, feats: frozenset[str]) -> None:
        try:
            self.shell(serial, f"rm -f {shlex.quote(remote)}", timeout=30.0, features=feats)
        except Exception:  # noqa: BLE001 - temp file cleanup is best effort
            pass
