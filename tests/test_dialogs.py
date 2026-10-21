import asyncio

import flet as ft
import msgpack
import pytest

from bull_tool.core.job_runner import Failure, Summary
from bull_tool.ui import dialogs
from tests.flet_harness import click, client_dismissed, mount_page


def summary_with_failures() -> Summary:
    return Summary(
        "xiaomi", "Xiaomi / Redmi", "R58N1234ABC", removed=14, disabled=3, installed=2, elapsed_s=95.0,
        failures=[Failure("Mi Analytics", "DELETE_FAILED_INTERNAL_ERROR", "Tắt thủ công trong Cài đặt"),
                  Failure("Facebook App Manager", "không tìm thấy gói")],
    )


def last_patch_target(conn) -> int:
    """Id of the control the most recent patch message was sent for."""
    return msgpack.unpackb(conn.sent[-1], strict_map_key=False)[1]["id"]


def test_confirm_closes_its_own_dialog_when_a_toast_sits_on_top():
    async def scenario():
        page, session, conn = mount_page()
        confirmed = []
        confirm = dialogs.show_confirm(page, "Sửa lỗi kết nối", "msg", "Sửa ngay", lambda: confirmed.append(1))
        toast = dialogs.toast(page, "Không ghi được file log phiên (console vẫn hoạt động)")
        await click(session, confirm.actions[1])
        assert (confirm.open, toast.open, confirmed) == (False, True, [1])
        assert last_patch_target(conn) == confirm._i and [0, 0, "open", False] in conn.last_patch_ops()
        await client_dismissed(session, confirm)
        assert page._dialogs.controls == [toast]  # no leaked entry; the toast times out on its own

    asyncio.run(scenario())


def test_a_click_that_raced_the_close_neither_confirms_twice_nor_closes_another_dialog():
    async def scenario():
        page, session, _conn = mount_page()
        confirmed = []

        async def fix() -> None:
            confirmed.append("fix")
            await asyncio.sleep(0)  # the second click is handled while this action is still running

        below = dialogs.show_confirm(page, "Cài driver", "msg", "Cài driver", lambda: confirmed.append("driver"))
        top = dialogs.show_confirm(page, "Sửa lỗi kết nối", "msg", "Sửa ngay", fix)
        await asyncio.gather(click(session, top.actions[1]), click(session, top.actions[1]))
        assert confirmed == ["fix"] and below.open and not top.open

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("show", "label"),
    [
        pytest.param(lambda page: dialogs.show_summary(page, summary_with_failures()), "Đóng", id="summary"),
        pytest.param(lambda page: dialogs.show_guide(page, 1), "Đã hiểu", id="guide"),
        pytest.param(lambda page: dialogs.show_message(page, "Không khởi động được tool", "Cổng 5037 đang bận"),
                     "Đóng", id="message"),
    ],
)
def test_single_button_dialogs_close_themselves_and_leave_the_toast_above_open(show, label):
    async def scenario():
        page, session, _conn = mount_page()
        dialog = show(page)
        toast = dialogs.toast(page, "Đã sửa xong — rút ra cắm lại cáp nếu máy vẫn chưa hiện")
        [button] = dialog.actions
        assert button.content.value == label
        await click(session, button)
        assert (dialog.open, toast.open) == (False, True)
        await client_dismissed(session, dialog)
        assert page._dialogs.controls == [toast]

    asyncio.run(scenario())


def test_dismiss_closes_only_its_dialog_and_ignores_repeats_and_dialogs_never_shown():
    async def scenario():
        page, session, conn = mount_page()
        exited = []
        confirm = dialogs.show_confirm(page, "Đang chạy tác vụ", "msg", "Dừng và thoát", lambda: exited.append(1),
                                       danger=True)
        toast = dialogs.toast(page, "Đã sửa xong — rút ra cắm lại cáp nếu máy vẫn chưa hiện")
        dialogs.dismiss(confirm)
        assert (confirm.open, toast.open, last_patch_target(conn)) == (False, True, confirm._i)
        sent = len(conn.sent)
        dialogs.dismiss(confirm)  # already closed: nothing more goes to the client
        assert len(conn.sent) == sent
        await click(session, confirm.actions[1])  # a click that raced the dismiss must not run the action
        assert exited == []
        dialogs.dismiss(ft.AlertDialog())  # never shown
        dialogs.dismiss(ft.AlertDialog(open=True))  # not on a page: flet's update() would raise
        await client_dismissed(session, confirm)
        assert page._dialogs.controls == [toast]

    asyncio.run(scenario())


def test_each_builder_returns_the_instance_it_put_on_the_page():
    page, _session, _conn = mount_page()
    shown = [
        dialogs.show_confirm(page, "Cài driver", "msg", "Cài driver", lambda: None, details=["Google USB Driver"]),
        dialogs.show_summary(page, summary_with_failures()),
        dialogs.show_guide(page),
        dialogs.show_message(page, "Không khởi động được tool", "msg"),
        dialogs.toast(page, "Đã lưu log"),
    ]
    assert [type(d) for d in shown] == [ft.AlertDialog] * 4 + [ft.SnackBar]
    assert all(d.open for d in shown)
    assert all(a is b for a, b in zip(page._dialogs.controls, shown, strict=True))
