"""``flet pack`` that names the exe correctly in its Windows version resource (used by build_exe.py).

flet pack copies the Flet client's VERSIONINFO into the PyInstaller exe and overrides only product name,
description, versions, company and copyright, so Explorer's Details tab would still show InternalName "Flet"
and OriginalFilename "flet.exe". This wrapper rewrites those two fields of the version file PyInstaller
receives, using the ``--name`` passed to flet pack; the Flet client keeps its own names.

    python scripts/flet_pack.py pack main.py --name BULL-TOOL ...   (same arguments as ``flet pack``)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import flet_cli.__pyinstaller.win_utils as win_utils


def with_file_names(update_version_info, exe_name: str):
    def update(**kwargs) -> str:
        path = update_version_info(**kwargs)
        text = Path(path).read_text(encoding="utf-8")
        text = re.sub(r"StringStruct\('InternalName', '[^']*'\)", f"StringStruct('InternalName', '{exe_name}')", text)
        text = re.sub(r"StringStruct\('OriginalFilename', '[^']*'\)",
                      f"StringStruct('OriginalFilename', '{exe_name}.exe')", text)
        Path(path).write_text(text, encoding="utf-8")
        return path

    return update


def main() -> None:
    exe_name = sys.argv[sys.argv.index("--name") + 1]
    win_utils.update_flet_view_version_info = with_file_names(win_utils.update_flet_view_version_info, exe_name)
    sys.argv = ["flet", *sys.argv[1:]]
    from flet.cli import main as flet_main

    flet_main()


if __name__ == "__main__":
    main()
