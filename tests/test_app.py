import asyncio
import contextvars

import flet as ft

from bull_tool.core.bootstrap import AppServices
from bull_tool.core.events import EventBus
from bull_tool.ui import app
from tests.flet_harness import mount_page


def test_importing_the_app_turns_flet_auto_update_off_for_every_event():
    # a fresh context (like each event task's) falls back to the process default the import changed
    assert contextvars.Context().run(ft.context.auto_update_enabled) is False


def test_launch_routes_window_close_and_a_lost_client_to_the_controller(monkeypatch):
    async def scenario():
        page, _session, _conn = mount_page()

        async def no_client_call(_window) -> None:  # center() waits for the desktop client to answer
            pass

        monkeypatch.setattr(type(page.window), "center", no_client_call)
        controller = await app.launch(page, AppServices(EventBus()), bootstrap=lambda _services: True,
                                      size=(1280, 800))
        controller.pump.stop()
        return page, controller

    page, controller = asyncio.run(scenario())
    assert page.window.prevent_close is True
    assert page.window.on_event == controller.on_window_event
    assert page.on_close == controller.on_session_closed  # the client vanished: cancel the job, release adb
    assert page.on_resize == controller.on_resize
