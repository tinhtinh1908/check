"""Bottom status bar: ADB / driver state on the left, shop links on the right."""

from __future__ import annotations

import flet as ft

from bull_tool import app_info
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W


class StatusBar:
    def __init__(self, open_url) -> None:
        self._adb_dot = ft.Container(width=7, height=7, border_radius=4, bgcolor=T.TEXT_MUTED)
        self._adb = W.text("ADB: đang khởi động", size=11.5, color=T.TEXT_MUTED, max_lines=1)
        self._driver_dot = ft.Container(width=7, height=7, border_radius=4, bgcolor=T.TEXT_MUTED)
        self._driver = W.text("Driver USB: đang kiểm tra", size=11.5, color=T.TEXT_MUTED, max_lines=1)

        def link(label: str, url: str) -> ft.Container:
            label_text = W.text(label, size=11.5, family=T.FONT_MEDIUM, color=T.TEXT_MUTED, max_lines=1)
            box = ft.Container(content=label_text, padding=ft.Padding(6, 2, 6, 2), border_radius=6,
                               on_click=lambda _e: open_url(url), tooltip=url)

            async def on_hover(e: ft.ControlEvent) -> None:
                label_text.color = T.PRIMARY if e.data in (True, "true") else T.TEXT_MUTED
                label_text.update()

            box.on_hover = on_hover
            return box

        # only the version label flexes, so it is the first to ellipsize; ADB / driver labels keep their natural
        # width (an even flex split would cut the longer ADB "mất kết nối, đang thử lại" text)
        left = ft.Row(
            [
                ft.Row([self._adb_dot, self._adb], spacing=6, tight=True),
                ft.Row([self._driver_dot, self._driver], spacing=6, tight=True),
                W.text(f"{app_info.APP_NAME} v{app_info.VERSION}", size=11.5, color=T.TEXT_MUTED, max_lines=1,
                       expand=True),
            ],
            spacing=18,
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        right = ft.Row(
            [link(app_info.WEBSITE_LABEL, app_info.WEBSITE), link(f"Zalo {app_info.ZALO_PHONE}", app_info.ZALO)],
            spacing=4,
            tight=True,
        )
        self.root = ft.Container(
            content=ft.Row([left, right], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            height=28,
            padding=ft.Padding(14, 0, 8, 0),
            bgcolor=T.BG,
            border=ft.Border(top=ft.BorderSide(1, T.BORDER)),
        )

    def set_adb(self, up: bool | None, revision: str = "") -> list[ft.Control]:
        version = f" {revision}" if revision else ""
        if up is None:
            self._adb_dot.bgcolor, self._adb.value = T.TEXT_MUTED, f"ADB{version}: đang khởi động"
        elif up:
            self._adb_dot.bgcolor, self._adb.value = T.SUCCESS, f"ADB{version}: sẵn sàng"
        else:
            self._adb_dot.bgcolor, self._adb.value = T.DANGER, f"ADB{version}: mất kết nối, đang thử lại"
        return [self._adb_dot, self._adb]

    def set_driver(self, ok: bool | None) -> list[ft.Control]:
        if ok is None:
            self._driver_dot.bgcolor, self._driver.value = T.TEXT_MUTED, "Driver USB: đang kiểm tra"
        elif ok:
            self._driver_dot.bgcolor, self._driver.value = T.SUCCESS, "Driver USB Xiaomi: đã cài"
        else:
            self._driver_dot.bgcolor, self._driver.value = T.WARNING, "Driver USB Xiaomi: chưa cài"
        return [self._driver_dot, self._driver]
