"""Shop contact card (Di Động BULL) and the secondary partner advertisement (MTFLASH)."""

from __future__ import annotations

from collections.abc import Callable

import flet as ft

from bull_tool import app_info
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W


def _link_button(
    icon: str, label: str, color: str, url: str, open_url: Callable[[str], object]
) -> tuple[ft.Container, ft.Text]:
    """Equal-width icon + label link. Returns (button, label_text); the tooltip names the link for icon-only mode."""
    label_text = W.text(label, size=11.5, family=T.FONT_MEDIUM, color=T.TEXT, max_lines=1)
    button = ft.Container(
        content=ft.Column(
            [ft.Icon(icon, size=18, color=color), label_text],
            spacing=4,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(6, 8, 6, 8),
        border_radius=T.RADIUS,
        bgcolor=T.CARD_HOVER,
        border=ft.Border.all(1, T.BORDER),
        on_click=lambda _e: open_url(url),
        tooltip=f"{label} · {url}",
        expand=True,
        animate=ft.Animation(T.DURATION_FAST, T.EASE),
    )

    async def on_hover(e: ft.ControlEvent) -> None:
        hovered = e.data in (True, "true")
        button.border = ft.Border.all(1, T.soft(color, 0.8) if hovered else T.BORDER)
        button.bgcolor = T.soft(color, 0.10) if hovered else T.CARD_HOVER
        button.update()

    button.on_hover = on_hover
    return button, label_text


def _text_link(label: str, url: str, open_url: Callable[[str], object]) -> ft.Container:
    text = W.text(label, size=12, family=T.FONT_SEMIBOLD, color=T.ACCENT_2, max_lines=1)
    link = ft.Container(content=text, on_click=lambda _e: open_url(url), tooltip=url, padding=ft.Padding(0, 2, 0, 2))

    async def on_hover(e: ft.ControlEvent) -> None:
        text.style = ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE if e.data in (True, "true") else None)
        text.update()

    link.on_hover = on_hover
    return link


class ContactCards:
    def __init__(self, open_url: Callable[[str], object]) -> None:
        logo = ft.Container(
            content=ft.Image(src="bull_logo_256.png", fit=ft.BoxFit.CONTAIN, filter_quality=ft.FilterQuality.HIGH),
            width=56,
            height=56,
            bgcolor=T.WHITE,
            border_radius=14,
            padding=3,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=T.shadow(0.6),
        )
        links = [
            _link_button(ft.Icons.LANGUAGE_ROUNDED, "Website", T.ACCENT, app_info.WEBSITE, open_url),
            _link_button(ft.Icons.FACEBOOK_ROUNDED, "Facebook", "#1877F2", app_info.FACEBOOK, open_url),
            _link_button(ft.Icons.CHAT_ROUNDED, "Zalo", "#0068FF", app_info.ZALO, open_url),
        ]
        self._link_labels = [label for _button, label in links]
        shop = W.card(
            ft.Column(
                [
                    ft.Row(
                        [
                            logo,
                            ft.Column(
                                [
                                    W.text(app_info.COMPANY, size=15, family=T.FONT_BOLD, max_lines=1),
                                    W.text(app_info.SHOP_TAGLINE, size=12, color=T.TEXT_MUTED, max_lines=2),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row([button for button, _label in links], spacing=8),
                ],
                spacing=12,
            ),
            padding=ft.Padding(14, 14, 14, 14),
        )
        ad_logo = ft.Container(
            content=ft.Image(src="mtflash_256.png", fit=ft.BoxFit.CONTAIN, filter_quality=ft.FilterQuality.HIGH),
            width=44,
            height=44,
        )
        partner = ft.Container(
            content=ft.Row(
                [
                    ad_logo,
                    ft.Column(
                        [
                            ft.Row([W.text(app_info.AD_NAME, size=13, family=T.FONT_BOLD, max_lines=1),
                                    W.pill("Đối tác", color=T.INFO, size=10)], spacing=6),
                            W.text(app_info.AD_SERVICES, size=11.5, color=T.TEXT_MUTED, max_lines=2),
                            ft.Row(
                                [_text_link(app_info.AD_SITE_LABEL, app_info.AD_SITE, open_url),
                                 W.text("·", size=12, color=T.TEXT_MUTED),
                                 _text_link("Facebook", app_info.AD_FACEBOOK, open_url)],
                                spacing=6,
                                wrap=True,
                            ),
                        ],
                        spacing=3,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=T.RADIUS_LG,
            border=ft.Border.all(1, T.BORDER),
            bgcolor=T.soft(T.INFO, 0.05),
        )
        self.controls = [shop, partner]

    def apply_layout(self, layout: T.Layout) -> None:
        # below a 288 px sidebar "Facebook" no longer fits a third of the row: icons only, the tooltip names the link
        for label in self._link_labels:
            label.visible = layout.sidebar >= 288
