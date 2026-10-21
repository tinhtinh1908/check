"""BULL TOOL entry point."""

from __future__ import annotations

import sys

SINGLE_INSTANCE_MUTEX = "Local\\BULL-TOOL-single-instance"


def run() -> None:
    if "--self-test" in sys.argv:  # headless build verification: no UI, no single-instance lock
        from bull_tool.core.self_test import main as self_test

        sys.exit(self_test(sys.argv[1:]))

    import flet as ft

    from bull_tool import app_info
    from bull_tool.core import paths, win32
    from bull_tool.ui import app

    if not win32.acquire_single_instance(SINGLE_INSTANCE_MUTEX):
        win32.focus_window(app_info.APP_NAME)
        return
    try:
        ft.run(app.main, assets_dir=str(paths.assets_dir()))
    finally:
        win32.release_single_instance()


if __name__ == "__main__":
    run()
