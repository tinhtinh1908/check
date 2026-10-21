"""ConsoleView on a headless Flet page: which controls a log tick re-sends and what reaches the client."""

import asyncio
import dataclasses
from collections.abc import Callable

import flet as ft
import msgpack
from flet.controls.object_patch import DiffBuilder, Operation

from bull_tool.core.events import Level, LogEvent
from bull_tool.ui import console_view
from bull_tool.ui.console_view import CHUNK_LINES, MAX_LINES, ConsoleView
from tests.flet_harness import EncodingConnection, mount_page

ADD, REPLACE = Operation.Add.value, Operation.Replace.value


def lines(count: int, start: int = 0) -> list[LogEvent]:
    return [LogEvent(Level.INFO, f"line {i}") for i in range(start, start + count)]


def mounted_console() -> tuple[ConsoleView, Callable[[], None], EncodingConnection]:
    """A ConsoleView on a headless page; flush() updates the controls it marked dirty, like UiPump.flush."""
    page, _session, conn = mount_page()
    dirty: dict[int, ft.Control] = {}
    view = ConsoleView(lambda *cs: dirty.update((id(c), c) for c in cs), lambda _text: None, lambda _text: None)
    page.add(view.root)

    def flush() -> None:
        for control in dirty.values():
            control.update()
        dirty.clear()

    return view, flush, conn


def sent_ops(conn: EncodingConnection, control: ft.Control, since: int) -> list:
    """Operations of the patches addressed to ``control`` among the messages sent after ``conn.sent[:since]``."""
    ops = []
    for raw in conn.sent[since:]:
        body = msgpack.unpackb(raw, strict_map_key=False)[1]
        if body.get("id") == control._i:
            ops.extend(body["patch"][1:])
    return ops


def added(ops: list, control_type: str) -> list[dict]:
    """Controls of ``control_type`` that ``ops`` add, each sent with all its props."""
    return [op[-1] for op in ops if op[0] == ADD and isinstance(op[-1], dict) and op[-1].get("_c") == control_type]


def test_starting_a_chunk_on_a_full_console_does_not_rediff_old_spans(monkeypatch):
    view, flush, _conn = mounted_console()
    for start in range(0, MAX_LINES, CHUNK_LINES):
        view.append(lines(CHUNK_LINES, start))
        flush()
    compared = []
    original = DiffBuilder._compare_dataclasses

    def recording(self, parent, path, src, dst, frozen):
        compared.append((parent, dst))
        return original(self, parent, path, src, dst, frozen)

    monkeypatch.setattr(DiffBuilder, "_compare_dataclasses", recording)
    view.append(lines(CHUNK_LINES + 1, MAX_LINES))  # starts a chunk and drops the oldest: one list update
    flush()
    assert len(view.list.controls) == console_view.MAX_CHUNKS
    assert sum(len(chunk.spans) for chunk in view.list.controls) >= 3 * MAX_LINES
    assert any(parent is view.list for parent, _dst in compared)  # the chunks' own props were still diffed
    assert [dst for parent, dst in compared if isinstance(parent, ft.TextSpan)] == []  # not each sent span's style


def test_a_tick_that_crosses_a_chunk_boundary_sends_lines_to_both_chunks():
    view, flush, conn = mounted_console()
    view.append(lines(CHUNK_LINES - 3))
    flush()
    mark = len(conn.sent)
    view.append(lines(10, CHUNK_LINES - 3))  # 3 lines finish the first chunk, 7 start the second
    flush()
    ops = sent_ops(conn, view.list, mark)
    assert len(added(ops, "TextSpan")) == 3 * 3  # appended to the first chunk, 3 spans per line
    [new_chunk] = added(ops, "Text")
    assert len(new_chunk["spans"]) == 7 * 3


def test_a_font_size_change_reaches_every_chunk():
    view, flush, conn = mounted_console()
    view.append(lines(5 * CHUNK_LINES))
    flush()
    mark = len(conn.sent)
    view.set_font_size(14.0)
    flush()
    size_ops = [op for op in sent_ops(conn, view.list, mark) if op[0] == REPLACE and op[-2:] == ["size", 14.0]]
    assert len(size_ops) == len(view.list.controls) == 5


def test_trimming_keeps_one_list_update_per_new_chunk(monkeypatch):
    monkeypatch.setattr(console_view, "MAX_LINES", 1500)  # not a multiple of CHUNK_LINES
    monkeypatch.setattr(console_view, "MAX_CHUNKS", 1500 // CHUNK_LINES + 1)
    list_updates: list[bool] = []
    view = ConsoleView(
        lambda *cs: list_updates.append(any(c is view.list for c in cs)), lambda _text: None, lambda _text: None
    )
    for start in range(0, 3000, 10):  # 200 lines/s in 10-line ticks
        view.append(lines(10, start))
    assert len(view.list.controls) == console_view.MAX_CHUNKS
    full = 1600 // 10  # a tick on a chunk boundary, after the console filled up and started trimming
    assert sum(list_updates[full:]) == (3000 - 1600) // CHUNK_LINES  # one per new chunk, none extra for trims


def test_a_chunk_is_isolated_and_still_sent_as_a_text_control():
    view, flush, conn = mounted_console()
    view.append(lines(CHUNK_LINES))
    flush()
    mark = len(conn.sent)
    view.append(lines(1, CHUNK_LINES))  # starts the second chunk
    flush()
    chunk = view.list.controls[-1]
    assert chunk.is_isolated()
    [sent] = [op[-1] for op in sent_ops(conn, view.list, mark) if op[0] == ADD]
    assert sent["_i"] == chunk._i and sent["_c"] == "Text" and len(sent["spans"]) == 3
    assert set(sent) <= {f.name for f in dataclasses.fields(ft.Text)}  # nothing isolation-specific on the wire


def test_clear_empties_the_list_and_the_line_count():
    view, flush, conn = mounted_console()
    view.append(lines(2 * CHUNK_LINES + 5))
    flush()
    mark = len(conn.sent)
    asyncio.run(view._clear(None))
    assert view.list.controls == [] and view.text() == ""
    assert sent_ops(conn, view.list, mark) == [[REPLACE, 0, "controls", []]]
    assert view._count.content.value == "0 dòng"
    assert [op[-1] for op in sent_ops(conn, view._count, mark)] == ["0 dòng"]
    view.append(lines(1))
    assert len(view.list.controls) == 1 and view._chunk_sizes == [1]  # the next line starts a fresh chunk
