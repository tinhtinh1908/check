"""Keeps bull_tool.core.profiles in lock-step with the original @ANDROID.bat menu items 1-6."""

import re
import zipfile
from pathlib import Path

import pytest

from bull_tool.core.profiles import (
    GUIDES,
    PROFILE_BY_ID,
    PROFILES,
    Disable,
    Install,
    InstallMulti,
    Push,
    Uninstall,
    referenced_apks,
    to_batch_line,
)

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "@ANDROID.bat"
LABELS = {"xiaomi": "cmd1", "oppo": "cmd2", "honor": "cmd3", "vivo": "cmd4", "sony": "cmd5"}


def normalize(line: str) -> str:
    line = re.sub(r"\s+", " ", line.strip()).replace('"', "")
    push = re.match(r"(adb push \S+) (\S+)$", line)
    if push:  # /sdcard/download and /sdcard/Download/ are the same folder on emulated storage
        line = f"{push.group(1)} {push.group(2).lower().rstrip('/')}"
    return line


def batch_sections() -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for raw in BAT.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        label = re.match(r"^:(\w+)$", stripped)
        if label:
            current = label.group(1)
            sections[current] = []
        elif current and stripped.lower().startswith("adb "):
            sections[current].append(normalize(stripped))
    return sections


def dedupe(lines: list[str]) -> list[str]:
    seen: set[str] = set()
    return [x for x in lines if not (x in seen or seen.add(x))]


@pytest.mark.parametrize("profile", PROFILES, ids=lambda p: p.id)
def test_profile_commands_match_batch(profile):
    expected = dedupe(batch_sections()[LABELS[profile.id]])
    actual = [normalize(to_batch_line(step)) for step in profile.steps]
    assert actual == expected


def test_step_counts_after_dropping_duplicates():
    counts = {
        p.id: (p.count(Uninstall), p.count(Disable), p.count(Install), p.count(InstallMulti), p.count(Push))
        for p in PROFILES
    }
    assert counts == {
        "xiaomi": (86, 5, 2, 0, 10),
        "oppo": (79, 16, 6, 2, 0),
        "honor": (101, 37, 6, 2, 0),
        "vivo": (53, 1, 6, 2, 0),
        "sony": (82, 1, 1, 0, 0),
    }


def test_referenced_apks_exist_in_repo():
    assert sorted(a for a in referenced_apks() if not (ROOT / a).is_file()) == []


def test_referenced_apks_exist_in_dev_payload():
    payload = ROOT / ".build" / "payload.zip"
    if not payload.exists():
        pytest.skip("dev payload not built")
    with zipfile.ZipFile(payload) as zf:
        assert referenced_apks() <= set(zf.namelist())


def test_guides_cover_batch_brands():
    assert [name for name, _steps in GUIDES] == [
        "Xiaomi / Redmi", "OPPO / Realme / OnePlus", "Honor / Huawei", "vivo / iQOO",
    ]
    assert all(len(steps) >= 7 for _name, steps in GUIDES)


def test_profile_summary_text():
    assert PROFILE_BY_ID["xiaomi"].summary == "Gỡ 86 · Tắt 5 · Cài 2 · Chép 10"
    assert PROFILE_BY_ID["sony"].summary == "Gỡ 82 · Tắt 1 · Cài 1"
    assert PROFILE_BY_ID["xiaomi"].short_summary == "Gỡ 86 · Tắt 5 · 12 APK"
    assert PROFILE_BY_ID["oppo"].short_summary == "Gỡ 79 · Tắt 16 · 8 APK"
