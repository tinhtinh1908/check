"""Generate the exe/window icon and resized logos from the original brand images.

The original files in the repo root stay untouched; outputs go to ``bull_tool/assets``.
Idempotent: a target is rebuilt only when it is missing or older than its source.
    python scripts/build_assets.py [--force]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "bull_tool" / "assets"
BULL_LOGO = ROOT / "BULL_logo.jpg"
MTFLASH_LOGO = ROOT / "MTFLASH_logo.png"
ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
SCRIPT = Path(__file__)


def _stale(target: Path, *sources: Path) -> bool:
    if not target.exists():
        return True
    built = target.stat().st_mtime
    return any(src.stat().st_mtime > built for src in sources)


def _square_rgba(path: Path) -> Image.Image:
    """Load an image as RGBA on a square canvas (white fill for opaque logos, transparent otherwise)."""
    with Image.open(path) as src:
        img = src.convert("RGBA")
    side = max(img.size)
    fill = (255, 255, 255, 255) if path.suffix.lower() in (".jpg", ".jpeg") else (0, 0, 0, 0)
    canvas = Image.new("RGBA", (side, side), fill)
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return canvas


def _resized(img: Image.Image, size: int) -> Image.Image:
    out = img.resize((size, size), Image.Resampling.LANCZOS)
    if size <= 32:
        # Small icon sizes lose detail after downscaling; a light unsharp mask keeps edges crisp.
        out = out.filter(ImageFilter.UnsharpMask(radius=0.6, percent=60, threshold=1))
    return out


def build_icon(force: bool) -> bool:
    target = ASSETS / "icon.ico"
    if not force and not _stale(target, BULL_LOGO, SCRIPT):
        return False
    logo = _square_rgba(BULL_LOGO)
    frames = [_resized(logo, s) for s in ICON_SIZES]
    largest = frames[-1]
    largest.save(target, format="ICO", sizes=[(s, s) for s in ICON_SIZES], append_images=frames[:-1])
    return True


def build_png(source: Path, target: Path, size: int, force: bool) -> bool:
    if not force and not _stale(target, source, SCRIPT):
        return False
    _resized(_square_rgba(source), size).save(target, format="PNG", optimize=True)
    return True


def main(argv: list[str]) -> int:
    force = "--force" in argv
    ASSETS.mkdir(parents=True, exist_ok=True)
    built = {
        "icon.ico": build_icon(force),
        "bull_logo_256.png": build_png(BULL_LOGO, ASSETS / "bull_logo_256.png", 256, force),
        "bull_logo_64.png": build_png(BULL_LOGO, ASSETS / "bull_logo_64.png", 64, force),
        "mtflash_256.png": build_png(MTFLASH_LOGO, ASSETS / "mtflash_256.png", 256, force),
    }
    for name, changed in built.items():
        print(f"{'built ' if changed else 'fresh '} {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
