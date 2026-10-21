"""Headless Flet page for UI tests: a real Session over a connection that encodes every message the way
flet's socket server does (the encoder records the snapshots the next diff compares against), so control
updates, dialogs and events behave as in the app without a window. Relies on flet internals; flet is pinned."""

from __future__ import annotations

import asyncio

import flet as ft
import msgpack
from flet.controls.base_control import BaseControl
from flet.messaging.connection import Connection
from flet.messaging.protocol import (
    Message,
    MessageAction,
    RegisterClientResponseBody,
    configure_encode_object_for_msgpack,
)
from flet.messaging.session import Session
from flet.pubsub.pubsub_hub import PubSubHub

import bull_tool.ui.app  # noqa: F401 - like the app: Flet auto-update off, so a handler that forgets update() shows

ENCODE = configure_encode_object_for_msgpack(BaseControl)


class EncodingConnection(Connection):
    def __init__(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        super().__init__()
        if loop is not None:
            self.loop = loop  # page.run_task schedules onto it
        self.pubsubhub = PubSubHub(loop)
        self.sent: list[bytes] = []

    def send_message(self, message: Message) -> None:
        self.sent.append(msgpack.packb([message.action, message.body], default=ENCODE))

    def last_patch_ops(self) -> list:
        """Operations of the most recent patch message (without the leading tree snapshot)."""
        return msgpack.unpackb(self.sent[-1], strict_map_key=False)[1]["patch"][1:]


def mount_page() -> tuple[ft.Page, Session, EncodingConnection]:
    """A registered page; call it inside a running event loop when the test needs page.run_task."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    conn = EncodingConnection(loop)
    session = conn.session = Session(conn)  # controls only hold weak references to the page: keep it alive
    conn.send_message(
        Message(MessageAction.REGISTER_CLIENT, RegisterClientResponseBody(session.id, session.get_page_patch(), ""))
    )
    return session.page, session, conn


async def click(session: Session, control: ft.Control) -> None:
    await session.dispatch_event(control._i, "click", None)


async def client_dismissed(session: Session, dialog: ft.DialogControl) -> None:
    """What the Flet client reports once a dialog or snack bar has gone: open=False, then the dismiss event."""
    session.apply_patch(dialog._i, {"open": False})
    await session.dispatch_event(dialog._i, "dismiss", None)
