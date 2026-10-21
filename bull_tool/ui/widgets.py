"""Small reusable control builders that share the design tokens (cards, pills, buttons, text)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import flet as ft

from bull_tool.ui import theme as T

Handler = Callable[[ft.ControlEvent], Awaitable[None] | None]


def text(
    value: str = "",
    size: float = 13.5,
    family: str = T.FONT,
    color: str = T.TEXT,
    max_lines: int | None = None,
    expand: bool | int | None = None,
    **kwargs,
) -> ft.Text:
    return ft.Text(
        value,
        size=size,
        font_family=family,
        font_family_fallback=T.FALLBACK,
        color=color,
        max_lines=max_lines,
        overflow=ft.TextOverflow.ELLIPSIS if max_lines else ft.TextOverflow.CLIP,
        expand=expand,
        **kwargs,
    )


def overline(value: str, color: str = T.TEXT_MUTED) -> ft.Text:
    return ft.Text(
        value.upper(),
        size=11,
        font_family=T.FONT_SEMIBOLD,
        color=color,
        style=ft.TextStyle(letter_spacing=0.9),
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )


def card(content: ft.Control, padding: float = 16, expand: bool | int | None = None, **kwargs) -> ft.Container:
    return ft.Container(
        content=content,
        padding=padding,
        bgcolor=T.CARD,
        border=ft.Border.all(1, T.BORDER),
        border_radius=T.RADIUS_LG,
        shadow=T.shadow(),
        expand=expand,
        **kwargs,
    )


def pill(value: str, color: str = T.TEXT_MUTED, bg: str | None = None, size: float = 11) -> ft.Container:
    return ft.Container(
        content=ft.Text(value, size=size, font_family=T.FONT_SEMIBOLD, color=color, max_lines=1),
        bgcolor=bg or T.soft(color, 0.12),
        border_radius=20,
        padding=ft.Padding(8, 2, 8, 3),
    )


def icon_tile(icon: str, color: str, size: int = 34) -> ft.Container:
    """Rounded square with a tinted background and an icon (used in tool rows and headers)."""
    return ft.Container(
        content=ft.Icon(icon, size=size * 0.55, color=color),
        width=size,
        height=size,
        bgcolor=T.soft(color, 0.14),
        border_radius=size * 0.3,
        alignment=ft.Alignment.CENTER,
    )


def gradient_button(
    label: str, icon: str, on_click: Handler, gradient: ft.Gradient = T.ACCENT_GRADIENT, height: float = 48
) -> tuple[ft.Container, ft.Text, ft.Icon]:
    """Primary call-to-action with a gradient fill and glow. Returns (button, label_text, icon)."""
    icon_ctrl = ft.Icon(icon, color=T.WHITE, size=22)
    label_ctrl = ft.Text(
        label, color=T.WHITE, size=14, font_family=T.FONT_BOLD, style=ft.TextStyle(letter_spacing=0.6), max_lines=1
    )
    button = ft.Container(
        content=ft.Row([icon_ctrl, label_ctrl], alignment=ft.MainAxisAlignment.CENTER, spacing=8, tight=True),
        gradient=gradient,
        border_radius=T.RADIUS,
        height=height,
        padding=ft.Padding(18, 0, 22, 0),
        alignment=ft.Alignment.CENTER,
        shadow=T.glow(),
        on_click=on_click,
        animate=ft.Animation(T.DURATION, T.EASE),
        animate_scale=ft.Animation(T.DURATION_FAST, T.EASE),
        animate_opacity=ft.Animation(T.DURATION, T.EASE),
        ink=False,
    )

    async def on_hover(e: ft.ControlEvent) -> None:
        if button.disabled:
            return
        button.scale = 1.03 if e.data in (True, "true") else 1.0
        button.update()

    button.on_hover = on_hover
    return button, label_ctrl, icon_ctrl


def style_cta(
    button: ft.Container,
    label: ft.Text,
    icon: ft.Icon,
    enabled: bool,
    gradient: ft.Gradient = T.ACCENT_GRADIENT,
    glow_color: str = T.ACCENT,
) -> None:
    """Enabled: vivid gradient + glow. Disabled: neutral surface so it clearly reads as unavailable."""
    button.disabled = not enabled
    button.gradient = gradient if enabled else None
    button.bgcolor = None if enabled else T.CARD_ACTIVE
    button.shadow = T.glow(glow_color, 0.32) if enabled else None
    button.border = None if enabled else ft.Border.all(1, T.BORDER)
    button.scale = 1.0
    label.color = T.WHITE if enabled else T.TEXT_MUTED
    icon.color = T.WHITE if enabled else T.TEXT_MUTED


def ghost_button(label: str, icon: str, on_click: Handler, color: str = T.TEXT) -> ft.Container:
    """Secondary text button with a hover tint."""
    row = ft.Row(
        [ft.Icon(icon, size=16, color=color), ft.Text(label, size=12.5, font_family=T.FONT_MEDIUM, color=color)],
        spacing=6,
        tight=True,
    )
    button = ft.Container(
        content=row,
        padding=ft.Padding(10, 6, 12, 6),
        border_radius=T.RADIUS_SM,
        on_click=on_click,
        animate=ft.Animation(T.DURATION_FAST, T.EASE),
    )

    async def on_hover(e: ft.ControlEvent) -> None:
        button.bgcolor = T.soft(color, 0.10) if e.data in (True, "true") else None
        button.update()

    button.on_hover = on_hover
    return button


def icon_button(icon: str, tooltip: str, on_click: Handler, color: str = T.TEXT_MUTED, size: int = 18) -> ft.IconButton:
    return ft.IconButton(
        icon=icon,
        icon_size=size,
        icon_color=color,
        tooltip=tooltip,
        on_click=on_click,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=T.RADIUS_SM), padding=6),
    )


def divider() -> ft.Container:
    return ft.Container(height=1, bgcolor=T.BORDER)
