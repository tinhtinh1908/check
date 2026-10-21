"""Read and parse device details (2 adb round-trips: ``getprop`` + one combined shell command)."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from bull_tool.core.adb.client import AdbClient
from bull_tool.core.profiles import PROFILES

SEPARATOR = "@@BULL@@"
STATS_CMD = (
    f"cat /proc/meminfo | head -3; echo {SEPARATOR}; df -k /data | tail -1; echo {SEPARATOR}; "
    f"dumpsys battery; echo {SEPARATOR}; wm size; wm density; echo {SEPARATOR}; "
    f"pm path com.google.android.gms; echo {SEPARATOR}; pm path com.android.vending"
)
RAM_SIZES_GB = (1, 2, 3, 4, 6, 8, 10, 12, 16, 18, 20, 24, 32)
BATTERY_STATUS = {"1": "Không rõ", "2": "Đang sạc", "3": "Đang dùng pin", "4": "Không sạc", "5": "Đầy"}
MARKETING_NAME_PROPS = (
    "ro.product.marketname",
    "ro.product.vendor.marketname",
    "ro.product.odm.marketname",
    "ro.config.marketing_name",
    "ro.vendor.oplus.market.name",
    "ro.oppo.market.name",
    "ro.vivo.market.name",
    "ro.product.vendor.model",
)
_PROP_LINE = re.compile(r"^\[(.+?)\]: \[(.*)\]$")


@dataclass
class DeviceInfo:
    serial: str
    brand: str = ""
    manufacturer: str = ""
    model: str = ""
    marketing_name: str = ""
    codename: str = ""
    android: str = ""
    sdk: str = ""
    rom: str = ""
    security_patch: str = ""
    build: str = ""
    chipset: str = ""
    abi: str = ""
    ram_gb: int | None = None
    storage_used_gb: float | None = None
    storage_total_gb: float | None = None
    battery_level: int | None = None
    battery_temp_c: float | None = None
    battery_status: str = ""
    screen: str = ""
    bootloader: str = ""
    gms: bool | None = None
    play_store: bool | None = None

    @property
    def display_name(self) -> str:
        return self.marketing_name or self.model or self.serial

    @property
    def storage_fraction(self) -> float | None:
        if self.storage_used_gb is None or not self.storage_total_gb:
            return None
        return min(1.0, self.storage_used_gb / self.storage_total_gb)

    def rows(self) -> list[tuple[str, str]]:
        """Ordered label/value pairs for the UI and the clipboard text."""

        def yes_no(value: bool | None) -> str:
            return "?" if value is None else ("Có" if value else "Không")

        storage = ""
        if self.storage_total_gb:
            storage = f"{self.storage_used_gb:.1f} / {self.storage_total_gb:.1f} GB".replace(".", ",")
        battery = ""
        if self.battery_level is not None:
            battery = f"{self.battery_level}%"
            if self.battery_temp_c is not None:
                battery += f" · {self.battery_temp_c:.1f}°C".replace(".", ",")
            if self.battery_status:
                battery += f" · {self.battery_status}"
        android = f"{self.android} (SDK {self.sdk})" if self.sdk else self.android
        return [
            ("Hãng", self.brand),
            ("Model", f"{self.model} · {self.codename}" if self.codename else self.model),
            ("Android", android),
            ("ROM", self.rom),
            ("Bản vá", self.security_patch),
            ("Chip", self.chipset),
            ("CPU ABI", self.abi),
            ("RAM", f"{self.ram_gb} GB" if self.ram_gb else ""),
            ("Bộ nhớ", storage),
            ("Pin", battery),
            ("Màn hình", self.screen),
            ("Bootloader", self.bootloader),
            ("Google Play", f"CH Play: {yes_no(self.play_store)} · GMS: {yes_no(self.gms)}"),
            ("Serial", self.serial),
        ]

    def as_text(self) -> str:
        lines = [self.display_name] + [f"{label}: {value}" for label, value in self.rows() if value]
        return "\n".join(lines)


def parse_getprop(text: str) -> dict[str, str]:
    props = {}
    for line in text.splitlines():
        match = _PROP_LINE.match(line.strip())
        if match:
            props[match.group(1)] = match.group(2)
    return props


def detect_rom(props: dict[str, str]) -> str:
    brand = props.get("ro.product.brand", "").lower()
    if version := props.get("ro.mi.os.version.incremental") or props.get("ro.mi.os.version.name"):
        return "HyperOS " + version.removeprefix("OS")
    if version := props.get("ro.miui.ui.version.name"):
        incremental = props.get("ro.build.version.incremental", "")
        return f"MIUI {version.lstrip('V')}" + (f" · {incremental}" if incremental else "")
    if version := props.get("ro.build.version.realmeui"):
        return f"realme UI {version.lstrip('V')}"
    if version := props.get("ro.build.version.oplusrom") or props.get("ro.build.version.opporom"):
        name = "OxygenOS" if brand == "oneplus" else "ColorOS"
        return f"{name} {version.lstrip('V')}"
    if version := props.get("ro.vivo.os.version"):
        return f"{props.get('ro.vivo.os.name', 'Funtouch OS')} {version}"
    if version := props.get("ro.build.version.magic"):
        return "MagicOS " + version.removeprefix("MagicUI_").removeprefix("MagicOS_")
    if version := props.get("hw_sc.build.platform.version"):
        return f"HarmonyOS {version}"
    if version := props.get("ro.build.version.emui"):
        return "EMUI " + version.removeprefix("EmotionUI_")
    return props.get("ro.build.display.id", "")


def detect_chipset(props: dict[str, str]) -> str:
    maker, model = props.get("ro.soc.manufacturer", ""), props.get("ro.soc.model", "")
    if model:
        return f"{maker} {model}".strip()
    return props.get("ro.hardware.chipname") or props.get("ro.board.platform") or props.get("ro.hardware", "")


def detect_bootloader(props: dict[str, str]) -> str:
    locked = props.get("ro.boot.flash.locked")
    state = props.get("ro.boot.verifiedbootstate", "")
    if locked == "1" or state == "green":
        return "Đã khóa"
    if locked == "0" or state in ("orange", "yellow"):
        return "Đã mở khóa"
    return ""


def parse_meminfo(text: str) -> int | None:
    match = re.search(r"MemTotal:\s+(\d+)\s*kB", text)
    if not match:
        return None
    gib = int(match.group(1)) / 1024 / 1024
    return next((size for size in RAM_SIZES_GB if size >= gib * 0.97), math.ceil(gib))


def parse_df(text: str) -> tuple[float | None, float | None]:
    """Return ``(used_gb, total_gb)`` from a ``df -k /data`` line."""
    for line in text.splitlines():
        cols = line.split()
        if len(cols) >= 4 and cols[1].isdigit() and cols[2].isdigit():
            total_kb, used_kb = int(cols[1]), int(cols[2])
            return used_kb * 1024 / 1e9, total_kb * 1024 / 1e9
    return None, None


def parse_battery(text: str) -> tuple[int | None, float | None, str]:
    values = {}
    for line in text.splitlines():
        if ":" in line:
            key, _sep, value = line.strip().partition(":")
            values[key.strip()] = value.strip()
    level = int(values["level"]) if values.get("level", "").isdigit() else None
    temp = values.get("temperature", "")
    temp_c = int(temp) / 10 if temp.lstrip("-").isdigit() else None
    return level, temp_c, BATTERY_STATUS.get(values.get("status", ""), "")


def parse_wm(text: str) -> str:
    def last(pattern: str) -> str:
        found = re.findall(pattern, text)
        return found[-1] if found else ""

    size = last(r"(?:Override|Physical) size: (\d+x\d+)")
    density = last(r"(?:Override|Physical) density: (\d+)")
    if size and density:
        return f"{size} · {density} dpi"
    return size


def build_info(serial: str, props: dict[str, str], stats: str) -> DeviceInfo:
    sections = (stats.split(SEPARATOR) + [""] * 6)[:6]
    meminfo, df, battery, wm, gms, vending = sections
    used, total = parse_df(df)
    level, temp, status = parse_battery(battery)
    marketing = next((props[k] for k in MARKETING_NAME_PROPS if props.get(k)), "")
    return DeviceInfo(
        serial=serial,
        brand=props.get("ro.product.brand", ""),
        manufacturer=props.get("ro.product.manufacturer", ""),
        model=props.get("ro.product.model", ""),
        marketing_name=marketing,
        codename=props.get("ro.product.device", ""),
        android=props.get("ro.build.version.release", ""),
        sdk=props.get("ro.build.version.sdk", ""),
        rom=detect_rom(props),
        security_patch=props.get("ro.build.version.security_patch", ""),
        build=props.get("ro.build.display.id", ""),
        chipset=detect_chipset(props),
        abi=props.get("ro.product.cpu.abi", ""),
        ram_gb=parse_meminfo(meminfo),
        storage_used_gb=used,
        storage_total_gb=total,
        battery_level=level,
        battery_temp_c=temp,
        battery_status=status,
        screen=parse_wm(wm),
        bootloader=detect_bootloader(props),
        gms="package:" in gms,
        play_store="package:" in vending,
    )


def collect_device_info(client: AdbClient, serial: str, features: frozenset[str] | None = None) -> DeviceInfo:
    feats = features if features is not None else client.features(serial)
    props = parse_getprop(client.shell(serial, "getprop", features=feats).stdout)
    stats = client.shell(serial, STATS_CMD, features=feats).stdout
    return build_info(serial, props, stats)


def match_profile(brand: str, manufacturer: str = "") -> str | None:
    """Return the profile id whose brand list contains the device brand or manufacturer."""
    names = {brand.strip().lower(), manufacturer.strip().lower()} - {""}
    for profile in PROFILES:
        if names & set(profile.brands):
            return profile.id
    return None
