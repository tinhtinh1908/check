# Kiến trúc BULL TOOL

App Python 3.14 + Flet 1.0. Thay cho `@ANDROID.bat`: dọn ứng dụng rác và cài ứng dụng cho 5 dòng máy qua ADB. Đóng gói thành một file exe duy nhất chứa sẵn APK, platform-tools và driver Xiaomi.

## Sơ đồ module

```text
main.py                     --self-test | single instance → ft.run(ui.app.main)
bull_tool/
├─ app_info.py              tên, version, link liên hệ / quảng cáo
├─ core/                    không phụ thuộc UI
│  ├─ payload.py            ResourceStore: zip nhúng trong exe (hoặc .build/payload.zip khi dev)
│  ├─ platform_tools.py     giải nén adb.exe vào %LOCALAPPDATA%, size+CRC, tự sửa file hỏng
│  ├─ adb/                  client giao thức adb server (127.0.0.1:5037), viết thuần Python
│  │  ├─ protocol.py        khung OKAY/FAIL, shell v2, sync SEND/DATA/DONE
│  │  ├─ client.py          devices, track, shell, push, install, install-multiple (stream + % theo byte)
│  │  └─ server.py          start/kill adb server; chỉ kill khi chính tool đã start (owned)
│  ├─ profiles.py           5 profile chép 1:1 từ .bat + hướng dẫn gỡ lỗi USB
│  ├─ job_runner.py         chạy profile: bỏ qua package không có, trọng số %, dừng giữa chừng, tổng kết
│  ├─ device_info.py        getprop + 1 lệnh shell gộp → DeviceInfo
│  ├─ device_monitor.py     host:track-devices-l (realtime, tự kết nối lại, pause/resume)
│  ├─ driver_installer.py   phát hiện qua DriverStore, cài bằng pnputil (UAC)
│  ├─ connection_fixer.py   tương đương mục 7 của .bat
│  ├─ bootstrap.py          trình tự khởi động + AppServices.shutdown
│  ├─ events.py             EventBus thread-safe, Logger, Progress
│  ├─ settings.py, session_log.py, win32.py, paths.py, self_test.py
└─ ui/                      Flet, mọi thay đổi UI chạy trên event loop
   ├─ app.py                cửa sổ, theme, font → AppController
   ├─ controller.py         nối sự kiện bus vào component, chạy job trong thread
   ├─ view_state.py         logic thuần (chọn máy, khoá nút, cảnh báo lệch hãng)
   ├─ ui_pump.py            drain EventBus mỗi 50 ms, chỉ update control "dirty"
   ├─ theme.py, widgets.py  design token (ColorScheme), breakpoint, control dùng chung
   └─ title_bar, status_bar, device_panel, profile_grid, progress_panel, console_view,
      tools_panel, contact_card, dialogs, shell_layout
scripts/                    build_assets, build_payload, inject_payload, build_exe, fetch_fonts, ui_preview
```

## Payload nhúng trong exe

```text
[PE bootloader][payload.zip][trailer <8sQ: "BULLPAY1", len>][PyInstaller PKG … cookie]
```

- Bootloader PyInstaller tìm PKG qua cookie ở cuối file (`pkg_start = cookie_end − archive_len`), nên bỏ qua dữ liệu chèn phía trước.
- `payload.locate_payload()` đọc cookie, rồi trailer, ra `(offset, length)`.
- `SubFile` + `zipfile` đọc payload ngay trong exe, không giải nén ra đĩa.
- APK để dạng `ZIP_STORED` và được **stream thẳng** sang điện thoại; `zipfile` kiểm CRC khi đọc tới cuối file.
- Driver `.7z` được giải nén lúc build (thư mục `USB_DRIVER_XIAOMI/`) để runtime chỉ cần stdlib.

## ADB

- `adb.exe` chỉ dùng cho `start-server`. Mọi lệnh khác đi qua socket tới server.
- Nếu đã có server khác đang chạy (ví dụ của scrcpy) thì dùng luôn server đó.

| Việc | Service |
| --- | --- |
| Theo dõi thiết bị | `host:track-devices-l` |
| Shell (lấy exit code) | `shell,v2,raw:<cmd>` (fallback `shell:` + marker) |
| Cài APK | `exec:cmd package install -S <size>` + stream byte |
| Split APK | `install-create` → `install-write -S … -` (stream) → `install-commit` / `install-abandon` |
| Chép vào Download | `sync:` SEND/DATA(64 KiB)/DONE |
| Android < 7 | push vào `/data/local/tmp` + `pm install` |

## Luồng sự kiện & threading

```text
worker thread (bootstrap, runner, monitor, fixer, driver) ──emit──▶ EventBus (SimpleQueue)
UiPump (async, page loop, mỗi 50 ms) ──drain──▶ log gom theo lô, chỉ lấy progress mới nhất mỗi job ──▶ control.update()
event handler UI (async) ──▶ run_in_daemon(job) ──▶ kết quả quay lại qua EventBus / giá trị trả về
```

- Không có thread nào chạm vào control Flet trừ event loop.
- Pump bọc lỗi từng handler, vòng lặp không bao giờ dừng. Control chưa gắn vào trang hoặc đã bị gỡ (không còn trong index của session) thì bỏ qua, không báo lỗi.
- **Tắt auto-update của Flet** (`ft.context.disable_auto_update()` ở module `ui/app.py`, chạy lúc import, trước `ft.run`). Mặc định Flet diff lại cả trang sau mỗi event handler (~60 ms khi console đầy), nên cuộn log hay kéo cửa sổ sẽ làm đơ loop. Quy tắc: mọi thay đổi UI phải đi qua `UiPump.mark_dirty`/`flush` hoặc gọi `.update()`/`page.update()` tường minh.
- Job (profile, sửa kết nối, driver) chạy trên **daemon thread** (`controller.run_in_daemon`). Thread của `asyncio.to_thread` bị join khi thoát, nên một job còn dở sẽ giữ process chạy ngầm (và giữ khoá single-instance).
- Console chia mỗi 40 dòng thành một `Text` (spans) **isolated**: diff của `ListView`/trang không đi vào span của chunk cũ (span không bao giờ bị sửa sau khi gửi). Mỗi tick chỉ gửi lại chunk vừa thêm dòng; cắt chunk cũ theo số chunk nên mỗi chunk mới chỉ tốn một lần update `ListView`.
- Đo bằng `ui_preview.py --scenario stress` (200 dòng/s, console đã đầy 3.000 dòng, 40 s): process Python ~11% một core, client Flet ~16% (trước khi tắt auto-update và isolate chunk: Python ~90%).

## Khởi động & tắt

**Khởi động** (bootstrap):

1. mở payload;
2. platform-tools (self-heal);
3. adb server;
4. driver (lần đầu trên máy: tự cài qua UAC; người dùng từ chối thì ghi nhớ, không hỏi lại);
5. `DeviceMonitor`.

**Đóng app:** `prevent_close` → đang có job thì hỏi xác nhận (chỉ một hộp thoại; job tự xong thì hộp thoại tự đóng) → `_shutdown_and_exit`:

1. `AppServices.begin_close()`: chốt `AdbServer` để **không gì khởi động adb được nữa** (monitor, sửa kết nối, bootstrap đang chạy dở); bootstrap dừng ở bước kế tiếp, không hỏi UAC sau khi cửa sổ đã đóng;
2. đang có job → bật cancel, console ghi “Đang dừng tác vụ trước khi thoát…”, chờ job tới checkpoint (tối đa 10 s);
3. `AppServices.shutdown()`: dừng monitor → kill adb server **chỉ khi** tool đã tự start → đóng store → đóng session log **sau cùng** (giữ được dòng log cuối của job);
4. `window.destroy()`.

`page.on_close` (client Flet mất đột ngột) → `on_session_closed`: bật cancel cho job rồi shutdown ngoài event loop. `atexit` gọi lại `shutdown` (idempotent) làm chốt cuối.

## Profile & parity

- `profiles.py` giữ đúng thứ tự lệnh của `.bat`; chỉ bỏ dòng trùng y hệt.
- **Khác với .bat (có chủ đích):**
  - bỏ qua package không có cho user 0, hoặc đã bị tắt sẵn (không gọi lệnh lên máy; kết quả cuối giống `.bat`);
  - bước `requires_pkg` (IME Gboard, Chrome mặc định) thiếu package thì SKIP;
  - bước cuối tắt ADB (Oppo/Honor/Vivo) khiến máy ngắt kết nối → tính là thành công, nhưng chỉ khi máy còn kết nối ngay trước bước đó;
  - một bước bị ngắt luồng (ví dụ cài lỗi do đầy bộ nhớ, phản hồi `Failure [...]` được giữ lại) mà máy **vẫn còn kết nối** → ghi lỗi cho bước đó rồi chạy tiếp, giống `.bat`;
  - máy **thật sự mất** (rút cáp) → dừng job và báo “Mất kết nối”, không chạy tiếp các lệnh còn lại vào khoảng trống;
  - trước khi chạy kiểm tra trạng thái máy: chưa cho phép gỡ lỗi USB / offline → báo bằng tiếng Việt, không chạy.
- `tests/test_profiles_parity.py` parse `@ANDROID.bat` và so khớp 100%.

## Độ bền

- Mọi worker (bootstrap, runner, monitor, fixer, driver) đều kết thúc bằng một trạng thái mà UI hiển thị được, kể cả khi gặp lỗi không lường trước. Payload hỏng → bootstrap báo lỗi nghiêm trọng thay vì treo màn hình khởi động.
- Lỗi socket khi gửi được đổi thành lỗi ADB, nên monitor tự kết nối lại thay vì chết.
- Trong lúc chờ điện thoại xác nhận cài đặt (tối đa 300 s), kể cả khi commit split APK (Zalo/Facebook), nút Dừng vẫn có tác dụng ngay.
- Cài driver tự động lần đầu không thành công (từ chối UAC hoặc pnputil lỗi) → không tự hỏi lại ở các lần mở sau; nút “Driver USB Xiaomi” vẫn dùng được.
- `settings.json` ghi tuần tự (lock): lần ghi sau cùng luôn mang giá trị mới nhất; lỗi ghi file trả về `False`, không làm sập phiên.

## Chọn máy & profile (khi cắm nhiều máy)

Logic thuần nằm ở `ui/view_state.py`, test ở `tests/test_view_state.py` và `tests/test_controller.py`.

- **Máy của người dùng** (`preferred_serial`): máy chọn trong dropdown, máy cắm vào khi chưa có máy nào, hoặc máy vừa chạy job. Cáp chập chờn hay adb kết nối lại → tool tự chọn lại đúng máy đó khi nó xuất hiện. Máy đã cắm cùng lúc với máy của người dùng (trước khi danh sách trống, ví dụ do “Sửa lỗi kết nối” hay hub chập chờn) không được nhận làm máy của người dùng khi nó hiện lại trước; chỉ máy mới hẳn mới được nhận.
- Nút Bắt đầu chạy trên một máy **khác** máy của người dùng (vì máy đó đã rút) → luôn hỏi lại, nêu rõ máy và serial. Hộp thoại xác nhận mở lâu mà máy/dòng máy đã đổi → không chạy, báo người dùng kiểm tra lại.
- **Chọn dòng máy bằng tay** gắn với máy đang được chọn lúc bấm (`manual_pick` = serial + model adb, chỉ nhớ lần chọn gần nhất): cắm lại đúng máy đó vẫn giữ lựa chọn; máy khác, kể cả máy rẻ tiền trùng serial nhưng khác model, được tự gợi ý theo hãng. Máy được đọc thông tin trong lúc đang chạy một tác vụ sẽ được gợi ý ngay khi tác vụ xong.
- Đọc thông tin máy chạy **lần lượt từng máy**; kết quả/lỗi luôn gắn đúng máy. Trong lúc đang đọc thông tin máy được chọn, nút Bắt đầu bị khoá (“Đang đọc thông tin máy…”), tránh chạy profile của máy trước lên máy mới.
- Nút trong hộp thoại chỉ đóng **chính hộp thoại đó** (không đóng nhầm thông báo nổi), bấm đúp không chạy hai lần.
