"""Sidebar tools: USB-debugging guide, connection fix, Xiaomi USB driver."""

from __future__ import annotations

import flet as ft

from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W


class _ToolRow:
    def __init__(self, icon: str, color: str, title: str, subtitle: str, on_click) -> None:
        self._tile = W.icon_tile(icon, color, 34)
        self.title = W.text(title, size=13, family=T.FONT_SEMIBOLD, max_lines=2)
        self.subtitle = W.text(subtitle, size=11.5, color=T.TEXT_MUTED, max_lines=2)
        self.trailing = ft.Container(ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=T.TEXT_MUTED))
        self.root = ft.Container(
            content=ft.Row(
                [self._tile, ft.Column([self.title, self.subtitle], spacing=1, expand=True), self.trailing],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(10, 9, 10, 9),
            border_radius=T.RADIUS,
            on_click=on_click,
            animate=ft.Animation(T.DURATION_FAST, T.EASE),
        )
        self.root.on_hover = self._on_hover

    async def _on_hover(self, e: ft.ControlEvent) -> None:
        self.root.bgcolor = T.CARD_HOVER if e.data in (True, "true") and not self.root.disabled else None
        self.root.update()

    def set_color(self, color: str) -> None:
        self._tile.bgcolor = T.soft(color, 0.14)
        self._tile.content.color = color


class ToolsPanel:
    def __init__(self, on_guide, on_fix, on_driver) -> None:
        self.guide = _ToolRow(ft.Icons.MENU_BOOK_ROUNDED, T.INFO, "Hướng dẫn gỡ lỗi USB",
                              "Xiaomi · OPPO · Honor · vivo", on_guide)
        self.fix = _ToolRow(ft.Icons.HEALING_ROUNDED, T.WARNING, "Sửa lỗi kết nối",
                            "Máy tính không nhận điện thoại", on_fix)
        self.driver = _ToolRow(ft.Icons.USB_ROUNDED, T.TEXT_MUTED, "Driver USB Xiaomi", "Đang kiểm tra…", on_driver)
        self._driver_badge = W.pill("…")
        self.driver.trailing.content = self._driver_badge
        self.root = W.card(
            ft.Column(
                [
                    ft.Row([W.icon_tile(ft.Icons.SETTINGS_SUGGEST_ROUNDED, T.INFO, 30), W.overline("Công cụ")],
                           spacing=10),
                    ft.Column([self.guide.root, self.fix.root, self.driver.root], spacing=2),
                ],
                spacing=10,
            ),
            padding=ft.Padding(12, 14, 12, 12),
        )

    def set_driver(self, ok: bool | None) -> list[ft.Control]:
        if ok is None:
            color, badge, subtitle = T.TEXT_MUTED, "…", "Đang kiểm tra…"
        elif ok:
            color, badge, subtitle = T.SUCCESS, "Đã cài", "Đã có trên máy tính này · bấm để cài lại"
        else:
            color, badge, subtitle = T.WARNING, "Chưa cài", "Bấm để cài (cần quyền Admin)"
        self.driver.set_color(color)
        self.driver.subtitle.value = subtitle
        self._driver_badge.content.value = badge
        self._driver_badge.content.color = color
        self._driver_badge.bgcolor = T.soft(color, 0.12)
        return [self.root]

    def set_busy(self, busy: bool) -> list[ft.Control]:
        for row in (self.fix, self.driver):
            row.root.disabled = busy
            row.root.opacity = 0.5 if busy else 1.0
        return [self.root]
