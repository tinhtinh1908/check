"""End-to-end check of the payload layout against a real PyInstaller onefile executable (slow)."""

import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import inject_payload  # noqa: E402

PROBE = """
from bull_tool.core.payload import ResourceStore
store = ResourceStore.open_default()
print("|".join(store.names()))
print(store.testzip())
"""


@pytest.mark.slow
def test_injected_exe_runs_and_reads_payload(tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(PROBE, encoding="utf-8")
    build = subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--onefile", "--console", "--noconfirm",
            "--log-level", "WARN",
            "--distpath", str(tmp_path / "out"), "--workpath", str(tmp_path / "work"),
            "--specpath", str(tmp_path), "--paths", str(ROOT), str(probe),
        ],
        capture_output=True, text=True, cwd=tmp_path,
    )
    assert build.returncode == 0, build.stderr[-2000:]
    src_exe = tmp_path / "out" / "probe.exe"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("APK/big.apk", os.urandom(3 * 1024 * 1024))
        zf.writestr("USB_DRIVER_XIAOMI/android_winusb.inf", "; inf")
    payload = tmp_path / "payload.zip"
    payload.write_bytes(buf.getvalue())

    out_exe = tmp_path / "release" / "probe.exe"
    inject_payload.inject(src_exe, payload, out_exe)
    inject_payload.verify(out_exe, payload)

    run = subprocess.run([str(out_exe)], capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stderr[-2000:]
    lines = run.stdout.strip().splitlines()
    assert lines[0] == "APK/big.apk|USB_DRIVER_XIAOMI/android_winusb.inf"
    assert lines[1] == "None"
