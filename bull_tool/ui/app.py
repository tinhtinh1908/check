"""Flet entry: window chrome, themes and fonts, then the controller takes over."""

from __future__ import annotations

import atexit
from collections.abc import Callable

import flet as ft

from bull_tool import app_info
from bull_tool.core import paths, win32
from bull_tool.core.bootstrap import AppServices
from bull_tool.core.events import EventBus
from bull_tool.core.session_log import SessionLog
from bull_tool.core.settings import load_settings
from bull_tool.ui import theme as T
from bull_tool.ui.controller import AppController

# Every UI change is sent explicitly (UiPump flush, control.update(), page.update()). Flet's default
# auto-update would re-diff the whole page after each event handler (~60 ms with a full console). This runs at
# import, outside any session, so it sets the process default that every event task inherits.
ft.context.disable_auto_update()

DEFAULT_SIZE = (1280, 800)
MIN_SIZE = (880, 540)


def initial_window_size() -> tuple[int, int]:
    """Default size, shrunk to 92% of the work area on small screens."""
    width, height = DEFAULT_SIZE
    area = win32.work_area_logical()
    if area:
        width = min(width, int(area[0] * 0.92))
        height = min(height, int(area[1] * 0.92))
    return max(width, MIN_SIZE[0]), max(height, MIN_SIZE[1])


def configure_page(page: ft.Page, dark: bool, size: tuple[int, int]) -> None:
    page.title = app_info.APP_NAME
    page.fonts = T.FONTS
    page.theme = T.build_theme(dark=False)
    page.dark_theme = T.build_theme(dark=True)
    page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
    page.theme_animation_style = ft.AnimationStyle(duration=ft.Duration(milliseconds=250), curve=T.EASE)
    page.padding = 0
    page.spacing = 0
    page.bgcolor = T.BG
    window = page.window
    window.icon = str(paths.assets_dir() / "icon.ico")
    window.title_bar_hidden = True
    window.title_bar_buttons_hidden = True
    window.min_width, window.min_height = MIN_SIZE
    window.width, window.height = size
    window.prevent_close = True


def create_services() -> AppServices:
    settings = load_settings()
    bus = EventBus()
    session_log = SessionLog(bus)
    bus.add_listener(session_log.write)
    services = AppServices(bus, settings=settings, session_log=session_log)
    atexit.register(services.shutdown)  # covers a client that disappears without a close event
    return services


async def launch(
    page: ft.Page,
    services: AppServices,
    bootstrap=None,
    size: tuple[int, int] | None = None,
    wrap: Callable[[ft.Control], ft.Control] | None = None,
) -> AppController:
    """Configure the window and start the controller.

    ``bootstrap`` and ``wrap`` (e.g. a Screenshot around the UI) are injection points for the preview harness.
    """
    size = size or initial_window_size()
    configure_page(page, services.settings.theme == "dark", size)
    controller = AppController(page, services, bootstrap) if bootstrap else AppController(page, services)
    page.window.on_event = controller.on_window_event
    page.on_resize = controller.on_resize
    page.on_close = controller.on_session_closed
    controller.apply_layout(*size)
    root = controller.build()
    page.add(wrap(root) if wrap else root)
    controller.start()
    await page.window.center()
    return controller


async def main(page: ft.Page) -> None:
    await launch(page, create_services())
