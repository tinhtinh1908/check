"""Download the bundled UI fonts from pinned upstream revisions and record their SHA-256.

Run once (needs internet); the files are then committed with the app assets:
    python scripts/fetch_fonts.py
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

FONTS_DIR = Path(__file__).resolve().parents[1] / "bull_tool" / "assets" / "fonts"

BVP_BASE = "https://raw.githubusercontent.com/google/fonts/c13390277dfb1fcc7415d84ef7ef9cfc1e52f8c1/ofl/bevietnampro"
JBM_BASE = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/v2.304"

# (local file name, pinned URL)
SOURCES: list[tuple[str, str]] = [
    ("BeVietnamPro-Regular.ttf", f"{BVP_BASE}/BeVietnamPro-Regular.ttf"),
    ("BeVietnamPro-Medium.ttf", f"{BVP_BASE}/BeVietnamPro-Medium.ttf"),
    ("BeVietnamPro-SemiBold.ttf", f"{BVP_BASE}/BeVietnamPro-SemiBold.ttf"),
    ("BeVietnamPro-Bold.ttf", f"{BVP_BASE}/BeVietnamPro-Bold.ttf"),
    ("BeVietnamPro-ExtraBold.ttf", f"{BVP_BASE}/BeVietnamPro-ExtraBold.ttf"),
    ("OFL-BeVietnamPro.txt", f"{BVP_BASE}/OFL.txt"),
    ("JetBrainsMono-Regular.ttf", f"{JBM_BASE}/fonts/ttf/JetBrainsMono-Regular.ttf"),
    ("JetBrainsMono-SemiBold.ttf", f"{JBM_BASE}/fonts/ttf/JetBrainsMono-SemiBold.ttf"),
    ("OFL-JetBrainsMono.txt", f"{JBM_BASE}/OFL.txt"),
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recorded_hashes() -> dict[str, str]:
    """SHA-256 values recorded by a previous run (the committed SOURCES.txt pins the font files)."""
    record = FONTS_DIR / "SOURCES.txt"
    if not record.exists():
        return {}
    hashes = {}
    for line in record.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and not line.startswith("#"):
            hashes[parts[0]] = parts[1]
    return hashes


def main() -> int:
    FONTS_DIR.mkdir(parents=True, exist_ok=True)
    pinned = recorded_hashes()
    lines = []
    for name, url in SOURCES:
        target = FONTS_DIR / name
        if not target.exists():
            print(f"download {name}")
            with urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 - pinned https URL
                data = resp.read()
            if name.endswith(".ttf") and data[:4] not in (b"\x00\x01\x00\x00", b"true", b"OTTO"):
                print(f"error: {name} is not a font file", file=sys.stderr)
                return 1
            target.write_bytes(data)
        digest = sha256_of(target)
        if name in pinned and pinned[name] != digest:
            print(f"error: {name} does not match its recorded SHA-256 (got {digest})", file=sys.stderr)
            return 1
        lines.append(f"{name}\t{digest}\t{url}")
    (FONTS_DIR / "SOURCES.txt").write_text(
        "# file\tsha256\tsource (SIL Open Font License 1.1)\n" + "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(f"ok: {len(SOURCES)} files in {FONTS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
