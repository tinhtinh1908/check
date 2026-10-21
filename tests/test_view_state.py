from bull_tool.core.adb.client import DeviceEntry
from bull_tool.core.device_info import DeviceInfo
from bull_tool.ui.theme import compute_layout
from bull_tool.ui.view_state import (
    FIX_JOB,
    PROFILE_JOB,
    ViewState,
    auto_profile,
    brand_warning,
    choose_serial,
    info_read_target,
    next_preferred,
    start_block_reason,
    suggest_profile,
    target_warning,
)

READY = DeviceEntry("A1", "device", model="M1")
UNAUTH = DeviceEntry("B2", "unauthorized")
OTHER_READY = DeviceEntry("C3", "device", model="M3")
XIAOMI = DeviceInfo(serial="A1", brand="Redmi", manufacturer="Xiaomi", marketing_name="Redmi Note 13")
OPPO = DeviceInfo(serial="C3", brand="OPPO", manufacturer="OPPO", model="CPH2581")


def ready_state(**overrides) -> ViewState:
    state = ViewState(bootstrap_ready=True, devices=(READY,), selected_serial="A1", selected_profile="xiaomi")
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def two_phones(**overrides) -> ViewState:
    """The user's phone A1 is selected while a second phone, C3, is plugged in too."""
    return ready_state(**{"devices": (READY, OTHER_READY), "preferred_serial": "A1", **overrides})


def test_choose_serial_prefers_job_then_current_then_first_ready():
    assert choose_serial((), None, None) is None
    assert choose_serial((UNAUTH, READY), None, None) == "A1"
    assert choose_serial((UNAUTH, READY), "B2", None) == "B2"
    assert choose_serial((UNAUTH, READY, OTHER_READY), "B2", "C3") == "C3"
    assert choose_serial((UNAUTH,), "gone", None) == "B2"


def test_choose_serial_restores_the_users_phone():
    assert choose_serial((OTHER_READY,), "A1", None, "A1") == "C3"  # the user's phone is gone: fall back
    assert choose_serial((OTHER_READY, READY), "C3", None, "A1") == "A1"  # it is back: restore it
    assert choose_serial((OTHER_READY, READY), None, None, "A1") == "A1"  # adb reconnect: () and then the list
    reconnecting = DeviceEntry("A1", "offline")
    assert choose_serial((OTHER_READY, reconnecting), "C3", None, "A1") == "A1"  # back but not ready yet
    assert choose_serial((OTHER_READY, READY), "C3", "C3", "A1") == "C3"  # a running job keeps its phone


def test_next_preferred_adopts_only_a_phone_that_appears_on_an_empty_panel():
    assert next_preferred(None, "A1", None) == "A1"  # the first phone of the session
    assert next_preferred(None, "C3", "A1") == "C3"  # one phone at a time: the next phone is the user's
    assert next_preferred("A1", "C3", "A1") == "A1"  # an automatic fallback keeps the user's phone
    assert next_preferred("A1", None, "A1") == "A1"  # so does unplugging every phone
    assert next_preferred(None, None, "A1") == "A1"


def test_phones_coming_back_after_an_adb_restart_do_not_replace_the_users_phone():
    seen = frozenset({"A1", "C3"})  # both were plugged in before the list emptied (adb restart, hub glitch)
    assert next_preferred(None, "C3", "A1", seen) == "A1"  # C3 is back first: still not the user's phone
    assert next_preferred(None, "D4", "A1", seen) == "D4"  # a phone that was not there before: a new phone
    assert next_preferred(None, "C3", None, seen) == "C3"  # nobody chosen yet: the first phone back


def test_target_warning_names_a_swapped_in_phone():
    swapped = two_phones(devices=(OTHER_READY,), selected_serial="C3")
    message = target_warning(swapped)
    assert "(A1) không còn kết nối" in message and "máy M3 (C3)" in message  # details not read yet: adb model
    swapped.infos = {"C3": OPPO}
    assert "máy CPH2581 (C3)" in target_warning(swapped)
    assert target_warning(two_phones()) == ""  # the user's own phone
    assert target_warning(ready_state()) == ""  # no phone chosen yet


def test_a_manual_pick_belongs_to_the_phone_it_was_made_for():
    state = two_phones(infos={"A1": XIAOMI, "C3": OPPO}, selected_profile="sony", manual_pick=("A1", "M1", "sony"))
    assert auto_profile(state) is None  # same phone, also after unplugging and plugging it back
    state.selected_serial = "C3"
    assert auto_profile(state) == "oppo"  # another phone gets its brand suggestion
    state.selected_serial, state.selected_profile = "A1", "oppo"
    assert auto_profile(state) == "sony"  # back on the first phone: its pick returns
    state.job = PROFILE_JOB
    assert auto_profile(state) is None  # never while a job runs
    state.job = FIX_JOB
    assert auto_profile(state) is None


def test_clicking_the_suggested_card_does_not_stop_suggestions_for_the_next_phone():
    state = two_phones(infos={"A1": XIAOMI, "C3": OPPO}, manual_pick=("A1", "M1", "xiaomi"))
    assert auto_profile(state) is None
    state.selected_serial = "C3"
    assert auto_profile(state) == "oppo"


def test_a_phone_of_unknown_brand_keeps_the_manual_pick():
    samsung = DeviceInfo(serial="C3", brand="samsung", manufacturer="samsung", model="SM-A556")
    state = two_phones(selected_serial="C3", infos={"C3": samsung}, selected_profile="sony")
    state.manual_pick = ("C3", "M3", "sony")
    assert auto_profile(state) is None
    state.manual_pick = ("A1", "M1", "sony")  # picked for another phone: there is no suggestion to replace it either
    assert auto_profile(state) is None


def test_info_reads_run_one_at_a_time():
    assert info_read_target(two_phones(), None) == "A1"
    assert info_read_target(two_phones(reading_serial="C3"), None) is None  # wait for the read in flight
    assert info_read_target(two_phones(infos={"A1": XIAOMI}), None) is None  # details already known
    assert info_read_target(two_phones(), "A1") is None  # its last read failed: wait for a refresh
    assert info_read_target(two_phones(), "C3") == "A1"  # another phone's failure does not hold it back
    assert info_read_target(ready_state(devices=(UNAUTH,), selected_serial="B2"), None) is None
    assert info_read_target(two_phones(bootstrap_ready=False), None) is None
    assert info_read_target(ready_state(devices=(), selected_serial=None), None) is None


def test_start_block_reasons():
    assert start_block_reason(ready_state()) == ""
    assert "khởi động" in start_block_reason(ready_state(bootstrap_ready=False))
    assert "khác" in start_block_reason(ready_state(job=FIX_JOB))
    assert "Chưa có" in start_block_reason(ready_state(devices=(), selected_serial=None))
    assert "chưa sẵn sàng" in start_block_reason(ready_state(devices=(UNAUTH,), selected_serial="B2"))
    assert "Chọn dòng máy" in start_block_reason(ready_state(selected_profile=None))
    assert start_block_reason(ready_state(job=PROFILE_JOB)) == ""  # acts as the Stop button


def test_start_waits_for_the_selected_phones_details():
    state = two_phones(reading_serial="A1")
    assert "Đang đọc" in start_block_reason(state)
    state.reading_serial = "C3"  # another phone's read runs first
    assert "Đang đọc" in start_block_reason(state)
    state.selected_profile = None  # the brand suggestion picks the profile once the details arrive
    assert "Đang đọc" in start_block_reason(state)
    state.selected_profile, state.reading_serial = "xiaomi", None  # a failed read falls back to the brand confirm
    assert start_block_reason(state) == ""
    state.infos, state.reading_serial = {"A1": XIAOMI}, "C3"
    assert start_block_reason(state) == ""


def test_brand_warning_cases():
    samsung = DeviceInfo(serial="A1", brand="samsung", manufacturer="samsung", model="SM-A556")
    assert brand_warning(ready_state(infos={"A1": XIAOMI})) == ""
    assert "OPPO" in brand_warning(ready_state(infos={"A1": XIAOMI}, selected_profile="oppo"))
    assert "không nhận ra" in brand_warning(ready_state(infos={"A1": samsung}))
    assert "Chưa đọc được" in brand_warning(ready_state())
    assert suggest_profile(XIAOMI) == "xiaomi" and suggest_profile(None) is None


def test_brand_warning_names_the_phone_whose_details_are_missing():
    assert "máy M1." in brand_warning(ready_state())
    underscored = DeviceEntry("A1", "device", model="Redmi_Note_13")
    assert "máy Redmi Note 13." in brand_warning(ready_state(devices=(underscored,)))
    assert "máy A1." in brand_warning(ready_state(devices=(DeviceEntry("A1", "device"),)))


def test_layout_breakpoints():
    assert compute_layout(1920, 1040).density == "full"
    assert compute_layout(1280, 800).density == "full"
    assert compute_layout(1280, 720).density == "compact"
    assert compute_layout(1024, 640).density == "chip"
    small = compute_layout(880, 540)
    assert small.density == "chip" and small.short and small.sidebar == 260
    assert compute_layout(1700, 1000).sidebar == 340


def test_a_manual_pick_does_not_follow_the_serial_onto_another_model():
    # cheap or re-flashed phones can all report the same serial: the adb model tells them apart
    state = ready_state(infos={"A1": OPPO}, selected_profile="xiaomi", manual_pick=("A1", "M9", "xiaomi"))
    assert auto_profile(state) == "oppo"  # another model under the same serial gets its own suggestion
    state.manual_pick = ("A1", "M1", "sony")
    assert auto_profile(state) == "sony"  # the same phone keeps the pick
    unauthorized = DeviceEntry("A1", "unauthorized")  # no model yet: the serial alone decides
    state.devices, state.manual_pick, state.selected_profile = (unauthorized,), ("A1", "M1", "sony"), "oppo"
    assert auto_profile(state) == "sony"
