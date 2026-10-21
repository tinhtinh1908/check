"""High-volume console: colored, chunked rendering (40 lines per isolated Text) so updates stay cheap.

Lines are kept in a bounded buffer (copy/save use it); the visible list keeps the newest ~3000 lines and drops
the oldest chunk when a new one starts. Auto-scroll pauses while the user reads older lines and resumes when
scrolled back to the bottom.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable

import flet as ft

from bull_tool.core.events import Level, LogEvent
from bull_tool.ui import theme as T
from bull_tool.ui import widgets as W
from bull_tool.ui.ui_pump import is_attached

CHUNK_LINES = 40
MAX_LINES = 3000
MAX_CHUNKS = MAX_LINES // CHUNK_LINES + 1  # trimmed by chunk count, so a trim shares the list update of a new chunk
BOTTOM_TOLERANCE = 48

# level -> (marker, marker colour, text colour)
LEVEL_STYLE = {
    Level.INFO: ("•", "#7C8599", T.CONSOLE_TEXT),
    Level.OK: ("✓", T.SUCCESS, T.CONSOLE_TEXT),
    Level.SKIP: ("–", T.CONSOLE_DIM, T.CONSOLE_DIM),
    Level.WARN: ("!", T.WARNING, "#FCD34D"),
    Level.ERROR: ("✗", T.DANGER, "#FCA5A5"),
    Level.CMD: ("$", T.CMD, "#67E8F9"),
    Level.STEP: ("━", T.ACCENT_2, T.ACCENT_2),
}


@ft.control(isolated=True)
class _Chunk(ft.Text):
    """Up to CHUNK_LINES console lines. Invariant: a span is never edited after it is sent; new ones are appended.

    Isolated, so ListView and page diffs skip the spans a chunk already holds instead of re-walking all of them
    (a list update on a full console took ~60 ms, ~13 ms with isolated chunks). The parent still diffs the chunk's
    own props (size) and its span list, so font-size changes and appended spans are sent; an in-place edit of a
    sent span would only reach the client through chunk.update().
    """


class ConsoleView:
    def __init__(
        self,
        mark_dirty: Callable[..., None],
        on_copy: Callable[[str], object],
        on_save: Callable[[str], object],
    ) -> None:
        self._mark_dirty = mark_dirty
        self._on_copy = on_copy
        self._on_save = on_save
        self._lines: deque[tuple[float, Level, str]] = deque(maxlen=MAX_LINES * 2)
        self._chunk_sizes: list[int] = []
        self._font_size = 12.5
        self.auto_scroll = True
        self._pending_scroll = False
        self._scroll_scheduled = False

        self.list = ft.ListView(
            expand=True,
            spacing=0,
            padding=ft.Padding(14, 10, 14, 12),
            build_controls_on_demand=True,
            on_scroll=self._on_scroll,
        )
        self._count = W.pill("0 dòng", color=T.CONSOLE_DIM, bg=T.soft(T.WHITE, 0.06))
        self._follow_icon = ft.Icon(ft.Icons.VERTICAL_ALIGN_BOTTOM_ROUNDED, size=16, color=T.SUCCESS)
        self._follow_text = ft.Text("Tự cuộn", size=12, font_family=T.FONT_MEDIUM, color=T.SUCCESS)
        follow = ft.Container(
            content=ft.Row([self._follow_icon, self._follow_text], spacing=4, tight=True),
            padding=ft.Padding(8, 4, 10, 4),
            border_radius=T.RADIUS_SM,
            on_click=self._toggle_follow,
            tooltip="Bật/tắt tự cuộn xuống dòng mới nhất",
        )

        def tool(icon: str, tip: str, handler) -> ft.IconButton:
            return W.icon_button(icon, tip, handler, color=T.CONSOLE_DIM, size=17)

        header = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.TERMINAL_ROUNDED, size=16, color=T.ACCENT_2),
                    W.overline("Console", color="#AEB5C2"),
                    self._count,
                    ft.Container(expand=True),
                    follow,
                    tool(ft.Icons.CONTENT_COPY_ROUNDED, "Sao chép toàn bộ log", self._copy),
                    tool(ft.Icons.SAVE_ALT_ROUNDED, "Lưu log ra file .txt", self._save),
                    tool(ft.Icons.DELETE_SWEEP_ROUNDED, "Xoá màn hình console", self._clear),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(14, 6, 6, 6),
            bgcolor=T.CONSOLE_HEADER,
            border=ft.Border(bottom=ft.BorderSide(1, T.CONSOLE_BORDER)),
        )
        self.root = ft.Container(
            content=ft.Column([header, self.list], spacing=0, expand=True),
            bgcolor=T.CONSOLE_BG,
            border=ft.Border.all(1, T.CONSOLE_BORDER),
            border_radius=T.RADIUS_LG,
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
            shadow=T.shadow(),
            expand=True,
        )

    # -- rendering -------------------------------------------------------------------------------
    def _spans(self, event: LogEvent, first: bool) -> list[ft.TextSpan]:
        marker, marker_color, text_color = LEVEL_STYLE.get(event.level, LEVEL_STYLE[Level.INFO])
        stamp = time.strftime("%H:%M:%S", time.localtime(event.ts))
        prefix = "" if first else "\n"
        bold = event.level in (Level.STEP, Level.ERROR)
        return [
            ft.TextSpan(f"{prefix}{stamp} ", ft.TextStyle(color=T.CONSOLE_TIME)),
            ft.TextSpan(f"{marker} ", ft.TextStyle(color=marker_color, font_family=T.MONO_BOLD)),
            ft.TextSpan(event.text, ft.TextStyle(color=text_color, font_family=T.MONO_BOLD if bold else T.MONO)),
        ]

    def _new_chunk(self) -> _Chunk:
        chunk = _Chunk(
            spans=[],
            selectable=True,
            font_family=T.MONO,
            size=self._font_size,
            style=ft.TextStyle(height=1.5),
            color=T.CONSOLE_TEXT,
        )
        self.list.controls.append(chunk)
        self._chunk_sizes.append(0)
        return chunk

    def append(self, events: list[LogEvent]) -> None:
        if not events:
            return
        structure_changed = False
        touched: list[ft.Text] = []
        for event in events:
            self._lines.append((event.ts, event.level, event.text))
            if not self._chunk_sizes or self._chunk_sizes[-1] >= CHUNK_LINES:
                chunk = self._new_chunk()
                structure_changed = True
            else:
                chunk = self.list.controls[-1]
            chunk.spans.extend(self._spans(event, first=self._chunk_sizes[-1] == 0))
            self._chunk_sizes[-1] += 1
            if not touched or touched[-1] is not chunk:
                touched.append(chunk)
        while len(self._chunk_sizes) > MAX_CHUNKS:
            self.list.controls.pop(0)
            self._chunk_sizes.pop(0)
            structure_changed = True
        self._count.content.value = f"{len(self._lines):,} dòng".replace(",", ".")
        # Diffing the whole list every tick is the expensive part: only re-send the chunk(s) that grew,
        # and the list itself only when chunks were added or dropped.
        self._mark_dirty(self._count, *([self.list] if structure_changed else touched))
        if self.auto_scroll:
            self._pending_scroll = True

    async def scroll_if_needed(self) -> None:
        """Called by the pump after updates were flushed: keep the newest line in view.

        The jump runs in its own task a moment later, once the client has laid out the new lines;
        jumping immediately would land on the previous end of the list.
        """
        if self._pending_scroll and self.auto_scroll and not self._scroll_scheduled and is_attached(self.list):
            self._pending_scroll = False
            self._scroll_scheduled = True
            self.list.page.run_task(self._jump_to_end)

    async def _jump_to_end(self) -> None:
        try:
            await asyncio.sleep(0.06)
            if self.auto_scroll and is_attached(self.list):
                await self.list.scroll_to(offset=-1, duration=0)
        except RuntimeError:  # the session closed while the jump was pending (the window is going away)
            pass
        finally:
            self._scroll_scheduled = False

    def set_font_size(self, size: float) -> None:
        if size == self._font_size:
            return
        self._font_size = size
        for chunk in self.list.controls:
            chunk.size = size
        self._mark_dirty(self.list)

    def text(self) -> str:
        return "\n".join(
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))} [{level.value.upper()}] {text}"
            for ts, level, text in self._lines
        )

    # -- interactions ---------------------------------------------------------------------------
    def _set_follow(self, follow: bool) -> None:
        if follow == self.auto_scroll:
            return
        self.auto_scroll = follow
        color = T.SUCCESS if follow else T.CONSOLE_DIM
        self._follow_icon.color = color
        self._follow_text.color = color
        self._follow_text.value = "Tự cuộn" if follow else "Đã dừng cuộn"
        self._mark_dirty(self._follow_icon, self._follow_text)

    async def _on_scroll(self, e: ft.OnScrollEvent) -> None:
        if e.max_scroll_extent is None or e.pixels is None:
            return
        at_bottom = e.pixels >= e.max_scroll_extent - BOTTOM_TOLERANCE
        # Only a real user gesture towards older lines (wheel/drag up = FORWARD) pauses following;
        # plain UPDATE events also fire while new lines grow the list and must not pause it.
        user_scrolled_up = e.event_type == ft.ScrollType.USER and e.direction == ft.ScrollDirection.FORWARD
        if user_scrolled_up and not at_bottom and self.auto_scroll:
            self._set_follow(False)
        elif at_bottom and not self.auto_scroll and e.event_type in (ft.ScrollType.END, ft.ScrollType.USER):
            self._set_follow(True)

    async def _toggle_follow(self, _e) -> None:
        self._set_follow(not self.auto_scroll)
        if self.auto_scroll:
            self._pending_scroll = True
            await self.scroll_if_needed()
        self._follow_icon.update()
        self._follow_text.update()

    async def _copy(self, _e) -> None:
        await self._on_copy(self.text())

    async def _save(self, _e) -> None:
        await self._on_save(self.text())

    async def _clear(self, _e) -> None:
        self._lines.clear()
        self._chunk_sizes.clear()
        self.list.controls.clear()
        self._count.content.value = "0 dòng"
        self.list.update()
        self._count.update()
