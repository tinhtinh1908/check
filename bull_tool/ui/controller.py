"""Application controller: builds the UI, routes bus events to components and runs jobs off the UI loop.

Every control mutation happens on the page event loop (UI pump callbacks and async event handlers);
blocking work runs in worker threads and reports back through the EventBus.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import flet as ft

from bull_tool.core.bootstrap import BOOT_JOB, AppServices, run_bootstrap
from bull_tool.core.connection_fixer import find_running, fix_connection
from bull_tool.core.driver_installer import DriverResult, install_driver
from bull_tool.core.events import (
    DeviceInfoEvent,
    DevicesEvent,
    JobState,
    JobStateEvent,
    Logger,
    Progress,
    ProgressEvent,
    StatusEvent,
)
from bull_tool.core.job_runner import INFO_JOB
from bull_tool.core.profiles import PROFILE_BY_ID, PROFILES
from bull_tool.core.settings import save_settings
from bull_tool.ui import dialogs
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W
from bull_tool.ui.console_view import ConsoleView
from bull_tool.ui.contact_card import ContactCards
from bull_tool.ui.device_panel import DevicePanel
from bull_tool.ui.profile_grid import ProfileGrid
from bull_tool.ui.progress_panel import ProgressPanel
from bull_tool.ui.shell_layout import ShellLayout
from bull_tool.ui.status_bar import StatusBar
from bull_tool.ui.title_bar import TitleBar
from bull_tool.ui.tools_panel import ToolsPanel
from bull_tool.ui.ui_pump import LOGS, UiPump
from bull_tool.ui.view_state import (
    DRIVER_JOB,
    EXCLUSIVE_JOBS,
    FIX_JOB,
    PROFILE_JOB,
    ViewState,
    auto_profile,
    brand_warning,
    choose_serial,
    info_read_target,
    next_preferred,
    start_block_reason,
    suggest_profile,
    target_warning,
)

GUIDE_INDEX = {"xiaomi": 0, "oppo": 1, "honor": 2, "vivo": 3}
JOB_STOP_WAIT = 10.0  # seconds the exit path gives a cancelled job to reach its next checkpoint
BUSY_MESSAGE = "Hãy đợi tool khởi động xong / tác vụ hiện tại kết thúc"


async def run_in_daemon(name: str, work: Callable[[], Any]) -> Any:
    """Run blocking job work on a daemon thread and await its result.

    asyncio.to_thread's pool threads are joined at interpreter exit, so a job still unwinding after the window
    closed would keep an invisible process alive (and the single-instance lock held).
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def settle(setter: Callable[[Any], None], value: Any) -> None:
        if not future.done():
            setter(value)

    def run() -> None:
        try:
            outcome = (future.set_result, work())
        except BaseException as exc:  # noqa: BLE001 - re-raised in the awaiting task
            outcome = (future.set_exception, exc)
        try:
            loop.call_soon_threadsafe(settle, *outcome)
        except RuntimeError:  # the loop is already closed: the app is exiting
            pass

    threading.Thread(target=run, name=name, daemon=True).start()
    return await future


class AppController:
    def __init__(
        self, page: ft.Page, services: AppServices, bootstrap: Callable[[AppServices], bool] = run_bootstrap
    ) -> None:
        self.page = page
        self.services = services
        self.bus = services.bus
        self._bootstrap = bootstrap
        self.state = ViewState()
        self.pump = UiPump(page, self.bus)
        self.clipboard = ft.Clipboard()
        self.file_picker = ft.FilePicker()
        self.url_launcher = ft.UrlLauncher()
        self.cancel: threading.Event | None = None  # stops the running profile or connection-fix job
        self._panel_key: tuple | None = None
        self._pulse = False
        self._resize_generation = 0
        self._closing = False
        self._close_prompt: ft.AlertDialog | None = None
        self._fix_prompting = False
        self._log_error_reported = False
        self._tools_revision = ""
        self._adb_detail = ""

        self.start_button, self._start_label, self._start_icon = W.gradient_button(
            "BẮT ĐẦU", ft.Icons.PLAY_ARROW_ROUNDED, self._on_start_click, height=52
        )
        self.start_button.width = 168
        self.title_bar = TitleBar(self._toggle_theme, self._minimize, self._maximize, self._close_click)
        self.title_bar.set_dark(page.theme_mode == ft.ThemeMode.DARK)
        self.status_bar = StatusBar(self.open_url)
        self.device_panel = DevicePanel(
            self._refresh_device, self._copy_device_info, self._select_device, self._show_guide, self._on_fix_click
        )
        self.profile_grid = ProfileGrid(PROFILES, self._pick_profile)
        self.tools = ToolsPanel(self._show_guide, self._on_fix_click, self._on_driver_click)
        self.contacts = ContactCards(self.open_url)
        self.progress = ProgressPanel(self.start_button)
        self.console = ConsoleView(self.pump.mark_dirty, self._copy_text, self._save_log)
        self.shell = ShellLayout(
            self.title_bar.root,
            self.status_bar.root,
            [self.device_panel.root, self.tools.root, *self.contacts.controls],
            [self.profile_grid.root, self.progress.root],
            self.console.root,
        )
        self._components_with_layout = [
            self.title_bar, self.device_panel, self.profile_grid, self.progress, self.contacts,
        ]

    # -- lifecycle -----------------------------------------------------------------------------------
    def build(self) -> ft.Control:
        return self.shell.root

    def start(self) -> None:
        self.pump.on(LOGS, self.console.append)
        self.pump.on(ProgressEvent, self._on_progress)
        self.pump.on(JobStateEvent, self._on_job_state)
        self.pump.on(DevicesEvent, self._on_devices)
        self.pump.on(DeviceInfoEvent, self._on_device_info)
        self.pump.on(StatusEvent, self._on_status)
        self.pump.after_flush(self.console.scroll_if_needed)
        self.pump.start()
        self.page.run_task(self._heartbeat)
        self._dirty(*self.progress.begin(BOOT_JOB, "Khởi động"))
        self._refresh_actions()
        threading.Thread(target=self._bootstrap, args=(self.services,), name="bootstrap", daemon=True).start()

    def apply_layout(self, width: float, height: float) -> None:
        layout = T.compute_layout(width, height)
        self.shell.apply(layout)
        for component in self._components_with_layout:
            component.apply_layout(layout)
        self.console.set_font_size(layout.console_size)
        self.start_button.height = 44 if layout.short else 52
        self.start_button.width = 148 if layout.main_width < 760 else 168

    async def on_resize(self, e: ft.PageResizeEvent) -> None:
        self._resize_generation += 1
        generation = self._resize_generation
        await asyncio.sleep(0.12)  # debounce while the user drags the border
        if generation != self._resize_generation:
            return
        self.apply_layout(e.width, e.height)
        self.page.update()

    async def on_window_event(self, e: ft.WindowEvent) -> None:
        if e.type == ft.WindowEventType.CLOSE:
            await self._request_close()
        elif e.type in (ft.WindowEventType.MAXIMIZE, ft.WindowEventType.UNMAXIMIZE):
            self._dirty(*self.title_bar.set_maximized(e.type == ft.WindowEventType.MAXIMIZE))

    async def on_session_closed(self, _e=None) -> None:
        """The client went away without the close flow (crashed or killed): stop the job and release adb.

        After a normal exit this runs once the window is gone and everything is already shut down.
        """
        self._closing = True
        self.services.begin_close()
        if self.cancel is not None:
            self.cancel.set()
        self.pump.stop()
        await asyncio.to_thread(self.services.shutdown)

    async def _heartbeat(self) -> None:
        while not self._closing:
            await asyncio.sleep(0.9)
            self._pulse = not self._pulse
            self._dirty(*self.device_panel.pulse(self._pulse))

    # -- helpers --------------------------------------------------------------------------------------
    def _dirty(self, *controls: ft.Control) -> None:
        self.pump.mark_dirty(*controls)

    def open_url(self, url: str) -> None:
        self.page.run_task(self.url_launcher.launch_url, url)

    def _toast_busy(self) -> None:
        if not self._closing:
            dialogs.toast(self.page, BUSY_MESSAGE, T.WARNING, ft.Icons.INFO_OUTLINE_ROUNDED)

    def _begin_progress(self, job: str, title: str) -> None:
        """Show a job in the progress card unless a more important job owns it."""
        owner = self.progress.job
        owner_running = self.progress.state == JobState.RUNNING
        if job == INFO_JOB and owner_running and owner in (*EXCLUSIVE_JOBS, BOOT_JOB):
            return
        self._dirty(*self.progress.begin(job, title))

    def _end_job(self) -> None:
        state = self.state
        state.job, state.job_serial, state.stopping = None, None, False
        self.cancel = None
        self._update_suggestion()  # a phone read while the job ran gets its brand profile now
        self._refresh_actions()
        if self._close_prompt is not None and not self._closing:
            dialogs.dismiss(self._close_prompt)  # "stop the running job and exit?" no longer applies
            self._close_prompt = None

    def _refresh_actions(self) -> None:
        state = self.state
        reason = start_block_reason(state)
        if state.job == PROFILE_JOB:
            stopping = state.stopping
            self._start_label.value = "ĐANG DỪNG…" if stopping else "DỪNG"
            self._start_icon.icon = ft.Icons.HOURGLASS_TOP_ROUNDED if stopping else ft.Icons.STOP_ROUNDED
            W.style_cta(self.start_button, self._start_label, self._start_icon, not stopping,
                        T.DANGER_GRADIENT, T.DANGER)
            self.start_button.tooltip = "Dừng sau bước hiện tại (dừng ngay nếu đang chép file)"
        else:
            self._start_label.value = "BẮT ĐẦU"
            self._start_icon.icon = ft.Icons.PLAY_ARROW_ROUNDED
            W.style_cta(self.start_button, self._start_label, self._start_icon, not reason and not self._closing)
            self.start_button.tooltip = reason or "Chạy dọn rác + cài ứng dụng cho dòng máy đã chọn"
        locked = state.busy or not state.bootstrap_ready
        self._dirty(
            self.start_button,
            *self.profile_grid.set_enabled(state.job != PROFILE_JOB),
            *self.tools.set_busy(locked),
            *self.device_panel.set_busy(locked),
        )

    # -- bus events -------------------------------------------------------------------------------------
    def _on_progress(self, event: ProgressEvent) -> None:
        self._dirty(*self.progress.show(event))

    def _on_job_state(self, event: JobStateEvent) -> None:
        if event.state != JobState.RUNNING:
            self._dirty(*self.progress.finish(event.job, event.state, event.message))
        if event.job == INFO_JOB and event.state != JobState.RUNNING:
            # reads run one at a time, so the read that just ended is the one reading_serial names
            serial = self.state.reading_serial
            self.state.reading_serial = None
            if event.state == JobState.FAILED and serial and serial == self.state.selected_serial:
                self._panel_key = ("error", serial)
                self._dirty(*self.device_panel.show_error(
                    "Không đọc được thông tin máy", (event.message or "")[:200] + " — bấm nút làm mới để thử lại."))
            self._render_device()  # starts the read a newly selected phone waits for; refreshes Start

    def _on_devices(self, event: DevicesEvent) -> None:
        state = self.state
        previous = state.selected_serial
        was_empty = not state.devices
        state.devices = event.devices
        present = {d.serial for d in event.devices}
        for serial in [s for s in state.infos if s not in present]:
            del state.infos[serial]  # unplugged: read fresh details next time
        state.selected_serial = choose_serial(event.devices, previous, state.job_serial, state.preferred_serial)
        state.preferred_serial = next_preferred(
            previous, state.selected_serial, state.preferred_serial, state.seen_serials
        )
        if event.devices:
            state.seen_serials = frozenset(present) if was_empty else state.seen_serials | present
        self._render_device()

    def _on_device_info(self, event: DeviceInfoEvent) -> None:
        state = self.state
        state.infos[event.serial] = event.info
        if event.serial == state.selected_serial:
            self._panel_key = None
            self._render_device()

    def _on_status(self, event: StatusEvent) -> None:
        state = self.state
        if event.key == "tools":
            self._dirty(*self.status_bar.set_adb(state.adb_up, event.value))
            self._tools_revision = event.value
        elif event.key == "adb":
            state.adb_up = event.value == "up"
            self._adb_detail = event.detail
            self._dirty(*self.status_bar.set_adb(state.adb_up, self._tools_revision))
            self._render_device()
        elif event.key == "driver":
            ok = event.value == "ok"
            self._dirty(*self.tools.set_driver(ok), *self.status_bar.set_driver(ok))
        elif event.key == "bootstrap":
            if event.value == "ready":
                state.bootstrap_ready = True
                self._panel_key = None
                self._render_device()
            elif event.value == "fatal":
                self._panel_key = ("fatal",)
                self._dirty(*self.device_panel.show_error("Không khởi động được tool", event.detail))
                dialogs.show_message(self.page, "Không khởi động được tool", event.detail)
            self._refresh_actions()
        elif event.key == "log" and not self._log_error_reported:
            self._log_error_reported = True
            dialogs.toast(self.page, "Không ghi được file log phiên (console vẫn hoạt động)", T.WARNING,
                          ft.Icons.WARNING_AMBER_ROUNDED)

    # -- device panel rendering ---------------------------------------------------------------------------
    def _render_device(self) -> None:
        state = self.state
        entry = state.entry()
        dirty = list(self.device_panel.set_devices(state.devices, state.selected_serial, state.busy))
        if not state.bootstrap_ready:
            key: tuple = ("starting",)
            pill = (T.TEXT_MUTED, "Đang khởi động…")
        elif state.adb_up is False and not state.devices:
            key = ("adb_down",)
            pill = (T.DANGER, "ADB mất kết nối")
        elif entry is None:
            key = ("no_device",)
            pill = (T.TEXT_MUTED, "Chưa có thiết bị")
        elif entry.state == "unauthorized":
            key = ("unauthorized", entry.serial)
            pill = (T.WARNING, "Chờ cho phép gỡ lỗi USB")
        elif not entry.ready:
            key = ("other", entry.serial, entry.state)
            pill = (T.WARNING, f"Thiết bị: {entry.state}")
        else:
            info = state.infos.get(entry.serial)
            name = info.display_name if info else (entry.model.replace("_", " ") or entry.serial)
            pill = (T.SUCCESS, f"{name} · Đã kết nối")
            key = ("ready", entry.serial) if info else ("reading", entry.serial)
            failed = self._panel_key[1] if self._panel_key and self._panel_key[0] == "error" else None
            target = info_read_target(state, failed)
            if target:
                self._start_read_info(target)
            if self._panel_key == ("error", entry.serial):
                key = self._panel_key
        if key != self._panel_key:
            self._panel_key = key
            kind = key[0]
            if kind == "starting":
                dirty += self.device_panel.show_starting()
            elif kind == "adb_down":
                dirty += self.device_panel.show_adb_down(self._adb_detail)
            elif kind == "no_device":
                dirty += self.device_panel.show_no_device()
            elif kind == "unauthorized":
                dirty += self.device_panel.show_unauthorized(entry)
            elif kind == "other":
                dirty += self.device_panel.show_other_state(entry)
            elif kind == "reading":
                dirty += self.device_panel.show_reading(entry)
            elif kind == "ready":
                dirty += self.device_panel.show_info(state.infos[entry.serial])
        dirty += self.title_bar.set_device(*pill)
        self._update_suggestion()
        self._dirty(*dirty)
        self._refresh_actions()

    def _update_suggestion(self) -> None:
        state = self.state
        suggested = suggest_profile(state.infos.get(state.selected_serial or ""))
        if suggested != state.suggested_profile:
            state.suggested_profile = suggested
            self._dirty(*self.profile_grid.set_suggested(suggested))
        target = auto_profile(state)
        if target:
            state.selected_profile = target
            self._dirty(*self.profile_grid.set_selected(target))

    def _start_read_info(self, serial: str) -> None:
        runner = self.services.runner
        if runner is None:
            return
        self.state.reading_serial = serial
        self._begin_progress(INFO_JOB, "Đọc thông tin thiết bị")
        threading.Thread(target=runner.read_info, args=(serial,), name="read-info", daemon=True).start()

    # -- user actions -----------------------------------------------------------------------------------
    async def _refresh_device(self, _e) -> None:
        state = self.state
        if state.busy or not state.bootstrap_ready or self._closing:
            return
        if state.selected_serial:
            state.infos.pop(state.selected_serial, None)
        self._panel_key = None
        self._render_device()
        await self.pump.flush()

    async def _select_device(self, e: ft.ControlEvent) -> None:
        if self.state.busy or self._closing:
            return
        self.state.selected_serial = self.state.preferred_serial = e.control.value
        self._panel_key = None
        self._render_device()
        await self.pump.flush()

    async def _pick_profile(self, profile_id: str) -> None:
        state = self.state
        if state.job == PROFILE_JOB or profile_id not in PROFILE_BY_ID or self._closing:
            return
        state.selected_profile = profile_id
        entry = state.entry()
        state.manual_pick = (state.selected_serial, entry.model if entry else "", profile_id)
        self._dirty(*self.profile_grid.set_selected(profile_id))
        self._refresh_actions()
        await self.pump.flush()

    async def _show_guide(self, _e=None) -> None:
        dialogs.show_guide(self.page, GUIDE_INDEX.get(self.state.suggested_profile or "", 0))

    async def _copy_device_info(self, _e) -> None:
        info = self.state.infos.get(self.state.selected_serial or "")
        if info:
            await self._copy_text(info.as_text(), "Đã sao chép thông tin máy")

    async def _copy_text(self, text: str, message: str = "Đã sao chép toàn bộ log") -> None:
        await self.clipboard.set(text)
        dialogs.toast(self.page, message)

    async def _save_log(self, text: str) -> None:
        path = await self.file_picker.save_file(
            dialog_title="Lưu log BULL TOOL",
            file_name=f"BULL-TOOL-log-{datetime.now():%Y%m%d-%H%M%S}.txt",
            allowed_extensions=["txt"],
        )
        if not path:
            return
        target = Path(path if path.lower().endswith(".txt") else f"{path}.txt")
        try:
            await asyncio.to_thread(target.write_text, text, "utf-8")
            dialogs.toast(self.page, f"Đã lưu log: {target.name}")
        except OSError as exc:
            dialogs.toast(self.page, f"Không lưu được log: {exc}", T.DANGER, ft.Icons.ERROR_OUTLINE_ROUNDED)

    # profile job ------------------------------------------------------------------------------------------
    async def _on_start_click(self, _e) -> None:
        state = self.state
        if self._closing:
            return
        if state.job == PROFILE_JOB:
            if self.cancel is not None and not state.stopping:
                state.stopping = True
                self.cancel.set()
                Logger(self.bus, PROFILE_JOB).warn("Đang dừng theo yêu cầu…")
                self._refresh_actions()
            return
        reason = start_block_reason(state)
        if reason:
            dialogs.toast(self.page, reason, T.WARNING, ft.Icons.INFO_OUTLINE_ROUNDED)
            return
        serial, profile = state.selected_serial, PROFILE_BY_ID[state.selected_profile]
        warning = "\n\n".join(text for text in (target_warning(state), brand_warning(state)) if text)
        if warning:
            dialogs.show_confirm(
                self.page, "Kiểm tra lại trước khi chạy", warning, "Vẫn chạy",
                lambda: self.page.run_task(self._run_profile, serial, profile), danger=True,
            )
            return
        self.page.run_task(self._run_profile, serial, profile)

    async def _run_profile(self, serial: str, profile) -> None:
        state = self.state
        if self._closing:
            return
        if state.busy or self.services.runner is None:
            self._toast_busy()
            return
        # the phone list or the selection may have changed while the confirm dialog was open
        if serial != state.selected_serial or profile.id != state.selected_profile or start_block_reason(state):
            dialogs.toast(self.page, "Máy hoặc dòng máy vừa thay đổi — kiểm tra lại rồi bấm Bắt đầu", T.WARNING,
                          ft.Icons.INFO_OUTLINE_ROUNDED)
            return
        state.job, state.job_serial, state.stopping = PROFILE_JOB, serial, False
        state.preferred_serial = serial
        cancel = self.cancel = threading.Event()
        runner = self.services.runner
        self._begin_progress(PROFILE_JOB, profile.name)
        self._refresh_actions()
        try:
            summary = await run_in_daemon("profile", lambda: runner.run_profile(serial, profile, cancel))
        finally:
            self._end_job()
        if not self._closing:
            dialogs.show_summary(self.page, summary)

    # connection fix -------------------------------------------------------------------------------------------
    async def _on_fix_click(self, _e=None) -> None:
        if self._fix_prompting or self._closing:
            return  # a second click while the first one is still listing the running apps
        if self.state.busy or self.services.server is None:
            self._toast_busy()
            return
        self._fix_prompting = True
        try:
            running = await asyncio.to_thread(find_running)
        finally:
            self._fix_prompting = False
        if self.state.busy or self._closing:
            self._toast_busy()
            return
        details = list(running) or ["(không thấy ứng dụng nào trong danh sách đang chạy)"]
        details.append("Tất cả tiến trình adb.exe (kể cả của tool khác)")
        dialogs.show_confirm(
            self.page, "Sửa lỗi máy tính không nhận điện thoại",
            "Tool sẽ đóng các ứng dụng chiếm ADB/USB sau đây rồi khởi động lại ADB:", "Sửa ngay",
            lambda: self.page.run_task(self._run_fix, running), details=details, icon=ft.Icons.HEALING_ROUNDED,
        )

    async def _run_fix(self, running: list[str]) -> None:
        if self._closing:
            return
        if self.state.busy:
            self._toast_busy()
            return
        self.state.job = FIX_JOB
        cancel = self.cancel = threading.Event()
        server, monitor = self.services.server, self.services.monitor
        self._begin_progress(FIX_JOB, "Sửa lỗi kết nối")
        self._refresh_actions()
        try:
            ok = await run_in_daemon(
                "fix-connection", lambda: fix_connection(server, self.bus, running, monitor, cancel=cancel)
            )
        finally:
            self._end_job()
        if self._closing:
            return
        if ok:
            dialogs.toast(self.page, "Đã sửa xong — rút ra cắm lại cáp nếu máy vẫn chưa hiện")
        else:
            dialogs.toast(self.page, "Chưa khởi động lại được ADB — xem console", T.DANGER,
                          ft.Icons.ERROR_OUTLINE_ROUNDED)

    # driver --------------------------------------------------------------------------------------------------
    async def _on_driver_click(self, _e=None) -> None:
        if self._closing:
            return
        if self.state.busy or self.services.store is None:
            self._toast_busy()
            return
        dialogs.show_confirm(
            self.page, "Cài driver USB Xiaomi",
            "Windows sẽ hỏi quyền quản trị (UAC) — hãy bấm Yes (Có) để cài driver.", "Cài driver",
            lambda: self.page.run_task(self._run_driver), icon=ft.Icons.USB_ROUNDED,
        )

    async def _run_driver(self) -> None:
        if self._closing:
            return
        if self.state.busy:
            self._toast_busy()
            return
        self.state.job = DRIVER_JOB
        self._begin_progress(DRIVER_JOB, "Cài driver USB Xiaomi")
        self._refresh_actions()
        store = self.services.store

        def work():
            progress = Progress(self.bus, DRIVER_JOB, "Cài driver USB Xiaomi")
            progress.state(JobState.RUNNING)
            log = Logger(self.bus, DRIVER_JOB)
            try:
                result = install_driver(store, log, progress)
            except Exception as exc:  # noqa: BLE001 - e.g. a damaged driver package: report, never hang
                log.error(f"Không cài được driver: {exc}")
                result = DriverResult(False, None, f"Không cài được driver: {exc}")
            if result.ok:
                progress.update(1.0, result.message, force=True)
            final = JobState.SUCCESS if result.ok else (JobState.CANCELLED if result.cancelled else JobState.FAILED)
            progress.state(final, message=result.message)
            self.bus.emit(StatusEvent("driver", "ok" if result.ok else "missing"))
            return result

        try:
            # a daemon thread: exiting never waits for the elevated pnputil, which finishes on its own
            result = await run_in_daemon("driver-install", work)
        finally:
            self._end_job()
        if self._closing:
            return
        if result.ok and self.services.settings.driver_auto_attempted:
            self.services.settings.driver_auto_attempted = False
            await asyncio.to_thread(save_settings, self.services.settings)
        color = T.SUCCESS if result.ok else T.WARNING
        dialogs.toast(self.page, result.message, color,
                      ft.Icons.CHECK_CIRCLE_ROUNDED if result.ok else ft.Icons.WARNING_AMBER_ROUNDED)

    # window -------------------------------------------------------------------------------------------------
    async def _toggle_theme(self, _e) -> None:
        dark = self.page.theme_mode != ft.ThemeMode.DARK
        self.page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        self.title_bar.set_dark(dark)
        self.page.update()
        self.services.settings.theme = "dark" if dark else "light"
        await asyncio.to_thread(save_settings, self.services.settings)

    async def _minimize(self, _e) -> None:
        self.page.window.minimized = True
        self.page.update()

    async def _maximize(self, _e) -> None:
        self.page.window.maximized = not self.page.window.maximized
        self.page.update()
        self._dirty(*self.title_bar.set_maximized(bool(self.page.window.maximized)))

    async def _close_click(self, _e) -> None:
        await self._request_close()

    async def _request_close(self) -> None:
        if self._closing:
            return
        if self.state.busy:
            if self._close_prompt is not None and self._close_prompt.open:
                return  # Alt+F4 / taskbar close while the question is already on screen
            self._close_prompt = dialogs.show_confirm(
                self.page, "Đang chạy tác vụ",
                "Thoát bây giờ sẽ dừng tác vụ đang chạy giữa chừng. Bạn chắc chắn muốn thoát?", "Dừng và thoát",
                self._shutdown_and_exit, danger=True,
            )
            return
        await self._shutdown_and_exit()

    async def _shutdown_and_exit(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._close_prompt = None
        self.services.begin_close()  # nothing may start adb from now on; bootstrap stops at its next step
        if self.state.busy:
            await self._stop_job_for_exit()
        self.pump.stop()
        await asyncio.to_thread(self.services.shutdown)
        with contextlib.suppress(RuntimeError):  # the client may exit before it answers: "Session closed"
            await self.page.window.destroy()

    async def _stop_job_for_exit(self) -> None:
        """Cancel the running job and give it a moment to reach a checkpoint, so it ends cleanly and its last
        log lines reach the session log. The window stays up meanwhile and shows that the tool is stopping."""
        state = self.state
        if self.cancel is not None:
            self.cancel.set()
        state.stopping = True
        Logger(self.bus, state.job or "").warn("Đang dừng tác vụ trước khi thoát…")
        self._refresh_actions()
        deadline = time.monotonic() + JOB_STOP_WAIT
        while state.busy and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
