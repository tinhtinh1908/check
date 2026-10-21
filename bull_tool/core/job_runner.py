"""Runs device jobs (read info, apply a profile) in worker threads and reports logs + progress.

Profile semantics follow ``@ANDROID.bat``, with one speed-up: packages that are not installed for
user 0 are skipped without a device round-trip (the batch file ran them and got
``Failure [not installed for 0]``). Progress is weighted per step; installs and pushes report real
bytes sent from the payload.
"""

from __future__ import annotations

import contextlib
import shlex
import threading
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from bull_tool.core.adb.client import AdbClient, InstallError
from bull_tool.core.adb.protocol import AdbError, Cancelled, DeviceGoneError
from bull_tool.core.device_info import DeviceInfo, collect_device_info
from bull_tool.core.events import DeviceInfoEvent, EventBus, JobState, Logger, Progress
from bull_tool.core.payload import CorruptMemberError, PayloadError, ResourceStore
from bull_tool.core.profiles import Disable, Install, InstallMulti, Profile, Push, Shell, Step, Uninstall

PROFILE_JOB = "profile"
INFO_JOB = "info"
BYTES_PER_WEIGHT = 6 * 1024 * 1024  # one quick shell step ≈ transferring + installing ~6 MB

STEP_GROUPS = {
    Uninstall: "GỠ ỨNG DỤNG RÁC",
    Disable: "TẮT ỨNG DỤNG HỆ THỐNG",
    Install: "CÀI ỨNG DỤNG",
    InstallMulti: "CÀI ỨNG DỤNG",
    Push: "CHÉP APK VÀO THƯ MỤC DOWNLOAD",
    Shell: "THIẾT LẬP",
}

INSTALL_HINTS = {
    "INSTALL_FAILED_USER_RESTRICTED": (
        "Máy đang chặn cài qua USB. Xiaomi: bật “Cài đặt qua USB” trong Tùy chọn nhà phát triển; "
        "máy khác: bấm Cho phép/Cài đặt trên điện thoại."
    ),
    "INSTALL_FAILED_ABORTED": "Bị từ chối trên điện thoại — bấm “Cài đặt” khi máy hỏi rồi chạy lại.",
    "INSTALL_FAILED_VERIFICATION_FAILURE": "Bị từ chối trên điện thoại — bấm “Cài đặt” khi máy hỏi rồi chạy lại.",
    "INSTALL_FAILED_INSUFFICIENT_STORAGE": "Bộ nhớ điện thoại không đủ.",
    "INSTALL_FAILED_UPDATE_INCOMPATIBLE": "Máy đã có bản app khác chữ ký — gỡ bản cũ trước rồi chạy lại.",
    "INSTALL_FAILED_VERSION_DOWNGRADE": "Máy đã có phiên bản mới hơn — có thể bỏ qua.",
    "INSTALL_FAILED_NO_MATCHING_ABIS": "APK không hợp kiến trúc CPU của máy.",
    "INSTALL_FAILED_OLDER_SDK": "Android trên máy quá cũ so với APK.",
    "INSTALL_FAILED_ALREADY_EXISTS": "Ứng dụng đã có trên máy.",
}
CORRUPT_HINT = "Dữ liệu APK bên trong tool bị hỏng — hãy tải lại file tool."


def install_hint(code: str) -> str:
    if code.startswith("INSTALL_PARSE_FAILED"):
        return "File APK bị hỏng hoặc không hợp lệ."
    return INSTALL_HINTS.get(code, "")


@dataclass
class Failure:
    label: str
    reason: str
    hint: str = ""


@dataclass
class Summary:
    profile_id: str
    profile_name: str
    serial: str
    removed: int = 0
    disabled: int = 0
    installed: int = 0
    pushed: int = 0
    configured: int = 0
    skipped: int = 0
    failures: list[Failure] = field(default_factory=list)
    elapsed_s: float = 0.0
    cancelled: bool = False
    aborted: str = ""
    disconnected_ok: bool = False
    post_note: str = ""

    @property
    def failed(self) -> int:
        return len(self.failures)

    @property
    def ok(self) -> bool:
        return not self.cancelled and not self.aborted and not self.failures


@dataclass
class _Context:
    serial: str
    features: frozenset[str]
    installed: set[str] | None  # None = unknown, never skip
    disabled: set[str]


class _Rate:
    """Smoothed transfer rate and ETA for one file."""

    def __init__(self) -> None:
        self.started = self._last_t = time.monotonic()
        self._last_bytes = 0
        self.bps = 0.0

    def update(self, done: int, total: int) -> tuple[float, float, float | None]:
        now = time.monotonic()
        elapsed = now - self._last_t
        if elapsed >= 0.25:
            current = (done - self._last_bytes) / elapsed
            self.bps = current if self.bps == 0 else 0.7 * self.bps + 0.3 * current
            self._last_t, self._last_bytes = now, done
        eta = (total - done) / self.bps if self.bps > 0 else None
        return (done / total if total else 1.0), self.bps, eta


def _basename(apk: str) -> str:
    return PurePosixPath(apk).name


def _mb(size: int) -> str:
    return f"{size / 1048576:.1f} MB".replace(".", ",")


def _parse_packages(output: str) -> set[str]:
    return {line.strip()[8:] for line in output.splitlines() if line.strip().startswith("package:")}


def _not_present(output: str) -> bool:
    """Package manager answers for a package that does not exist for user 0 (not a real failure)."""
    text = output.lower()
    return "not installed for" in text or "unknown package" in text or "doesn't exist" in text


class JobRunner:
    def __init__(self, client: AdbClient, store: ResourceStore, bus: EventBus) -> None:
        self.client = client
        self.store = store
        self.bus = bus

    # -- device info ----------------------------------------------------------------------------
    def read_info(self, serial: str) -> DeviceInfo | None:
        log = Logger(self.bus, INFO_JOB)
        progress = Progress(self.bus, INFO_JOB, "Đọc thông tin thiết bị")
        progress.state(JobState.RUNNING)
        progress.update(0.15, "Đang đọc thông số máy…", force=True)
        try:
            info = collect_device_info(self.client, serial)
        except Exception as exc:  # noqa: BLE001 - always end the job with a state the UI can show
            log.error(f"Không đọc được thông tin máy {serial}: {exc}")
            progress.state(JobState.FAILED, message=str(exc))
            return None
        self.bus.emit(DeviceInfoEvent(serial, info))
        progress.update(1.0, info.display_name, force=True)
        progress.state(JobState.SUCCESS, summary=info)
        log.ok(f"Thiết bị: {info.display_name} · Android {info.android} · {info.rom or info.build}")
        return info

    # -- profile ---------------------------------------------------------------------------------
    def weight(self, step: Step) -> float:
        if isinstance(step, Install | Push):
            return 1.0 + self.store.size(step.apk) / BYTES_PER_WEIGHT
        if isinstance(step, InstallMulti):
            return 1.0 + sum(self.store.size(a) for a in step.apks) / BYTES_PER_WEIGHT
        return 1.0

    def run_profile(self, serial: str, profile: Profile, cancel: threading.Event) -> Summary:
        log = Logger(self.bus, PROFILE_JOB)
        progress = Progress(self.bus, PROFILE_JOB, profile.name)
        summary = Summary(profile.id, profile.name, serial, post_note=profile.post_note)
        started = time.monotonic()
        progress.state(JobState.RUNNING)
        progress.update(0.0, "Chuẩn bị…", 0, len(profile.steps), force=True)
        log.step(f"{profile.name.upper()} · {serial} · {len(profile.steps)} bước")
        steps = profile.steps
        done_weight = 0.0
        try:
            ctx = self._preflight(serial, log)
            try:
                weights = [self.weight(s) for s in steps]
            except PayloadError as exc:
                raise AdbError(f"Thiếu dữ liệu APK bên trong tool ({exc}) — hãy tải lại file tool.") from exc
            total_weight = sum(weights)
            group = None
            for index, (step, weight) in enumerate(zip(steps, weights, strict=True), start=1):
                if cancel.is_set():
                    summary.cancelled = True
                    break
                if STEP_GROUPS[type(step)] != group:
                    group = STEP_GROUPS[type(step)]
                    log.step(group)
                label = self._label(step)
                base = done_weight

                def on_fraction(frac, bps, eta, base=base, weight=weight, label=label, index=index):
                    progress.update(
                        (base + frac * weight) / total_weight, label, index, len(steps),
                        sub_fraction=frac, rate_bps=bps, eta_s=eta,
                    )

                progress.update(base / total_weight, label, index, len(steps), force=True)
                try:
                    self._run_step(step, ctx, summary, log, cancel, on_fraction)
                except Cancelled:
                    summary.cancelled = True
                    break
                except DeviceGoneError as exc:
                    # A broken stream or a timeout is not always a lost phone (e.g. a failed install
                    # that closed early): keep going, like the batch file, if the phone is still here.
                    if not self._device_present(serial):
                        raise
                    summary.failures.append(Failure(label, str(exc), "Kết nối bị ngắt giữa chừng — thử lại bước này"))
                    log.error(f"{label} thất bại — {exc}")
                done_weight += weight
        except Cancelled:
            summary.cancelled = True
        except DeviceGoneError as exc:
            summary.aborted = f"Mất kết nối với điện thoại ({exc})"
        except AdbError as exc:
            summary.aborted = str(exc)
        except Exception as exc:  # noqa: BLE001 - the job must always end with a reported state
            summary.aborted = f"Lỗi không mong đợi: {type(exc).__name__}: {exc}"
        summary.elapsed_s = time.monotonic() - started
        return self._finish(summary, progress, log, len(steps))

    def _device_present(self, serial: str) -> bool:
        try:
            return any(d.serial == serial and d.ready for d in self.client.devices())
        except AdbError:
            return False

    def _finish(self, summary: Summary, progress: Progress, log: Logger, steps: int) -> Summary:
        minutes, seconds = divmod(int(summary.elapsed_s), 60)
        counts = (
            f"gỡ {summary.removed}, tắt {summary.disabled}, cài {summary.installed}, chép {summary.pushed}, "
            f"thiết lập {summary.configured}, bỏ qua {summary.skipped}, lỗi {summary.failed}"
        )
        if summary.cancelled:
            log.warn(f"Đã dừng theo yêu cầu sau {minutes}:{seconds:02d} — {counts}")
            progress.state(JobState.CANCELLED, summary)
        elif summary.aborted:
            log.error(f"Dừng giữa chừng: {summary.aborted} — {counts}")
            progress.state(JobState.FAILED, summary, summary.aborted)
        else:
            if summary.disconnected_ok:
                log.info("Đã tắt gỡ lỗi USB trên điện thoại — máy sẽ ngắt kết nối với tool.")
            if summary.failures:
                log.warn(f"Hoàn tất sau {minutes}:{seconds:02d} (có {summary.failed} lỗi) — {counts}")
            else:
                log.ok(f"Hoàn tất sau {minutes}:{seconds:02d} — {counts}")
            progress.update(1.0, "Hoàn tất", steps, steps, force=True)
            progress.state(JobState.SUCCESS, summary)
        return summary

    def _preflight(self, serial: str, log: Logger) -> _Context:
        entry = next((d for d in self.client.devices() if d.serial == serial), None)
        if entry is None:
            raise DeviceGoneError("không tìm thấy điện thoại — hãy cắm lại cáp")
        if entry.state == "unauthorized":
            raise AdbError("Điện thoại chưa cho phép gỡ lỗi USB — mở khoá màn hình và bấm Cho phép (Allow)")
        if not entry.ready:
            raise AdbError(f"Điện thoại chưa sẵn sàng (trạng thái: {entry.state}) — rút cáp ra cắm lại")
        features = self.client.features(serial)
        listing = self.client.shell(serial, "pm list packages --user 0", features=features)
        installed = _parse_packages(listing.stdout)
        if not installed:
            installed = _parse_packages(self.client.shell(serial, "pm list packages", features=features).stdout)
        disabled = _parse_packages(
            self.client.shell(serial, "pm list packages -d --user 0", features=features).stdout
        )
        if installed:
            log.info(f"Máy đang có {len(installed)} ứng dụng (user 0)")
        else:
            log.warn("Không đọc được danh sách ứng dụng — sẽ chạy đủ mọi lệnh như bản .bat")
        return _Context(serial, features, installed or None, disabled)

    @staticmethod
    def _label(step: Step) -> str:
        if isinstance(step, Uninstall):
            return f"Gỡ {step.pkg}"
        if isinstance(step, Disable):
            return f"Tắt {step.pkg}"
        if isinstance(step, Install):
            return f"Cài {_basename(step.apk)}"
        if isinstance(step, InstallMulti):
            return f"Cài {step.label}"
        if isinstance(step, Push):
            return f"Chép {_basename(step.apk)}"
        return step.label

    def _run_step(self, step, ctx, summary, log, cancel, on_fraction) -> None:
        if isinstance(step, Uninstall):
            self._uninstall(step, ctx, summary, log)
        elif isinstance(step, Disable):
            self._disable(step, ctx, summary, log)
        elif isinstance(step, Install | InstallMulti | Push):
            self._transfer(step, ctx, summary, log, cancel, on_fraction)
        elif isinstance(step, Shell):
            self._shell(step, ctx, summary, log)

    def _shell_out(self, ctx: _Context, cmd: str):
        return self.client.shell(ctx.serial, cmd, features=ctx.features)

    def _uninstall(self, step: Uninstall, ctx: _Context, summary: Summary, log: Logger) -> None:
        if ctx.installed is not None and step.pkg not in ctx.installed:
            summary.skipped += 1
            log.skip(f"Bỏ qua {step.pkg} — không có trên máy")
            return
        result = self._shell_out(ctx, f"pm uninstall -k --user 0 {shlex.quote(step.pkg)}")
        if "Success" in result.output:
            summary.removed += 1
            if ctx.installed is not None:
                ctx.installed.discard(step.pkg)
            log.ok(f"Đã gỡ {step.pkg}")
        elif _not_present(result.output):
            summary.skipped += 1
            log.skip(f"Bỏ qua {step.pkg} — không có trên máy")
        else:
            summary.failures.append(Failure(f"Gỡ {step.pkg}", result.output or f"exit {result.exit_code}"))
            log.error(f"Không gỡ được {step.pkg} — {result.output}")

    def _disable(self, step: Disable, ctx: _Context, summary: Summary, log: Logger) -> None:
        if ctx.installed is not None and step.pkg not in ctx.installed:
            summary.skipped += 1
            log.skip(f"Bỏ qua {step.pkg} — không có trên máy")
            return
        if step.pkg in ctx.disabled:
            summary.skipped += 1
            log.skip(f"Bỏ qua {step.pkg} — đã tắt sẵn")
            return
        result = self._shell_out(ctx, f"pm disable-user --user 0 {shlex.quote(step.pkg)}")
        if result.ok and "disabled" in result.output:
            summary.disabled += 1
            ctx.disabled.add(step.pkg)
            log.ok(f"Đã tắt {step.pkg}")
        elif _not_present(result.output):
            summary.skipped += 1
            log.skip(f"Bỏ qua {step.pkg} — không có trên máy")
        else:
            summary.failures.append(Failure(f"Tắt {step.pkg}", result.output or f"exit {result.exit_code}"))
            log.error(f"Không tắt được {step.pkg} — {result.output}")

    def _shell(self, step: Shell, ctx: _Context, summary: Summary, log: Logger) -> None:
        if step.requires_pkg:
            check = self._shell_out(ctx, f"pm path {shlex.quote(step.requires_pkg)}")
            if "package:" not in check.output:
                summary.skipped += 1
                log.skip(f"Bỏ qua: {step.label} — máy chưa có {step.requires_pkg}")
                return
        if step.may_disconnect and not self._device_present(ctx.serial):
            # a phone that is already gone did not have USB debugging turned off by us
            raise DeviceGoneError("điện thoại đã ngắt kết nối trước bước cuối")
        try:
            result = self._shell_out(ctx, step.cmd)
        except DeviceGoneError:
            if not step.may_disconnect:
                raise
            summary.configured += 1
            summary.disconnected_ok = True
            log.ok(step.label)
            return
        if result.ok:
            summary.configured += 1
            if step.may_disconnect:
                summary.disconnected_ok = True
            log.ok(step.label + (f" — {result.output}" if result.output else ""))
        else:
            summary.failures.append(Failure(step.label, result.output or f"exit {result.exit_code}"))
            log.error(f"{step.label} thất bại — {result.output}")

    def _transfer(self, step, ctx: _Context, summary: Summary, log: Logger, cancel, on_fraction) -> None:
        apks = step.apks if isinstance(step, InstallMulti) else (step.apk,)
        sizes = [self.store.size(a) for a in apks]
        total = sum(sizes)
        label = self._label(step)
        rate = _Rate()

        def on_progress(done: int, _total: int) -> None:
            on_fraction(*rate.update(done, total))

        started = time.monotonic()
        try:
            with contextlib.ExitStack() as stack:
                streams = [stack.enter_context(self.store.open(a)) for a in apks]
                if isinstance(step, Install):
                    self.client.install(
                        ctx.serial, streams[0], sizes[0], _basename(step.apk), on_progress=on_progress,
                        cancel=cancel, features=ctx.features,
                    )
                elif isinstance(step, InstallMulti):
                    parts = [(_basename(a), s, n) for a, s, n in zip(apks, streams, sizes, strict=True)]
                    self.client.install_multiple(
                        ctx.serial, parts, on_progress=on_progress, cancel=cancel, features=ctx.features
                    )
                else:
                    remote = step.dest.rstrip("/") + "/" + _basename(step.apk)
                    self.client.push(ctx.serial, streams[0], sizes[0], remote, on_progress=on_progress, cancel=cancel)
        except InstallError as exc:
            hint = install_hint(exc.code)
            reason = exc.raw or str(exc)
            summary.failures.append(Failure(label, reason, hint))
            log.error(f"{label} thất bại — {reason}")
            if hint:
                log.warn(f"Gợi ý: {hint}")
            return
        except (CorruptMemberError, PayloadError, zipfile.BadZipFile) as exc:
            summary.failures.append(Failure(label, str(exc), CORRUPT_HINT))
            log.error(f"{label} thất bại — {CORRUPT_HINT}")
            return
        except AdbError as exc:
            if isinstance(exc, DeviceGoneError):
                raise
            summary.failures.append(Failure(label, str(exc)))
            log.error(f"{label} thất bại — {exc}")
            return
        seconds = max(time.monotonic() - started, 0.001)
        speed = _mb(int(total / seconds)) + "/s"
        if isinstance(step, Push):
            summary.pushed += 1
            log.ok(f"Đã chép {_basename(step.apk)} vào Download ({_mb(total)}, {seconds:.1f}s, {speed})")
        else:
            summary.installed += 1
            log.ok(f"Đã cài {label[4:]} ({_mb(total)}, {seconds:.1f}s, {speed})")
