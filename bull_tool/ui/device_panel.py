"""Sidebar device card: connection states, live device details and a selector when several are plugged in."""

from __future__ import annotations

import flet as ft

from bull_tool.core.adb.client import DeviceEntry
from bull_tool.core.device_info import DeviceInfo
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W

STATE_MESSAGES = {
    "offline": ("Thiết bị đang offline", "Rút cáp ra cắm lại, mở khóa màn hình điện thoại."),
    "recovery": ("Máy đang ở chế độ Recovery", "Khởi động lại máy vào Android để dùng tool."),
    "sideload": ("Máy đang ở chế độ Sideload", "Khởi động lại máy vào Android để dùng tool."),
    "bootloader": ("Máy đang ở chế độ Fastboot", "Khởi động lại máy vào Android để dùng tool."),
    "authorizing": ("Đang xác thực kết nối…", "Mở khóa màn hình và bấm Cho phép nếu được hỏi."),
    "connecting": ("Đang kết nối…", "Chờ vài giây."),
}


class DevicePanel:
    def __init__(self, on_refresh, on_copy, on_select, on_guide, on_fix) -> None:
        self._on_guide = on_guide
        self._on_fix = on_fix
        self._refresh = W.icon_button(ft.Icons.REFRESH_ROUNDED, "Kiểm tra lại thiết bị", on_refresh)
        self._copy = W.icon_button(ft.Icons.CONTENT_COPY_ROUNDED, "Sao chép thông tin máy", on_copy)
        self._copy.visible = False
        header = ft.Row(
            [
                W.icon_tile(ft.Icons.PHONE_ANDROID_ROUNDED, T.ACCENT, 30),
                W.overline("Thiết bị"),
                ft.Container(expand=True),
                self._copy,
                self._refresh,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._selector = ft.Dropdown(
            options=[],
            dense=True,
            filled=True,
            fill_color=T.CARD_HOVER,
            # explicit FOCUSED entry: a single border would draw the focus ring in the theme primary
            border={
                ft.ControlState.DEFAULT: ft.OutlineInputBorder(border_radius=T.RADIUS_SM,
                                                               side=ft.BorderSide(1, T.BORDER)),
                ft.ControlState.FOCUSED: ft.OutlineInputBorder(border_radius=T.RADIUS_SM,
                                                               side=ft.BorderSide(2, T.BORDER)),
            },
            text_style=ft.TextStyle(size=12, font_family=T.FONT_MEDIUM),
            on_select=on_select,
            visible=False,
            expand=True,
        )
        self._switcher = ft.AnimatedSwitcher(
            content=self._starting_view(),
            duration=ft.Duration(milliseconds=260),
            reverse_duration=ft.Duration(milliseconds=160),
            switch_in_curve=T.EASE,
            transition=ft.AnimatedSwitcherTransition.FADE,
        )
        self._pulse_icon: ft.Icon | None = None
        self.label_width = 92
        self.root = W.card(
            ft.Column([header, ft.Row([self._selector]), self._switcher], spacing=12),
            padding=ft.Padding(16, 14, 16, 16),
        )
        self.state = "starting"

    # -- views -------------------------------------------------------------------------------------
    def _message_view(self, icon: str, color: str, title: str, detail: str, extra: list[ft.Control] | None = None):
        icon_ctrl = ft.Icon(icon, size=26, color=color, animate_opacity=ft.Animation(700, T.EASE))
        self._pulse_icon = icon_ctrl
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(icon_ctrl, width=46, height=46, border_radius=14, bgcolor=T.soft(color, 0.12),
                                     alignment=ft.Alignment.CENTER),
                        ft.Column(
                            [W.text(title, size=14, family=T.FONT_SEMIBOLD, max_lines=2),
                             W.text(detail, size=12, color=T.TEXT_MUTED, max_lines=3)],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                *(extra or []),
            ],
            spacing=12,
        )

    @staticmethod
    def _loading_view(message: str) -> ft.Control:
        """Spinner + status line above placeholder bars (startup and device-info read)."""
        bars = [
            ft.Container(height=h, width=w, border_radius=6, bgcolor=T.CARD_ACTIVE)
            for h, w in ((16, 170), (12, 120), (10, 210), (10, 190), (10, 150))
        ]
        return ft.Column(
            [
                ft.Row([ft.ProgressRing(width=16, height=16, stroke_width=2, color=T.PRIMARY),
                        W.text(message, size=12.5, color=T.TEXT_MUTED, max_lines=1, expand=True)],
                       spacing=10),
                ft.Shimmer(content=ft.Column(bars, spacing=10), base_color=T.CARD_ACTIVE, highlight_color=T.CARD_DEEP),
            ],
            spacing=12,
        )

    def _starting_view(self) -> ft.Control:
        return self._loading_view("Đang khởi động ADB…")

    def _no_device_view(self) -> ft.Control:
        checklist = [
            (ft.Icons.DEVELOPER_MODE_ROUNDED, "Bật Tùy chọn nhà phát triển + Gỡ lỗi USB"),
            (ft.Icons.CABLE_ROUNDED, "Cắm cáp USB vào máy tính"),
            (ft.Icons.VERIFIED_ROUNDED, "Bấm Cho phép (Allow) trên điện thoại"),
        ]
        rows = [
            ft.Row(
                [ft.Icon(icon, size=16, color=T.TEXT_MUTED), W.text(label, size=12, color=T.TEXT_MUTED, max_lines=2,
                                                                  expand=True)],
                spacing=8,
            )
            for icon, label in checklist
        ]
        actions = ft.Row(
            [
                self._outline_action("Hướng dẫn", ft.Icons.MENU_BOOK_ROUNDED, self._on_guide, T.INFO),
                self._outline_action("Sửa kết nối", ft.Icons.HEALING_ROUNDED, self._on_fix, T.WARNING),
            ],
            spacing=8,
        )
        return self._message_view(
            ft.Icons.PHONE_ANDROID_ROUNDED, T.TEXT_MUTED, "Chưa có thiết bị",
            "Đang chờ điện thoại kết nối qua cáp USB.",
            [ft.Column(rows, spacing=6), actions],
        )

    @staticmethod
    def _outline_action(label: str, icon: str, on_click, color: str) -> ft.Container:
        """Equal-width secondary action (two of them share one row)."""
        # expand + expand_loose = Flexible: natural width, ellipsis instead of overflow when the button is too narrow.
        # Sized so "Sửa kết nối" (~71 px at 12 px) fits the ~74 px left in each button at the 260 px sidebar.
        label_text = W.text(label, size=12, family=T.FONT_SEMIBOLD, color=color, max_lines=1, expand=True)
        label_text.expand_loose = True
        button = ft.Container(
            content=ft.Row(
                [ft.Icon(icon, size=16, color=color), label_text],
                spacing=5,
                alignment=ft.MainAxisAlignment.CENTER,
                tight=True,
            ),
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding(4, 8, 4, 8),
            border_radius=T.RADIUS_SM,
            border=ft.Border.all(1, T.soft(color, 0.45)),
            bgcolor=T.soft(color, 0.06),
            on_click=on_click,
            expand=True,
            animate=ft.Animation(T.DURATION_FAST, T.EASE),
        )

        async def on_hover(e: ft.ControlEvent) -> None:
            button.bgcolor = T.soft(color, 0.14 if e.data in (True, "true") else 0.06)
            button.update()

        button.on_hover = on_hover
        return button

    def _info_row(self, label: str, value: str) -> ft.Row:
        return ft.Row(
            [
                ft.Container(W.text(label, size=12, color=T.TEXT_MUTED, max_lines=1), width=self.label_width),
                W.text(value or "—", size=12.5, family=T.FONT_MEDIUM, max_lines=2, expand=True),
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def _ready_view(self, info: DeviceInfo) -> ft.Control:
        subtitle = " · ".join(p for p in (info.brand, info.model, info.codename) if p)
        chips = ft.Row(
            [
                W.pill("● Đã kết nối", color=T.SUCCESS),
                W.pill(f"Android {info.android}", color=T.INFO) if info.android else ft.Container(),
                W.pill(f"RAM {info.ram_gb} GB", color=T.TEXT_MUTED) if info.ram_gb else ft.Container(),
            ],
            spacing=6,
            wrap=True,
        )
        blocks: list[ft.Control] = [
            ft.Column(
                [W.text(info.display_name, size=16, family=T.FONT_SEMIBOLD, max_lines=2),
                 W.text(subtitle, size=12, color=T.TEXT_MUTED, max_lines=1)],
                spacing=2,
            ),
            chips,
        ]
        if info.storage_fraction is not None:
            used_color = T.DANGER if info.storage_fraction > 0.9 else T.PRIMARY
            blocks.append(
                ft.Column(
                    [
                        ft.Row([W.text("Bộ nhớ", size=12, color=T.TEXT_MUTED, expand=True),
                                W.text(f"{info.storage_used_gb:.1f} / {info.storage_total_gb:.1f} GB".replace(".", ","),
                                       size=12, family=T.MONO, color=T.TEXT_MUTED)]),
                        ft.ProgressBar(value=info.storage_fraction, bar_height=6, border_radius=6,
                                       color=used_color, bgcolor=T.CARD_ACTIVE),
                    ],
                    spacing=6,
                )
            )
        rows = [(label, value) for label, value in info.rows() if label not in ("Hãng", "Bộ nhớ")]
        blocks.append(W.divider())
        blocks.append(ft.Column([self._info_row(label, value) for label, value in rows], spacing=7))
        return ft.Column(blocks, spacing=12)

    def _reading_view(self, entry: DeviceEntry | None) -> ft.Control:
        name = (entry.model.replace("_", " ") if entry and entry.model else "") or (entry.serial if entry else "")
        return self._loading_view(f"Đang đọc thông tin {name}…")

    # -- public API ----------------------------------------------------------------------------------
    def _show(self, state: str, view: ft.Control) -> list[ft.Control]:
        self.state = state
        if state not in ("no_device", "adb_down", "unauthorized"):
            self._pulse_icon = None
        self._copy.visible = state == "ready"
        self._switcher.content = view
        return [self.root]

    def show_starting(self) -> list[ft.Control]:
        return self._show("starting", self._starting_view())

    def show_no_device(self) -> list[ft.Control]:
        return self._show("no_device", self._no_device_view())

    def show_adb_down(self, detail: str) -> list[ft.Control]:
        detail = (detail[:160] + "…") if len(detail) > 160 else detail
        # the monitor keeps retrying on its own: say so on its own line, so a long error detail cannot hide it
        retrying = ft.Row(
            [ft.ProgressRing(width=14, height=14, stroke_width=2, color=T.TEXT_MUTED),
             W.text("Tool đang tự thử lại…", size=12, color=T.TEXT_MUTED, max_lines=1, expand=True)],
            spacing=8,
        )
        view = self._message_view(
            ft.Icons.LINK_OFF_ROUNDED, T.DANGER, "Không kết nối được ADB", detail or "Mất kết nối tới ADB server.",
            [retrying, W.ghost_button("Sửa lỗi kết nối", ft.Icons.HEALING_ROUNDED, self._on_fix, color=T.WARNING)],
        )
        return self._show("adb_down", view)

    def show_unauthorized(self, entry: DeviceEntry) -> list[ft.Control]:
        view = self._message_view(
            ft.Icons.LOCK_ROUNDED, T.WARNING, "Chờ cho phép gỡ lỗi USB",
            "Mở khóa màn hình điện thoại và bấm Cho phép (Allow). Nên tick “Luôn cho phép từ máy tính này”.",
        )
        return self._show("unauthorized", view)

    def show_other_state(self, entry: DeviceEntry) -> list[ft.Control]:
        title, detail = STATE_MESSAGES.get(entry.state, (f"Trạng thái: {entry.state}", "Rút cáp ra cắm lại."))
        return self._show("other", self._message_view(ft.Icons.LINK_OFF_ROUNDED, T.WARNING, title, detail))

    def show_error(self, title: str, detail: str) -> list[ft.Control]:
        view = self._message_view(ft.Icons.ERROR_OUTLINE_ROUNDED, T.DANGER, title, detail)
        return self._show("error", view)

    def show_reading(self, entry: DeviceEntry | None) -> list[ft.Control]:
        return self._show("reading", self._reading_view(entry))

    def show_info(self, info: DeviceInfo) -> list[ft.Control]:
        return self._show("ready", self._ready_view(info))

    def set_devices(self, devices: tuple[DeviceEntry, ...], selected: str | None, locked: bool) -> list[ft.Control]:
        self._selector.visible = len(devices) > 1

        def label(d: DeviceEntry) -> str:
            # short enough for the 260 px sidebar (the field clips, it does not ellipsize); the card below shows
            # the full serial and the state of the selected phone
            name = (d.model or "").replace("_", " ")
            if len(name) > 16:
                name = name[:15] + "…"
            if name and len(d.serial) > 4:
                text = f"{name} · …{d.serial[-4:]}"  # enough to tell two phones of the same model apart
            else:
                text = f"{name} · {d.serial}" if name else d.serial
            return text if d.ready else f"⚠ {text}"

        self._selector.options = [ft.DropdownOption(key=d.serial, text=label(d)) for d in devices]
        self._selector.value = selected
        self._selector.disabled = locked
        return [self.root]

    def pulse(self, on: bool) -> list[ft.Control]:
        if self._pulse_icon is None:
            return []
        self._pulse_icon.opacity = 1.0 if on else 0.35
        return [self._pulse_icon]

    def set_busy(self, busy: bool) -> list[ft.Control]:
        self._refresh.disabled = busy
        self._selector.disabled = busy
        return [self._refresh, self._selector]

    def apply_layout(self, layout: T.Layout) -> None:
        self.label_width = 84 if layout.sidebar < 300 else 96
