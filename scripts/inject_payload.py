"""Insert the payload zip into a PyInstaller onefile exe, just before its PKG archive, and verify it.

    python scripts/inject_payload.py SRC_EXE PAYLOAD_ZIP OUT_EXE [--no-crc]
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bull_tool.core.payload import (  # noqa: E402
    PAYLOAD_MAGIC,
    TRAILER,
    ResourceStore,
    locate_payload,
    pyinstaller_pkg_start,
)

_CHUNK = 4 * 1024 * 1024


def _copy_range(src, dst, length: int) -> None:
    remaining = length
    while remaining > 0:
        chunk = src.read(min(_CHUNK, remaining))
        if not chunk:
            raise OSError("unexpected end of file while copying")
        dst.write(chunk)
        remaining -= len(chunk)


def inject(src_exe: Path, payload_zip: Path, out_exe: Path) -> None:
    """Write ``[head][payload][trailer][pkg]`` to ``out_exe`` (atomic replace)."""
    with open(src_exe, "rb") as src:
        pkg_start = pyinstaller_pkg_start(src)
        src.seek(0, os.SEEK_END)
        total = src.tell()
        tmp = out_exe.with_name(out_exe.name + ".tmp")
        out_exe.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, "wb") as out:
            src.seek(0)
            _copy_range(src, out, pkg_start)
            with open(payload_zip, "rb") as payload:
                shutil.copyfileobj(payload, out, _CHUNK)
            out.write(TRAILER.pack(PAYLOAD_MAGIC, payload_zip.stat().st_size))
            src.seek(pkg_start)
            _copy_range(src, out, total - pkg_start)
    os.replace(tmp, out_exe)


def verify(out_exe: Path, payload_zip: Path, check_crc: bool = True) -> None:
    """Cross-check the PKG offset with PyInstaller's own reader and that the payload reads back intact."""
    from PyInstaller.archive.readers import CArchiveReader

    reader = CArchiveReader(str(out_exe))
    if not reader.toc:
        raise SystemExit("verify: PyInstaller archive TOC is empty")
    with open(out_exe, "rb") as fp:
        ours = pyinstaller_pkg_start(fp)
    if reader._start_offset != ours:  # noqa: SLF001 - independent cross-check of the cookie math
        raise SystemExit(f"verify: PKG offset mismatch (pyinstaller={reader._start_offset}, ours={ours})")
    _offset, length = locate_payload(out_exe)
    if length != payload_zip.stat().st_size:
        raise SystemExit("verify: payload length mismatch")
    store = ResourceStore.from_exe(out_exe)
    try:
        expected = ResourceStore(open(payload_zip, "rb"), str(payload_zip))
        try:
            if store.names() != expected.names():
                raise SystemExit("verify: payload member list differs")
        finally:
            expected.close()
        if check_crc:
            bad = store.testzip()
            if bad is not None:
                raise SystemExit(f"verify: CRC error in {bad}")
    finally:
        store.close()


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 3:
        print(__doc__)
        return 2
    src, payload, out = (Path(a) for a in args)
    inject(src, payload, out)
    verify(out, payload, check_crc="--no-crc" not in argv)
    print(f"ok: {out} ({out.stat().st_size / 1048576:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
