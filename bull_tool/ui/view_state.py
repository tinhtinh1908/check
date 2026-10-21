"""Pure UI decisions (no Flet): device and profile selection, info reads, start-button gating, run warnings."""

from __future__ import annotations

from dataclasses import dataclass, field

from bull_tool.core.adb.client import DeviceEntry
from bull_tool.core.device_info import DeviceInfo, match_profile
from bull_tool.core.profiles import PROFILE_BY_ID

PROFILE_JOB = "profile"
FIX_JOB = "fix"
DRIVER_JOB = "driver"
EXCLUSIVE_JOBS = frozenset({PROFILE_JOB, FIX_JOB, DRIVER_JOB})


@dataclass
class ViewState:
    bootstrap_ready: bool = False
    adb_up: bool | None = None
    devices: tuple[DeviceEntry, ...] = ()
    seen_serials: frozenset[str] = frozenset()  # phones listed since the phone list was last empty
    selected_serial: str | None = None
    preferred_serial: str | None = None  # the phone the user means; an automatic fallback does not change it
    infos: dict[str, DeviceInfo] = field(default_factory=dict)
    selected_profile: str | None = None
    suggested_profile: str | None = None
    # (serial, adb model, profile id) of the phone the card was picked for; the model tells apart cheap phones
    # that all report the same serial
    manual_pick: tuple[str | None, str, str] | None = None
    job: str | None = None
    job_serial: str | None = None
    stopping: bool = False
    reading_serial: str | None = None

    @property
    def busy(self) -> bool:
        return self.job in EXCLUSIVE_JOBS

    def entry(self, serial: str | None = None) -> DeviceEntry | None:
        serial = serial or self.selected_serial
        return next((d for d in self.devices if d.serial == serial), None)


def choose_serial(
    devices: tuple[DeviceEntry, ...], current: str | None, job_serial: str | None, preferred: str | None = None
) -> str | None:
    """Keep the job phone, then the user's phone, then the current one while present; else the first ready one."""
    serials = [d.serial for d in devices]
    for keep in (job_serial, preferred, current):
        if keep and keep in serials:
            return keep
    ready = [d.serial for d in devices if d.ready]
    return (ready or serials or [None])[0]


def next_preferred(
    previous: str | None, selected: str | None, preferred: str | None, seen: frozenset[str] = frozenset()
) -> str | None:
    """A phone that appears on an empty panel becomes the user's phone; an automatic fallback swap does not.

    ``seen`` holds the phones listed since the list was last empty. A phone that was plugged in alongside the
    user's phone is not adopted when it comes back first (adb restart, connection fix, hub glitch: phones
    return one by one), so the user's phone is restored when it reappears and Start keeps asking until then.
    """
    if previous is None and selected is not None and (preferred is None or selected not in seen):
        return selected
    return preferred


def suggest_profile(info: DeviceInfo | None) -> str | None:
    return match_profile(info.brand, info.manufacturer) if info else None


def auto_profile(state: ViewState) -> str | None:
    """Profile the grid should switch to, or None to leave it: the user's pick for the selected phone
    (kept while that phone is unplugged and plugged back), otherwise the phone's brand suggestion."""
    if state.busy:
        return None
    pick, entry = state.manual_pick, state.entry()
    # the same phone: same serial, and the adb model does not contradict it (unknown while unauthorized)
    same_phone = bool(pick) and pick[0] == state.selected_serial and not (
        pick[1] and entry is not None and entry.model and entry.model != pick[1]
    )
    target = pick[2] if same_phone else suggest_profile(state.infos.get(state.selected_serial or ""))
    return target if target and target != state.selected_profile else None


def info_read_target(state: ViewState, error_serial: str | None) -> str | None:
    """Serial whose details should be read now: the selected ready phone without details, one read at a time.
    ``error_serial`` is the phone whose last read failed; it waits for the user's refresh instead."""
    entry = state.entry()
    if not state.bootstrap_ready or state.reading_serial is not None or entry is None or not entry.ready:
        return None
    if entry.serial in state.infos or entry.serial == error_serial:
        return None
    return entry.serial


def start_block_reason(state: ViewState) -> str:
    """Empty string when the Start button may run; otherwise the reason shown as its tooltip."""
    if state.job == PROFILE_JOB:
        return ""  # the button acts as Stop
    if not state.bootstrap_ready:
        return "Đang khởi động tool…"
    if state.busy:
        return "Đang có tác vụ khác chạy"
    entry = state.entry()
    if entry is None:
        return "Chưa có điện thoại kết nối"
    if not entry.ready:
        return "Điện thoại chưa sẵn sàng (chưa cho phép gỡ lỗi USB?)"
    if state.reading_serial is not None and entry.serial not in state.infos:
        return "Đang đọc thông tin máy…"  # the brand, and so the suggested profile, is not known yet
    if state.selected_profile not in PROFILE_BY_ID:
        return "Chọn dòng máy trước"
    return ""


def _phone_name(state: ViewState, serial: str) -> str:
    """Name the panel shows for a phone: its marketing name once read, else the adb model, else the serial."""
    info = state.infos.get(serial)
    if info is not None:
        return info.display_name
    entry = state.entry(serial)
    return (entry.model.replace("_", " ") if entry else "") or serial


def target_warning(state: ViewState) -> str:
    """Message for the confirmation dialog when the user's phone is gone and another one was selected instead."""
    serial, preferred = state.selected_serial, state.preferred_serial
    if serial is None or preferred is None or serial == preferred:
        return ""
    return (f"Máy đã chọn trước đó ({preferred}) không còn kết nối. "
            f"Tool sẽ chạy trên máy {_phone_name(state, serial)} ({serial}).")


def brand_warning(state: ViewState) -> str:
    """Message for the confirmation dialog when the chosen profile may not fit the plugged-in phone."""
    info = state.infos.get(state.selected_serial or "")
    profile = PROFILE_BY_ID.get(state.selected_profile or "")
    if profile is None:
        return ""
    if info is None:
        name = _phone_name(state, state.selected_serial or "")
        return f"Chưa đọc được hãng của máy {name}. Vẫn chạy cấu hình “{profile.name}”?"
    suggested = suggest_profile(info)
    phone = f"{info.brand} {info.display_name}".strip()
    if suggested is None:
        return (f"Tool không nhận ra hãng “{info.brand}” của máy {info.display_name}. "
                f"Chạy cấu hình “{profile.name}” có thể gỡ nhầm ứng dụng.")
    if suggested != profile.id:
        return (f"Máy đang cắm là {phone}, nhưng bạn chọn “{profile.name}”. "
                f"Chạy sai dòng máy có thể gỡ nhầm ứng dụng của máy.")
    return ""
