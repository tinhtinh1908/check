"""Build ``.build/payload.zip`` from the repo inputs (APK folder, platform-tools zip, Xiaomi USB driver).

- APKs and the platform-tools zip are already compressed: stored as-is (ZIP_STORED) so the app can
  stream them straight to the phone without extracting anything.
- The driver ``.7z`` (LZMA2 + BCJ) is unpacked here at build time, because Windows 10's built-in
  ``tar`` lacks LZMA support; the app then only needs stdlib ``zipfile`` at runtime.
- Skips work when the inputs are unchanged (fingerprint of paths, sizes and mtimes).

    python scripts/build_payload.py [--force] [--no-verify]
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bull_tool.core.payload import (  # noqa: E402
    APK_PREFIX,
    DRIVER_INF,
    DRIVER_PREFIX,
    PLATFORM_TOOLS_ZIP,
)

APK_DIR = ROOT / "APK"
PLATFORM_TOOLS = ROOT / PLATFORM_TOOLS_ZIP
DRIVER_7Z = ROOT / "USB_DRIVER_XIAOMI.7z"
BUILD_DIR = ROOT / ".build"
OUTPUT = BUILD_DIR / "payload.zip"
FINGERPRINT = BUILD_DIR / "payload.fingerprint.json"
STAGE = BUILD_DIR / "stage"
BUILDER_VERSION = 1
CREATE_NO_WINDOW = 0x08000000


def _input_files() -> list[Path]:
    apks = sorted(p for p in APK_DIR.rglob("*") if p.is_file())
    return [*apks, PLATFORM_TOOLS, DRIVER_7Z]


def fingerprint() -> dict:
    entries = []
    for path in _input_files():
        st = path.stat()
        entries.append([path.relative_to(ROOT).as_posix(), st.st_size, st.st_mtime_ns])
    return {"builder": BUILDER_VERSION, "inputs": entries}


def _seven_zip_candidates() -> list[list[str]]:
    """Extraction commands to try, in order: Windows tar (libarchive) then 7-Zip."""
    windir = os.environ.get("SystemRoot", r"C:\Windows")
    cmds = [[os.path.join(windir, "System32", "tar.exe"), "-xf", str(DRIVER_7Z), "-C", "{out}"]]
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            cmds.append([os.path.join(base, "7-Zip", "7z.exe"), "x", "-y", "-o{out}", str(DRIVER_7Z)])
    return cmds


def extract_driver() -> Path:
    """Unpack the driver archive into ``.build/stage`` and return the ``USB_DRIVER_XIAOMI`` folder."""
    shutil.rmtree(STAGE, ignore_errors=True)
    STAGE.mkdir(parents=True)
    errors = []
    for template in _seven_zip_candidates():
        if not Path(template[0]).exists():
            continue
        cmd = [part.replace("{out}", str(STAGE)) for part in template]
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)
        inf = STAGE / DRIVER_INF
        if result.returncode == 0 and inf.exists():
            return inf.parent
        errors.append(f"{Path(template[0]).name}: rc={result.returncode} {result.stderr.strip()[:200]}")
        shutil.rmtree(STAGE, ignore_errors=True)
        STAGE.mkdir(parents=True)
    details = "\n  ".join(errors)
    raise SystemExit(f"error: cannot extract {DRIVER_7Z.name} (needs Windows 11 tar or 7-Zip):\n  {details}")


def _check_disk_space() -> None:
    need = sum(p.stat().st_size for p in _input_files()) + 300 * 1024 * 1024
    free = shutil.disk_usage(ROOT).free
    if free < need:
        raise SystemExit(f"error: not enough disk space ({free >> 20} MB free, need {need >> 20} MB)")


def build(force: bool = False, verify: bool = True) -> Path:
    for required in (APK_DIR, PLATFORM_TOOLS, DRIVER_7Z):
        if not required.exists():
            raise SystemExit(f"error: missing input {required}")
    BUILD_DIR.mkdir(exist_ok=True)
    current = fingerprint()
    if not force and OUTPUT.exists() and FINGERPRINT.exists():
        if json.loads(FINGERPRINT.read_text(encoding="utf-8")) == current:
            print(f"payload up to date: {OUTPUT}")
            return OUTPUT

    _check_disk_space()
    started = time.perf_counter()
    driver_root = extract_driver()
    tmp = OUTPUT.with_suffix(".zip.tmp")
    count = 0
    with zipfile.ZipFile(tmp, "w", allowZip64=True) as zf:
        for path in sorted(p for p in APK_DIR.rglob("*") if p.is_file()):
            arcname = APK_PREFIX + path.relative_to(APK_DIR).as_posix()
            zf.write(path, arcname, compress_type=zipfile.ZIP_STORED)
            count += 1
            print(f"  + {arcname} ({path.stat().st_size / 1048576:.1f} MB)")
        zf.write(PLATFORM_TOOLS, PLATFORM_TOOLS_ZIP, compress_type=zipfile.ZIP_STORED)
        count += 1
        for path in sorted(p for p in driver_root.rglob("*") if p.is_file()):
            arcname = DRIVER_PREFIX + path.relative_to(driver_root).as_posix()
            zf.write(path, arcname, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
            count += 1
    if verify:
        with zipfile.ZipFile(tmp) as zf:
            bad = zf.testzip()
        if bad is not None:
            tmp.unlink(missing_ok=True)
            raise SystemExit(f"error: CRC check failed for {bad}")
    os.replace(tmp, OUTPUT)
    FINGERPRINT.write_text(json.dumps(current), encoding="utf-8")
    shutil.rmtree(STAGE, ignore_errors=True)
    size_mb = OUTPUT.stat().st_size / 1048576
    print(f"payload built: {OUTPUT} ({count} files, {size_mb:.1f} MB, {time.perf_counter() - started:.1f}s)")
    return OUTPUT


def main(argv: list[str]) -> int:
    build(force="--force" in argv, verify="--no-verify" not in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
