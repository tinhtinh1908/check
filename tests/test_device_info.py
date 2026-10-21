import pytest

from bull_tool.core.device_info import (
    SEPARATOR,
    build_info,
    detect_rom,
    match_profile,
    parse_battery,
    parse_df,
    parse_getprop,
    parse_meminfo,
    parse_wm,
)

XIAOMI_PROPS = """
[ro.product.brand]: [Redmi]
[ro.product.manufacturer]: [Xiaomi]
[ro.product.model]: [23129RAA4G]
[ro.product.marketname]: [Redmi Note 13 5G]
[ro.product.device]: [gold]
[ro.build.version.release]: [14]
[ro.build.version.sdk]: [34]
[ro.mi.os.version.name]: [OS1.0]
[ro.mi.os.version.incremental]: [OS1.0.6.0.UNQMIXM]
[ro.build.version.security_patch]: [2024-05-01]
[ro.soc.manufacturer]: [Mediatek]
[ro.soc.model]: [MT6833]
[ro.product.cpu.abi]: [arm64-v8a]
[ro.boot.flash.locked]: [1]
[ro.build.description]: [multi word value: with colon]
"""

STATS = SEPARATOR.join(
    [
        "MemTotal:        7654321 kB\nMemFree:  100 kB\n",
        "/dev/block/dm-48 115340288 45000000 70340288  39% /data\n",
        "Current Battery Service state:\n  AC powered: false\n  status: 2\n  level: 87\n  temperature: 312\n",
        "Physical size: 1080x2400\nOverride size: 1080x2340\nPhysical density: 440\n",
        "package:/data/app/com.google.android.gms/base.apk\n",
        "",
    ]
)


def test_parse_getprop_and_build_info():
    props = parse_getprop(XIAOMI_PROPS)
    assert props["ro.build.description"] == "multi word value: with colon"
    info = build_info("SER1", props, STATS)
    assert info.display_name == "Redmi Note 13 5G"
    assert info.rom == "HyperOS 1.0.6.0.UNQMIXM"
    assert info.chipset == "Mediatek MT6833"
    assert info.bootloader == "Đã khóa"
    assert info.ram_gb == 8
    assert info.battery_level == 87 and info.battery_temp_c == pytest.approx(31.2)
    assert info.battery_status == "Đang sạc"
    assert info.screen == "1080x2340 · 440 dpi"
    assert info.gms is True and info.play_store is False
    assert info.storage_fraction == pytest.approx(45000000 / 115340288)
    text = info.as_text()
    assert text.startswith("Redmi Note 13 5G") and "Android: 14 (SDK 34)" in text


@pytest.mark.parametrize(
    "props,expected",
    [
        ({"ro.miui.ui.version.name": "V14", "ro.build.version.incremental": "V14.0.4.0"}, "MIUI 14 · V14.0.4.0"),
        ({"ro.product.brand": "OPPO", "ro.build.version.oplusrom": "V14.0.0"}, "ColorOS 14.0.0"),
        ({"ro.product.brand": "OnePlus", "ro.build.version.oplusrom": "V14.0.0"}, "OxygenOS 14.0.0"),
        ({"ro.build.version.realmeui": "V5.0", "ro.build.version.oplusrom": "V14"}, "realme UI 5.0"),
        ({"ro.vivo.os.name": "OriginOS", "ro.vivo.os.version": "4.0"}, "OriginOS 4.0"),
        ({"ro.build.version.magic": "MagicOS_8.0.0"}, "MagicOS 8.0.0"),
        ({"hw_sc.build.platform.version": "4.2.0"}, "HarmonyOS 4.2.0"),
        ({"ro.build.version.emui": "EmotionUI_12.0.0"}, "EMUI 12.0.0"),
        ({"ro.build.display.id": "67.2.A.2.112"}, "67.2.A.2.112"),
    ],
)
def test_detect_rom(props, expected):
    assert detect_rom(props) == expected


@pytest.mark.parametrize(
    "kb,expected", [(7654321, 8), (11534336, 12), (3800000, 4), (5800000, 6), (15900000, 16), (1900000, 2)]
)
def test_parse_meminfo_rounds_to_marketing_size(kb, expected):
    assert parse_meminfo(f"MemTotal:       {kb} kB") == expected


def test_parsers_tolerate_garbage():
    assert parse_meminfo("nothing") is None
    assert parse_df("df: /data: Permission denied") == (None, None)
    assert parse_battery("") == (None, None, "")
    assert parse_wm("") == ""


def test_parse_df_values():
    df = "Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/x 1000000 250000 750000 25% /data"
    used, total = parse_df(df)
    assert used == pytest.approx(0.256) and total == pytest.approx(1.024)


@pytest.mark.parametrize(
    "brand,manufacturer,expected",
    [
        ("Redmi", "Xiaomi", "xiaomi"),
        ("POCO", "Xiaomi", "xiaomi"),
        ("realme", "realme", "oppo"),
        ("OnePlus", "OnePlus", "oppo"),
        ("OPPO", "OPPO", "oppo"),
        ("iQOO", "vivo", "vivo"),
        ("HUAWEI", "HUAWEI", "honor"),
        ("HONOR", "HONOR", "honor"),
        ("Sony", "Sony", "sony"),
        ("samsung", "samsung", None),
    ],
)
def test_match_profile(brand, manufacturer, expected):
    assert match_profile(brand, manufacturer) == expected
