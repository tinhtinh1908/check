"""Headless self-test of a build: ``BULL-TOOL.exe --self-test [--full] [--report out.json]``.

Runs before any UI or single-instance check. Verifies the embedded payload, every resource the profiles
need, a clean platform-tools extraction (into a temp dir) and that the Flet runtime imports. The exe is
windowed (no console), so results go to the exit code and an optional JSON report.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from bull_tool import app_info
from bull_tool.core import paths
from bull_tool.core.events import EventBus, Logger
from bull_tool.core.payload import DRIVER_INF, PLATFORM_TOOLS_ZIP, ResourceStore
from bull_tool.core.platform_tools import ensure_platform_tools
from bull_tool.core.profiles import referenced_apks


def run_self_test(full: bool = False, report: Path | None = None) -> int:
    results: list[dict] = []
    store: ResourceStore | None = None

    def check(name: str, action: Callable[[], str]) -> None:
        started = time.perf_counter()
        try:
            detail, ok = action(), True
        except Exception as exc:  # noqa: BLE001 - every failure is reported, not raised
            detail, ok = f"{type(exc).__name__}: {exc}", False
        results.append({"check": name, "ok": ok, "detail": detail, "seconds": round(time.perf_counter() - started, 3)})

    def open_store() -> str:
        nonlocal store
        store = ResourceStore.open_default()
        return store.source

    def required_entries() -> str:
        needed = referenced_apks() | {PLATFORM_TOOLS_ZIP, DRIVER_INF}
        missing = sorted(needed - set(store.names()))
        if missing:
            raise AssertionError(f"missing: {missing}")
        return f"{len(needed)} required entries present"

    def platform_tools() -> str:
        with tempfile.TemporaryDirectory() as tmp:
            result = ensure_platform_tools(store, Logger(EventBus()), target=Path(tmp))
            return f"revision {result.revision}, {len(result.extracted)} files extracted and verified"

    def payload_crc() -> str:
        bad = store.testzip()
        if bad is not None:
            raise AssertionError(f"CRC error in {bad}")
        return f"{len(store.names())} entries, CRC OK"

    def flet_runtime() -> str:
        import flet
        import flet_desktop  # noqa: F401 - imported to prove the desktop client package is bundled

        return f"flet {getattr(flet, '__version__', '?')}"

    check("payload", open_store)
    if store is not None:
        check("required entries", required_entries)
        check("platform-tools", platform_tools)
        if full:
            check("payload CRC", payload_crc)
        store.close()
    check("flet runtime", flet_runtime)

    ok = all(item["ok"] for item in results)
    data = {
        "ok": ok,
        "app": app_info.APP_NAME,
        "version": app_info.VERSION,
        "frozen": paths.is_frozen(),
        "executable": sys.executable,
        "results": results,
    }
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(text, encoding="utf-8")
    if sys.stdout is not None:  # windowed builds have no console
        print(text)
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    report = None
    if "--report" in argv:
        index = argv.index("--report")
        if index + 1 < len(argv):
            report = Path(argv[index + 1])
    return run_self_test(full="--full" in argv, report=report)
