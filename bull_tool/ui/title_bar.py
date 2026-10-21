"""Custom title bar: logo, name, version, live device status, theme toggle and window buttons."""

from __future__ import annotations

import flet as ft

from bull_tool import app_info
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W
from bull_tool.ui.widgets import Handler


class TitleBar:
    def __init__(
        self,
        on_toggle_theme: Handler,
        on_minimize: Handler,
        on_maximize: Handler,
        on_close: Handler,
    ) -> None:
        logo = ft.Container(
            content=ft.Image(src="bull_logo_64.png", fit=ft.BoxFit.CONTAIN, filter_quality=ft.FilterQuality.HIGH),
            width=28,
            height=28,
            bgcolor=T.WHITE,
            border_radius=7,
            padding=1,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        name = ft.Text(
            app_info.APP_NAME,
            size=14,
            font_family=T.FONT_EXTRABOLD,
            color=T.TEXT,
            style=ft.TextStyle(letter_spacing=1.4),
            max_lines=1,
        )
        self._dot = ft.Container(width=8, height=8, border_radius=4, bgcolor=T.TEXT_MUTED,
                                 animate=ft.Animation(T.DURATION, T.EASE))
        self._device_text = W.text(
            "Đang khởi động…", size=12, family=T.FONT_MEDIUM, color=T.TEXT_MUTED, max_lines=1, expand=True
        )
        self._device_text.expand_loose = True  # ellipsis instead of overflow when the bar gets narrow
        self._device_pill = ft.Container(
            content=ft.Row([self._dot, self._device_text], spacing=8, tight=True,
                           vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding(10, 4, 12, 4),
            border_radius=20,
            bgcolor=T.soft(T.TEXT_MUTED, 0.08),
            border=ft.Border.all(1, T.BORDER),
            expand=True,
        )
        self._device_pill.expand_loose = True
        brand = ft.Row(
            [logo, name, W.pill(f"v{app_info.VERSION}"), ft.Container(width=6), self._device_pill],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._drag = ft.WindowDragArea(
            content=ft.Container(content=brand, padding=ft.Padding(12, 0, 8, 0), alignment=ft.Alignment.CENTER_LEFT),
            maximizable=True,
            expand=True,
        )
        self._theme_button = W.icon_button(ft.Icons.LIGHT_MODE_ROUNDED, "Đổi giao diện sáng/tối", on_toggle_theme)
        self._max_icon = ft.Icon(ft.Icons.CROP_SQUARE_ROUNDED, size=16, color=T.TEXT_MUTED)
        self._buttons = [
            self._window_button(ft.Icon(ft.Icons.REMOVE_ROUNDED, size=18, color=T.TEXT_MUTED), on_minimize, "Thu nhỏ"),
            self._window_button(self._max_icon, on_maximize, "Phóng to / Thu về"),
            self._window_button(
                ft.Icon(ft.Icons.CLOSE_ROUNDED, size=18, color=T.TEXT_MUTED), on_close, "Đóng", close=True
            ),
        ]
        self.root = ft.Container(
            content=ft.Row(
                [self._drag, self._theme_button, ft.Container(width=6), *self._buttons],
                spacing=0,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            height=44,
            bgcolor=T.BG,
            border=ft.Border(bottom=ft.BorderSide(1, T.BORDER)),
        )

    def _window_button(self, icon: ft.Icon, on_click: Handler, tooltip: str, close: bool = False) -> ft.Container:
        button = ft.Container(
            content=icon,
            width=46,
            alignment=ft.Alignment.CENTER,
            on_click=on_click,
            tooltip=tooltip,
            animate=ft.Animation(T.DURATION_FAST, T.EASE),
        )

        async def on_hover(e: ft.ControlEvent) -> None:
            hovered = e.data in (True, "true")
            if close:
                button.bgcolor = T.CLOSE_HOVER if hovered else None
                icon.color = T.WHITE if hovered else T.TEXT_MUTED
            else:
                button.bgcolor = T.soft(T.TEXT_MUTED, 0.12) if hovered else None
            button.update()

        button.on_hover = on_hover
        return button

    def set_device(self, color: str, label: str) -> list[ft.Control]:
        self._dot.bgcolor = color
        self._device_text.value = label
        self._device_text.color = T.TEXT if color in (T.SUCCESS,) else T.TEXT_MUTED
        return [self._device_pill]

    def set_maximized(self, maximized: bool) -> list[ft.Control]:
        self._max_icon.icon = ft.Icons.FILTER_NONE_ROUNDED if maximized else ft.Icons.CROP_SQUARE_ROUNDED
        return [self._max_icon]

    def set_dark(self, dark: bool) -> list[ft.Control]:
        self._theme_button.icon = ft.Icons.LIGHT_MODE_ROUNDED if dark else ft.Icons.DARK_MODE_ROUNDED
        return [self._theme_button]

    def apply_layout(self, layout: T.Layout) -> None:
        self.root.height = 40 if layout.short else 44
        self._device_pill.visible = layout.width >= 960
