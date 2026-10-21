import dataclasses
import warnings

import flet as ft
import pytest
from flet.utils.validation import validate

from bull_tool import app_info
from bull_tool.core.adb.client import DeviceEntry
from bull_tool.core.device_info import DeviceInfo
from bull_tool.ui import theme as T
from bull_tool.ui.contact_card import ContactCards
from bull_tool.ui.device_panel import DevicePanel
from bull_tool.ui.status_bar import StatusBar
from tests.flet_harness import mount_page

SAMPLE_INFO = DeviceInfo(
    serial="R58N1234ABC", brand="Redmi", manufacturer="Xiaomi", model="23090RA98G", marketing_name="Redmi Note 13",
    codename="sapphire", android="14", sdk="34", rom="HyperOS 1.0.5.0", chipset="MT6789", ram_gb=8,
    storage_used_gb=41.3, storage_total_gb=128.0, battery_level=87, battery_temp_c=31.5, battery_status="Đang sạc",
    screen="1080x2400", gms=True, play_store=True,
)


def noop(*_args) -> None:
    return None


def new_panel() -> DevicePanel:
    return DevicePanel(noop, noop, noop, noop, noop)


def walk(control: ft.BaseControl):
    """The control and every control below it, following control-valued properties."""
    yield control
    for field in dataclasses.fields(control):
        if field.name.startswith("_"):
            continue
        value = getattr(control, field.name)
        for child in value if isinstance(value, (list, tuple)) else (value,):
            if isinstance(child, ft.BaseControl):
                yield from walk(child)


def of_type(root: ft.BaseControl, cls: type) -> list:
    return [c for c in walk(root) if isinstance(c, cls)]


def texts(root: ft.BaseControl) -> list[str]:
    return [t.value for t in of_type(root, ft.Text)]


def link_buttons(cards: ContactCards) -> list[tuple[ft.Container, ft.Text]]:
    """The shop card's link buttons (its only containers with a tooltip) with their labels."""
    links = []
    for button in [c for c in walk(cards.controls[0]) if isinstance(c, ft.Container) and c.tooltip]:
        [label] = of_type(button, ft.Text)
        links.append((button, label))
    return links


def test_device_selector_border_uses_no_deprecated_props():
    [selector] = of_type(new_panel().root, ft.Dropdown)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        validate(selector)
    # same look as before: 1 px outline, and a neutral 2 px one when focused instead of the theme primary
    assert {state: (border.side.width, border.side.color) for state, border in selector.border.items()} == {
        ft.ControlState.DEFAULT: (1, T.BORDER),
        ft.ControlState.FOCUSED: (2, T.BORDER),
    }


def test_contact_links_show_icons_only_on_the_narrow_sidebar_and_name_the_link_in_the_tooltip():
    cards = ContactCards(noop)
    links = link_buttons(cards)
    assert [label.value for _button, label in links] == ["Website", "Facebook", "Zalo"]

    cards.apply_layout(T.compute_layout(880, 540))
    assert [label.visible for _button, label in links] == [False, False, False]
    for button, label in links:
        assert button.tooltip.startswith(f"{label.value} · https://")
        assert button.expand and button.content.horizontal_alignment == ft.CrossAxisAlignment.CENTER

    cards.apply_layout(T.compute_layout(1280, 800))
    assert [label.visible for _button, label in links] == [True, True, True]
    assert all(button.tooltip.startswith(f"{label.value} · ") for button, label in links)


@pytest.mark.parametrize(("width", "labels_visible"), [(1023, False), (1024, True)])
def test_contact_link_labels_come_back_from_the_288px_sidebar(width, labels_visible):
    cards = ContactCards(noop)
    cards.apply_layout(T.compute_layout(width, 768))
    assert [label.visible for _button, label in link_buttons(cards)] == [labels_visible] * 3


def test_no_device_action_labels_ellipsize_instead_of_overflowing():
    panel = new_panel()
    panel.show_no_device()
    labels = [t for t in of_type(panel.root, ft.Text) if t.value in ("Hướng dẫn", "Sửa kết nối")]
    assert len(labels) == 2
    assert all(t.expand and t.expand_loose and t.max_lines == 1 for t in labels)


def test_only_the_version_label_flexes_in_the_status_bar():
    labels = {t.value: t for t in of_type(StatusBar(noop).root, ft.Text)}
    assert labels[f"{app_info.APP_NAME} v{app_info.VERSION}"].expand
    # an even flex split would cut the longer ADB "mất kết nối, đang thử lại" text
    assert not labels["ADB: đang khởi động"].expand and not labels["Driver USB: đang kiểm tra"].expand


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_every_device_panel_view_mounts_and_updates_headless():
    page, _session, conn = mount_page()
    panel = new_panel()
    page.add(panel.root)
    unauthorized = DeviceEntry("R58N1234ABC", "unauthorized")
    connected = DeviceEntry("R58N1234ABC", "device", model="Redmi_Note_13")
    steps = [
        ("starting", panel.show_starting, "Đang khởi động ADB…"),
        ("no_device", panel.show_no_device, "Chưa có thiết bị"),
        ("adb_down", lambda: panel.show_adb_down(""), "Mất kết nối tới ADB server."),
        ("adb_down", lambda: panel.show_adb_down("adb server did not start"), "adb server did not start"),
        ("adb_down", lambda: panel.show_adb_down("x" * 200), "x" * 160 + "…"),
        ("unauthorized", lambda: panel.show_unauthorized(unauthorized), "Chờ cho phép gỡ lỗi USB"),
        ("reading", lambda: panel.show_reading(connected), "Đang đọc thông tin Redmi Note 13…"),
        ("ready", lambda: panel.show_info(SAMPLE_INFO), "Redmi Note 13"),
    ]
    for state, show, expected in steps:
        sent = len(conn.sent)
        for control in show():
            control.update()
        assert panel.state == state and len(conn.sent) > sent  # the new view went out as a patch
        assert expected in texts(panel.root)
        if state == "starting":  # status line above the placeholder bars, like the reading view
            assert of_type(panel.root, ft.ProgressRing) and of_type(panel.root, ft.Shimmer)
        if state == "adb_down":  # the automatic retry is announced on its own line, whatever the detail
            assert "Tool đang tự thử lại…" in texts(panel.root)

    for control in panel.set_devices((connected, unauthorized), connected.serial, locked=False):
        control.update()
    [selector] = of_type(panel.root, ft.Dropdown)
    assert selector.visible and selector.value == connected.serial
    # short labels: the field clips long text at the 260 px sidebar; the card shows the full serial and state
    assert [option.text for option in selector.options] == ["Redmi Note 13 · …4ABC", "⚠ R58N1234ABC"]


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_status_bar_and_contact_cards_mount_and_update_headless():
    page, _session, conn = mount_page()
    bar, cards = StatusBar(noop), ContactCards(noop)
    page.add(bar.root, *cards.controls)
    for control in [*bar.set_adb(False, "36.0.2"), *bar.set_driver(True)]:
        control.update()
    assert "ADB 36.0.2: mất kết nối, đang thử lại" in texts(bar.root)

    cards.apply_layout(T.compute_layout(880, 540))
    cards.controls[0].update()
    assert sum(op[-2:] == ["visible", False] for op in conn.last_patch_ops()) == 3  # one per link label
