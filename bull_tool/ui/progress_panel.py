"""Progress card for the active job: ring with %, title + state chip, bar, step label, speed / ETA / elapsed,
a thin per-file bar while bytes are being transferred, and the Start/Stop action on the right."""

from __future__ import annotations

import flet as ft

from bull_tool.core.events import JobState, ProgressEvent
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W

STATE_STYLE = {
    None: ("Sẵn sàng", T.TEXT_MUTED),
    JobState.RUNNING: ("Đang chạy", T.ACCENT),
    JobState.SUCCESS: ("Hoàn tất", T.SUCCESS),
    JobState.CANCELLED: ("Đã dừng", T.WARNING),
    JobState.FAILED: ("Lỗi", T.DANGER),
}


def _clock(seconds: float | None) -> str:
    if seconds is None:
        return ""
    seconds = int(max(seconds, 0))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _speed(bps: float) -> str:
    if bps <= 0:
        return ""
    return f"{bps / 1048576:.1f} MB/s".replace(".", ",")


class ProgressPanel:
    def __init__(self, action: ft.Control) -> None:
        self._ring = ft.ProgressRing(
            value=0, stroke_width=6, color=T.PRIMARY, bgcolor=T.CARD_ACTIVE, width=62, height=62,
            stroke_cap=ft.StrokeCap.ROUND,
        )
        self._percent = ft.Text("0%", size=15, font_family=T.MONO_BOLD, color=T.TEXT)
        self._ring_box = ft.Stack(
            [self._ring, ft.Container(self._percent, alignment=ft.Alignment.CENTER, width=62, height=62)],
            width=62,
            height=62,
        )
        # expand + expand_loose = Flexible: natural width, ellipsis only when the row is too narrow
        self._title = W.text("Sẵn sàng", size=15, family=T.FONT_SEMIBOLD, max_lines=1, expand=True)
        self._title.expand_loose = True
        self._chip_text = ft.Text("Chờ lệnh", size=11, font_family=T.FONT_SEMIBOLD, color=T.TEXT_MUTED)
        self._chip = ft.Container(
            content=self._chip_text, padding=ft.Padding(8, 2, 8, 3), border_radius=20,
            bgcolor=T.soft(T.TEXT_MUTED, 0.12),
        )
        self._counter = W.text("", size=12, family=T.MONO, color=T.TEXT_MUTED, max_lines=1)
        self._bar = ft.ProgressBar(value=0, bar_height=8, border_radius=8, color=T.PRIMARY, bgcolor=T.CARD_ACTIVE)
        self._sub_bar = ft.ProgressBar(
            value=0, bar_height=3, border_radius=3, color=T.soft(T.ACCENT_2, 0.85), bgcolor=T.soft(T.TEXT_MUTED, 0.1),
            visible=False,
        )
        self._label = W.text(
            "Cắm điện thoại, chọn dòng máy rồi bấm Bắt đầu", size=12.5, color=T.TEXT_MUTED, max_lines=1, expand=True
        )
        self._meta = W.text("", size=12, family=T.MONO, color=T.TEXT_MUTED, max_lines=1)
        title_group = ft.Container(
            content=ft.Row([self._title, self._chip], spacing=10, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            expand=True,
        )
        info = ft.Column(
            [
                ft.Row([title_group, self._counter], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self._bar,
                ft.Row([self._label, self._meta], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                self._sub_bar,
            ],
            spacing=8,
            expand=True,
        )
        self._action = action
        self._row = ft.Row([self._ring_box, info, action], spacing=18, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.root = W.card(self._row, padding=ft.Padding(18, 14, 18, 14))
        self.job: str | None = None
        self.state: JobState | None = None

    # -- updates ----------------------------------------------------------------------------------
    def begin(self, job: str, title: str) -> list[ft.Control]:
        self.job = job
        self.state = JobState.RUNNING
        self._title.value = title
        self._apply_state(JobState.RUNNING)
        self._set_fraction(0.0)
        self._label.value = "Chuẩn bị…"
        self._meta.value = ""
        self._counter.value = ""
        self._sub_bar.visible = False
        return [self.root]

    def show(self, event: ProgressEvent) -> list[ft.Control]:
        if event.job != self.job:
            return []
        self._title.value = event.title
        self._set_fraction(event.fraction)
        if event.label:
            self._label.value = event.label
        self._counter.value = f"{event.step}/{event.steps}" if event.steps else ""
        transferring = event.sub_fraction is not None and self.state == JobState.RUNNING
        self._sub_bar.visible = transferring
        if transferring:
            self._sub_bar.value = event.sub_fraction
        parts = [_speed(event.rate_bps)] if transferring else []
        if transferring and event.eta_s is not None:
            parts.append(f"còn {_clock(event.eta_s)}")
        parts.append(_clock(event.elapsed_s))
        self._meta.value = " · ".join(p for p in parts if p)
        return [self.root]

    def finish(self, job: str, state: JobState, message: str = "") -> list[ft.Control]:
        if job != self.job:
            return []
        self.state = state
        self._apply_state(state)
        self._sub_bar.visible = False
        if state == JobState.SUCCESS:
            self._set_fraction(1.0)
        if message:
            self._label.value = message
        return [self.root]

    def _apply_state(self, state: JobState | None) -> None:
        label, color = STATE_STYLE[state]
        self._chip_text.value = label
        self._chip_text.color = color
        self._chip.bgcolor = T.soft(color, 0.14)
        bar_color = T.SUCCESS if state == JobState.SUCCESS else (T.WARNING if state == JobState.CANCELLED else (
            T.DANGER if state == JobState.FAILED else T.PRIMARY))
        self._bar.color = bar_color
        self._ring.color = bar_color

    def _set_fraction(self, fraction: float | None) -> None:
        self._bar.value = fraction
        self._ring.value = fraction
        self._percent.value = "…" if fraction is None else f"{int(fraction * 100)}%"

    def apply_layout(self, layout: T.Layout) -> None:
        size = 48 if layout.short else 62
        self._ring.width = self._ring.height = size
        self._ring_box.width = self._ring_box.height = size
        self._ring_box.controls[1].width = self._ring_box.controls[1].height = size
        self._percent.size = 13 if layout.short else 15
        self.root.padding = ft.Padding(14, 10, 14, 10) if layout.short else ft.Padding(18, 14, 18, 14)
        self._row.spacing = 12 if layout.width < 1024 else 18
