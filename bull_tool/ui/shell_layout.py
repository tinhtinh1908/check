"""Window shell: title bar, scrollable sidebar + main column (profiles, progress, console), status bar."""

from __future__ import annotations

import flet as ft

from bull_tool.ui import theme as T


class ShellLayout:
    def __init__(
        self,
        title_bar: ft.Control,
        status_bar: ft.Control,
        sidebar: list[ft.Control],
        main_top: list[ft.Control],
        console: ft.Control,
    ) -> None:
        self.sidebar_column = ft.Column(sidebar, spacing=16, scroll=ft.ScrollMode.AUTO)
        self.sidebar = ft.Container(content=self.sidebar_column, width=316, padding=ft.Padding(0, 0, 6, 0))
        self.main = ft.Column([*main_top, console], spacing=16, expand=True)
        self.body = ft.Row(
            [self.sidebar, self.main], spacing=16, expand=True, vertical_alignment=ft.CrossAxisAlignment.STRETCH
        )
        self.body_box = ft.Container(content=self.body, padding=16, expand=True)
        glow = ft.Container(
            left=0, top=0, right=0, bottom=0,
            gradient=ft.RadialGradient(
                center=ft.Alignment(-1.0, -1.0), radius=1.3, colors=[T.soft(T.ACCENT, 0.09), T.soft(T.ACCENT, 0.0)]
            ),
        )
        content = ft.Container(
            left=0, top=0, right=0, bottom=0,
            content=ft.Column([title_bar, self.body_box, status_bar], spacing=0, expand=True),
        )
        self.root = ft.Stack([glow, content], expand=True)

    def apply(self, layout: T.Layout) -> None:
        self.sidebar.width = layout.sidebar
        self.sidebar_column.spacing = layout.gap
        self.body.spacing = layout.gap
        self.main.spacing = layout.gap
        self.body_box.padding = layout.gap
