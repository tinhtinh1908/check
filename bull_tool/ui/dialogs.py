"""Dialog builders (confirmation, job summary, USB-debug guide, fatal error) sharing the design tokens."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import flet as ft

from bull_tool.core.job_runner import Summary
from bull_tool.core.profiles import GENERAL_NOTE, GUIDES
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W

Action = Callable[[], Awaitable[None] | None]
ActionSpec = tuple[str, Action | None, bool, bool]  # label, then, primary, danger


def _width(page: ft.Page, preferred: int = 600) -> float:
    available = (page.width or preferred + 64) - 64
    return max(320, min(preferred, available))


def dismiss(dialog: ft.DialogControl) -> None:
    """Close this dialog if it is still open; a no-op once it is closed or when it is not on a page.

    Flet keeps the entry in the page's dialog stack until the client reports the dismiss, then removes it."""
    if not dialog.open:
        return
    dialog.open = False
    try:
        dialog.update()
    except RuntimeError:  # never shown, or its page is gone: nothing on screen to close
        pass


def _close(dialog: ft.AlertDialog, then: Action | None = None):
    async def handler(_e) -> None:
        # Close the dialog that owns the button, not the top of the page's dialog stack (a toast may sit there).
        # A click that raced the close (double click, or the app dismissed it) finds it closed and does nothing.
        if not dialog.open:
            return
        dismiss(dialog)
        if then is not None:
            result = then()
            if hasattr(result, "__await__"):
                await result

    return handler


def _dialog(page: ft.Page, icon: str, color: str, title: str, body: ft.Control, actions: list[ActionSpec],
            width: int = 560) -> ft.AlertDialog:
    dialog = ft.AlertDialog(
        modal=True,
        bgcolor=T.CARD,
        shape=ft.RoundedRectangleBorder(radius=T.RADIUS_LG),
        title=ft.Row(
            [W.icon_tile(icon, color, 36), W.text(title, size=17, family=T.FONT_BOLD, max_lines=2, expand=True)],
            spacing=12,
        ),
        # the dialog scrolls title + content itself: it stays as tall as its content and scrolls only when the
        # window is too short, with the buttons always visible (a scrolling Column inside filled the window)
        content=ft.Container(content=ft.Column([body], tight=True), width=_width(page, width)),
        scrollable=True,
        actions_alignment=ft.MainAxisAlignment.END,
    )
    dialog.actions = [_action(label, _close(dialog, then), primary=primary, danger=danger)
                      for label, then, primary, danger in actions]
    return dialog


def _action(label: str, on_click, primary: bool = False, danger: bool = False) -> ft.Control:
    if primary or danger:
        return ft.FilledButton(
            content=ft.Text(label, font_family=T.FONT_SEMIBOLD),
            on_click=on_click,
            style=ft.ButtonStyle(
                bgcolor=T.DANGER if danger else T.ACCENT,
                color=T.WHITE,
                shape=ft.RoundedRectangleBorder(radius=T.RADIUS_SM),
                padding=ft.Padding(18, 12, 18, 12),
            ),
        )
    return ft.TextButton(
        content=ft.Text(label, font_family=T.FONT_MEDIUM, color=T.TEXT_MUTED),
        on_click=on_click,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=T.RADIUS_SM), padding=ft.Padding(14, 12, 14, 12)),
    )


def show_confirm(
    page: ft.Page,
    title: str,
    message: str,
    confirm_label: str,
    on_confirm: Action,
    details: list[str] | None = None,
    danger: bool = False,
    icon: str = ft.Icons.WARNING_AMBER_ROUNDED,
) -> ft.AlertDialog:
    color = T.DANGER if danger else T.WARNING
    parts: list[ft.Control] = [W.text(message, size=13.5, color=T.TEXT)]
    if details:
        parts.append(
            ft.Container(
                content=ft.Column(
                    [W.text(f"•  {line}", size=12.5, family=T.MONO, color=T.TEXT_MUTED) for line in details], spacing=4
                ),
                padding=12,
                bgcolor=T.CARD_HOVER,
                border_radius=T.RADIUS,
                border=ft.Border.all(1, T.BORDER),
            )
        )
    dialog = _dialog(
        page, icon, color, title, ft.Column(parts, spacing=12, tight=True),
        [("Huỷ", None, False, False), (confirm_label, on_confirm, not danger, danger)],
    )
    page.show_dialog(dialog)
    return dialog


def _stat(label: str, value: int, color: str) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [ft.Text(str(value), size=20, font_family=T.MONO_BOLD, color=color),
             W.text(label, size=11.5, color=T.TEXT_MUTED, max_lines=1)],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(6, 10, 6, 10),
        border_radius=T.RADIUS,
        bgcolor=T.soft(color, 0.08),
        col={"xs": 6, "sm": 3},
    )


def show_summary(page: ft.Page, summary: Summary) -> ft.AlertDialog:
    if summary.cancelled:
        icon, color, title = ft.Icons.PAUSE_ROUNDED, T.WARNING, f"Đã dừng — {summary.profile_name}"
    elif summary.aborted:
        icon, color, title = ft.Icons.ERROR_OUTLINE_ROUNDED, T.DANGER, f"Dừng giữa chừng — {summary.profile_name}"
    elif summary.failures:
        icon, color, title = ft.Icons.WARNING_AMBER_ROUNDED, T.WARNING, f"Hoàn tất (có lỗi) — {summary.profile_name}"
    else:
        icon, color, title = ft.Icons.CHECK_CIRCLE_ROUNDED, T.SUCCESS, f"Hoàn tất — {summary.profile_name}"
    minutes, seconds = divmod(int(summary.elapsed_s), 60)
    stats = ft.ResponsiveRow(
        [
            _stat("Đã gỡ", summary.removed, T.ACCENT),
            _stat("Đã tắt", summary.disabled, T.ACCENT_2),
            _stat("Đã cài", summary.installed, T.SUCCESS),
            _stat("Đã chép", summary.pushed, T.INFO),
            _stat("Thiết lập", summary.configured, T.CMD),
            _stat("Bỏ qua", summary.skipped, T.TEXT_MUTED),
            _stat("Lỗi", summary.failed, T.DANGER),
            _stat("Giây", int(summary.elapsed_s), T.TEXT),
        ],
        spacing=8,
        run_spacing=8,
    )
    parts: list[ft.Control] = [
        W.text(f"Thiết bị {summary.serial} · thời gian {minutes}:{seconds:02d}", size=12.5, color=T.TEXT_MUTED),
        stats,
    ]
    if summary.aborted:
        parts.append(W.text(summary.aborted, size=13, color=T.DANGER))
    if summary.failures:
        rows = []
        for failure in summary.failures[:12]:
            rows.append(W.text(f"✗ {failure.label}: {failure.reason}", size=12, family=T.MONO, color="#FCA5A5",
                               max_lines=3))
            if failure.hint:
                rows.append(W.text(f"   → {failure.hint}", size=12, color=T.WARNING, max_lines=3))
        if len(summary.failures) > 12:
            rows.append(W.text(f"… và {len(summary.failures) - 12} lỗi khác (xem console)", size=12,
                               color=T.TEXT_MUTED))
        parts.append(ft.Container(ft.Column(rows, spacing=4), padding=12, bgcolor=T.CONSOLE_BG,
                                  border_radius=T.RADIUS))
    if summary.disconnected_ok:
        parts.append(_note(
            ft.Icons.INFO_OUTLINE_ROUNDED, T.INFO,
            "Tool đã tắt gỡ lỗi USB trên điện thoại ở bước cuối nên máy đã ngắt kết nối — đúng như bản .bat.",
        ))
    if summary.post_note and not summary.cancelled and not summary.aborted:
        parts.append(_note(ft.Icons.TIPS_AND_UPDATES_ROUNDED, T.ACCENT_2, summary.post_note))
    dialog = _dialog(page, icon, color, title, ft.Column(parts, spacing=14, tight=True),
                     [("Đóng", None, True, False)], width=620)
    page.show_dialog(dialog)
    return dialog


def _note(icon: str, color: str, message: str) -> ft.Container:
    return ft.Container(
        content=ft.Row([ft.Icon(icon, size=18, color=color), W.text(message, size=12.5, expand=True)], spacing=10,
                       vertical_alignment=ft.CrossAxisAlignment.START),
        padding=12,
        border_radius=T.RADIUS,
        bgcolor=T.soft(color, 0.08),
        border=ft.Border.all(1, T.soft(color, 0.35)),
    )


def show_guide(page: ft.Page, initial: int = 0) -> ft.AlertDialog:
    steps_column = ft.Column(spacing=8, tight=True)
    tabs_row = ft.Row(spacing=6, wrap=True, run_spacing=6)

    def tab_handler(index: int):
        async def handler(_e) -> None:
            render(index)
            tabs_row.update()
            steps_column.update()

        return handler

    def render(index: int) -> None:
        tabs_row.controls = []
        for i, (name, _steps) in enumerate(GUIDES):
            active = i == index
            tabs_row.controls.append(
                ft.Container(
                    content=ft.Text(name, size=12.5, font_family=T.FONT_SEMIBOLD,
                                    color=T.WHITE if active else T.TEXT_MUTED),
                    padding=ft.Padding(12, 6, 12, 7),
                    border_radius=20,
                    bgcolor=T.ACCENT if active else T.CARD_HOVER,
                    border=ft.Border.all(1, T.ACCENT if active else T.BORDER),
                    on_click=tab_handler(i),
                )
            )
        steps_column.controls = []
        for number, step in enumerate(GUIDES[index][1], start=1):
            steps_column.controls.append(
                ft.Row(
                    [
                        ft.Container(
                            ft.Text(str(number), size=12, font_family=T.MONO_BOLD, color=T.ACCENT),
                            width=26, height=26, border_radius=13, bgcolor=T.soft(T.ACCENT, 0.12),
                            alignment=ft.Alignment.CENTER,
                        ),
                        W.text(step, size=13, expand=True),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

    render(initial)
    body = ft.Column(
        [tabs_row, ft.Container(steps_column, padding=ft.Padding(2, 6, 2, 6)),
         _note(ft.Icons.INFO_OUTLINE_ROUNDED, T.INFO, GENERAL_NOTE)],
        spacing=14,
        tight=True,
    )
    dialog = _dialog(page, ft.Icons.MENU_BOOK_ROUNDED, T.INFO, "Hướng dẫn bật gỡ lỗi USB", body,
                     [("Đã hiểu", None, True, False)], width=620)
    page.show_dialog(dialog)
    return dialog


def show_message(page: ft.Page, title: str, message: str, color: str = T.DANGER,
                 icon: str = ft.Icons.ERROR_OUTLINE_ROUNDED) -> ft.AlertDialog:
    dialog = _dialog(page, icon, color, title, W.text(message, size=13.5), [("Đóng", None, True, False)])
    page.show_dialog(dialog)
    return dialog


def toast(page: ft.Page, message: str, color: str = T.SUCCESS,
          icon: str = ft.Icons.CHECK_CIRCLE_ROUNDED) -> ft.SnackBar:
    snack = ft.SnackBar(
        content=ft.Row([ft.Icon(icon, color=color, size=18),
                        ft.Text(message, color=T.WHITE, font_family=T.FONT_MEDIUM, size=13)], spacing=10),
        bgcolor="#1F2330",
        behavior=ft.SnackBarBehavior.FLOATING,
        shape=ft.RoundedRectangleBorder(radius=T.RADIUS),
        width=420,
        duration=ft.Duration(milliseconds=2600),
    )
    page.show_dialog(snack)
    return snack
