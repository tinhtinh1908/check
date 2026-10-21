"""One-command release build: assets → payload → flet pack (PyInstaller onefile + UPX) → inject payload →
verify → self-test. Output: ``release/BULL-TOOL.exe``.

    python scripts/build_exe.py [--skip-payload] [--keep-work]
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import build_assets  # noqa: E402
import build_payload  # noqa: E402
import inject_payload  # noqa: E402

from bull_tool import app_info  # noqa: E402

PYINSTALLER_VERSION = "6.22.3"
EXE_NAME = "BULL-TOOL"  # file name only (release/BULL-TOOL.exe); window, taskbar and product name stay "BULL TOOL"
WORK = ROOT / ".build" / "pack"
RELEASE = ROOT / "release"
UPX = ROOT / "upx.exe"
ASSETS = ROOT / "bull_tool" / "assets"
SELFTEST_REPORT = ROOT / ".build" / "selftest.json"


def step(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def check_environment() -> None:
    import PyInstaller

    problems = []
    if sys.version_info[:2] != (3, 14) or struct.calcsize("P") != 8:
        problems.append(f"need 64-bit Python 3.14, running {sys.version.split()[0]} ({struct.calcsize('P') * 8}-bit)")
    if PyInstaller.__version__ != PYINSTALLER_VERSION:
        problems.append(f"need PyInstaller {PYINSTALLER_VERSION} (payload layout is verified for it), "
                        f"found {PyInstaller.__version__}")
    if not UPX.exists():
        problems.append(f"missing {UPX}")
    free_gb = shutil.disk_usage(ROOT).free / 1e9
    if free_gb < 4:
        problems.append(f"need ≥ 4 GB free disk space, have {free_gb:.1f} GB")
    if problems:
        raise SystemExit("environment check failed:\n  " + "\n  ".join(problems))


def flet_pack() -> Path:
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    version = app_info.VERSION
    cmd = [
        # flet pack, plus the exe's own InternalName / OriginalFilename in its version resource
        sys.executable, str(ROOT / "scripts" / "flet_pack.py"), "pack", str(ROOT / "main.py"), "-y",
        "--name", EXE_NAME,
        "--distpath", "out",
        "--icon", str(ASSETS / "icon.ico"),
        "--product-name", app_info.APP_NAME,
        "--file-description", f"{app_info.APP_NAME} - Dọn rác & cài ứng dụng Android",
        "--product-version", version,
        "--file-version", f"{version}.0",
        "--company-name", app_info.COMPANY,
        "--copyright", f"© 2026 {app_info.COMPANY}",
        "--add-data", f"{ASSETS}{os.pathsep}bull_tool/assets",
        f"--pyinstaller-build-args=--upx-dir={ROOT}",
        "--pyinstaller-build-args=--upx-exclude=vcruntime140.dll",
        "--pyinstaller-build-args=--upx-exclude=vcruntime140_1.dll",
        "--pyinstaller-build-args=--upx-exclude=python3.dll",
        # Pillow is only a build-time dependency (build_assets); flet imports it lazily for RawImage, which the
        # app does not use. Excluding it keeps ~4 MB of .pyd out of the exe and out of every _MEI extraction.
        "--pyinstaller-build-args=--exclude-module=PIL",
    ]
    log_path = WORK / "pack.log"
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    with open(log_path, "w", encoding="utf-8") as log:
        result = subprocess.run(cmd, cwd=WORK, stdout=log, stderr=subprocess.STDOUT, env=env)
    text = log_path.read_text(encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(text[-4000:])
        raise SystemExit(f"flet pack failed (exit {result.returncode}); full log: {log_path}")
    exe = WORK / "out" / f"{EXE_NAME}.exe"
    if not exe.exists():
        raise SystemExit(f"flet pack did not produce {exe}")
    packed, total = count_upx_packed(exe)
    if packed == 0:
        raise SystemExit(f"UPX did not pack any binary; check {UPX} and the log: {log_path}")
    print(f"flet pack ok: {exe.stat().st_size / 1048576:.1f} MB · UPX packed {packed}/{total} DLL/PYD "
          f"({text.count('Disabling UPX')} skipped: CFG or excluded)")
    return exe


def count_upx_packed(exe: Path) -> tuple[int, int]:
    """(packed, total) DLL/PYD files inside the onefile archive. PyInstaller only logs the binaries it skips,
    so check each one for UPX's ``UPX0`` section name instead."""
    from PyInstaller.archive.readers import CArchiveReader

    reader = CArchiveReader(str(exe))
    binaries = [name for name in reader.toc if name.lower().endswith((".dll", ".pyd"))]
    packed = sum(b"UPX0" in reader.extract(name)[:4096] for name in binaries)
    return packed, len(binaries)


def run_self_test(exe: Path) -> None:
    SELFTEST_REPORT.unlink(missing_ok=True)
    result = subprocess.run([str(exe), "--self-test", "--full", "--report", str(SELFTEST_REPORT)], timeout=600)
    report = SELFTEST_REPORT.read_text(encoding="utf-8") if SELFTEST_REPORT.exists() else "(no report)"
    if result.returncode != 0:
        print(report)
        raise SystemExit(f"self-test failed (exit {result.returncode})")
    print(f"self-test ok: {SELFTEST_REPORT}")


def main(argv: list[str]) -> int:
    started = time.perf_counter()
    step("Kiểm tra môi trường build")
    check_environment()
    step("Sinh icon + logo")
    build_assets.main([])
    if "--skip-payload" not in argv:
        step("Đóng gói payload (APK, platform-tools, driver)")
        payload = build_payload.build()
    else:
        payload = build_payload.OUTPUT
    step("flet pack (PyInstaller onefile + UPX)")
    packed = flet_pack()
    step("Chèn payload vào exe + kiểm tra")
    RELEASE.mkdir(exist_ok=True)
    final = RELEASE / f"{EXE_NAME}.exe"
    staged = RELEASE / f"{EXE_NAME}.new.exe"
    inject_payload.inject(packed, payload, staged)
    inject_payload.verify(staged, payload, check_crc=True)
    os.replace(staged, final)
    step("Self-test exe")
    run_self_test(final)
    if "--keep-work" not in argv:
        shutil.rmtree(WORK, ignore_errors=True)
    size_gb = final.stat().st_size / 1e9
    print(f"\nDONE: {final} ({size_gb:.2f} GB) in {time.perf_counter() - started:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
