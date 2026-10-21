"""Brand profile picker: five cards (full / compact) or chips (narrow windows), with suggestion badge."""

from __future__ import annotations

import inspect
from collections.abc import Callable

import flet as ft

from bull_tool.core.profiles import Profile
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W

MARKS = {
    "xiaomi": ("Mi", T.WHITE),
    "oppo": ("OP", T.WHITE),
    "honor": ("HN", T.WHITE),
    "vivo": ("vi", T.WHITE),
    "sony": ("SO", "#14161B"),
}
CHIP_NAMES = {
    "xiaomi": "Xiaomi/Redmi",
    "oppo": "OPPO/Realme",
    "honor": "Honor/Huawei",
    "vivo": "vivo/iQOO",
    "sony": "Sony Xperia",
}


class _ProfileCard:
    def __init__(self, profile: Profile, on_pick: Callable[[str], object]) -> None:
        self.profile = profile
        self._on_pick = on_pick
        letters, fg = MARKS.get(profile.id, (profile.name[:2], T.WHITE))
        self._mark_text = ft.Text(letters, size=13, font_family=T.FONT_EXTRABOLD, color=fg)
        self.mark = ft.Container(
            content=self._mark_text, width=32, height=32, border_radius=10, bgcolor=profile.accent,
            alignment=ft.Alignment.CENTER,
        )
        self._badge = W.pill("Gợi ý", color=T.ACCENT)
        self._badge.visible = False
        # chips are too narrow for the pill next to the name: a small mark instead (selection shows as the border)
        self._chip_badge = ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=T.ACCENT, size=14, visible=False,
                                   tooltip="Gợi ý theo máy đang cắm")
        self._check = ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=T.ACCENT, size=20, visible=False)
        self._title = W.text(profile.name, size=13.5, family=T.FONT_SEMIBOLD, max_lines=2)
        self._summary = W.text(profile.short_summary, size=11.5, color=T.TEXT_MUTED, max_lines=1)
        # every card reserves the same lines so the row stays even without cross-axis stretching
        self._note = W.text(profile.note or " ", size=11, color=T.WARNING, max_lines=1)
        self._title_box = ft.Container(content=self._title, height=38, alignment=ft.Alignment.TOP_LEFT)
        self._top = ft.Row(spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        self.root = ft.Container(
            padding=ft.Padding(12, 12, 12, 12),
            border_radius=T.RADIUS,
            bgcolor=T.CARD_HOVER,
            border=ft.Border.all(1, T.BORDER),
            on_click=self._on_click,
            tooltip=f"{profile.name}\n{profile.summary}" + (f"\n{profile.note}" if profile.note else ""),
            animate=ft.Animation(T.DURATION, T.EASE),
            animate_scale=ft.Animation(T.DURATION, T.EASE),
            expand=True,
        )
        self.selected = False
        self.enabled = True
        self.density = "full"
        self.root.on_hover = self._on_hover
        self.render()

    async def _on_click(self, _e: ft.ControlEvent) -> None:
        result = self._on_pick(self.profile.id)
        if inspect.isawaitable(result):
            await result

    async def _on_hover(self, e: ft.ControlEvent) -> None:
        hovered = e.data in (True, "true") and self.enabled
        self.root.scale = 1.02 if hovered and not self.selected else 1.0
        if not self.selected:
            self.root.border = ft.Border.all(1, T.soft(self.profile.accent, 0.7) if hovered else T.BORDER)
        self.root.update()

    def render(self) -> None:
        compact = self.density != "full"
        chip = self.density == "chip"
        # a control may only have one parent: detach shared children from the layout not in use
        self._top.controls = [] if chip else [self.mark, ft.Container(expand=True), self._badge, self._check]
        self._title_box.content = None
        self._title.value = CHIP_NAMES.get(self.profile.id, self.profile.name) if chip else self.profile.name
        if chip:
            self.mark.width = self.mark.height = 26
            self._mark_text.size = 11
            self._title.max_lines = 1
            self._title.size = 12.5
            self.root.padding = ft.Padding(10, 8, 10, 8)
            self._title.expand = True
            self.root.content = ft.Row(
                [self.mark, self._title, self._chip_badge], spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        else:
            self.mark.width = self.mark.height = 32
            self._mark_text.size = 13
            self._title.max_lines = 1 if compact else 2
            self._title.size = 13.5
            self._title.expand = None
            self.root.padding = ft.Padding(12, 10, 12, 10) if compact else ft.Padding(12, 12, 12, 12)
            if compact:
                parts: list[ft.Control] = [self._top, self._title, self._summary]
            else:
                self._title_box.content = self._title
                parts = [self._top, self._title_box, self._summary, self._note]
            self.root.content = ft.Column(parts, spacing=6 if not compact else 4)
        self.root.border = ft.Border.all(1.5, T.ACCENT) if self.selected else ft.Border.all(1, T.BORDER)
        self.root.bgcolor = T.soft(T.ACCENT, 0.08) if self.selected else T.CARD_HOVER
        self.root.shadow = T.glow(T.ACCENT, 0.18) if self.selected else None
        self._check.visible = self.selected
        self.root.opacity = 1.0 if self.enabled else 0.55
        self.root.disabled = not self.enabled

    def set_badge(self, visible: bool) -> None:
        self._badge.visible = self._chip_badge.visible = visible and not self.selected


class ProfileGrid:
    def __init__(self, profiles: tuple[Profile, ...], on_pick: Callable[[str], object]) -> None:
        self.cards = {p.id: _ProfileCard(p, on_pick) for p in profiles}
        self._hint = W.text("Tự gợi ý theo máy đang cắm", size=12, color=T.TEXT_MUTED, max_lines=1)
        header = ft.Row(
            [W.icon_tile(ft.Icons.AUTO_AWESOME_ROUNDED, T.ACCENT_2, 30), W.overline("Chọn dòng máy"),
             ft.Container(expand=True), self._hint],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._grid = ft.Container()
        self.root = W.card(ft.Column([header, self._grid], spacing=12), padding=ft.Padding(16, 14, 16, 16))
        self.density = ""
        self.selected: str | None = None
        self.suggested: str | None = None
        self.apply_density("full")

    def apply_density(self, density: str) -> None:
        if density == self.density:
            return
        self.density = density
        for card in self.cards.values():
            card.density = density
            card.render()
        roots = [c.root for c in self.cards.values()]
        if density == "chip":
            for root in roots:
                root.col = {"xs": 6, "sm": 4}
            self._grid.content = ft.ResponsiveRow(roots, spacing=8, run_spacing=8)
        else:
            for root in roots:
                root.col = None
            self._grid.content = ft.Row(roots, spacing=10, vertical_alignment=ft.CrossAxisAlignment.START)

    def set_selected(self, profile_id: str | None) -> list[ft.Control]:
        self.selected = profile_id
        for pid, card in self.cards.items():
            card.selected = pid == profile_id
            card.set_badge(pid == self.suggested)
            card.render()
        return [self.root]

    def set_suggested(self, profile_id: str | None) -> list[ft.Control]:
        self.suggested = profile_id
        for pid, card in self.cards.items():
            card.set_badge(pid == profile_id)
        name = self.cards[profile_id].profile.name if profile_id in self.cards else ""
        self._hint.value = f"Gợi ý: {name}" if name else "Tự gợi ý theo máy đang cắm"
        self._hint.color = T.ACCENT if name else T.TEXT_MUTED
        return [self.root]

    def set_enabled(self, enabled: bool) -> list[ft.Control]:
        for card in self.cards.values():
            card.enabled = enabled
            card.render()
        return [self.root]

    def apply_layout(self, layout: T.Layout) -> None:
        self.apply_density(layout.density)
        self._hint.visible = layout.main_width >= 640
