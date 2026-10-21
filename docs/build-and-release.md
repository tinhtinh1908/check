# Build & phát hành BULL TOOL

Tài liệu cho người bảo trì: chạy từ source, build file `BULL-TOOL.exe`, thay APK, xử lý sự cố.

## Yêu cầu máy build

| Thành phần | Ghi chú |
| --- | --- |
| Windows 10/11 x64 | Bản exe chỉ chạy trên Windows 10/11 64-bit |
| Python 3.14 x64 | `py -3.14` |
| Dung lượng trống ≥ 4 GB | payload ~1,5 GB + exe ~1,55 GB |
| Internet (lần đầu) | `pip install` và tải client Flet vào `~/.flet/client` |
| Windows 11 **hoặc** 7-Zip | Giải nén `USB_DRIVER_XIAOMI.7z` (LZMA2 + BCJ) lúc build; `tar` của Windows 10 không đọc được LZMA |

## Cài đặt môi trường

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

Các version đã ghim trong `requirements*.txt`. **Không nâng PyInstaller** khi chưa chạy lại test `slow`. Payload được chèn vào exe dựa trên layout onefile của PyInstaller 6.22.3, và build sẽ dừng nếu version khác.

## File đầu vào không có trong git

Bốn mục dưới đây quá nặng để đưa vào git (nhóm “Large binary build inputs” trong `.gitignore`), nên phải chép vào thư mục gốc repo trước khi chạy từ source hay build. Git không giữ bản nào, vì vậy cần tự sao lưu cả bộ, ví dụ để cùng chỗ với file exe phát hành.

| File | Dùng để | Lấy ở đâu |
| --- | --- | --- |
| `APK/` | Cài hoặc chép lên điện thoại theo profile | Repo không ghi nguồn; bộ hiện tại do người bảo trì cung cấp. Tên từng file phải khớp các đường dẫn `APK/…` trong `bull_tool/core/profiles.py` |
| `platform-tools-latest-windows.zip` | `adb.exe` nhúng trong exe | Google. `https://dl.google.com/android/repository/platform-tools-latest-windows.zip` luôn trả về bản mới nhất. Muốn đúng bản đang dùng thì tải `https://dl.google.com/android/repository/platform-tools_r<revision>-win.zip` rồi đổi tên thành `platform-tools-latest-windows.zip`; revision đang dùng hiện ở mục platform-tools trong kết quả `--self-test` |
| `USB_DRIVER_XIAOMI.7z` | Driver USB Xiaomi, cài bằng `pnputil` trên máy người dùng | Repo không ghi nguồn; bộ hiện tại do người bảo trì cung cấp |
| `upx.exe` | Nén DLL/PYD trong exe lúc build | UPX bản Windows 64-bit: <https://github.com/upx/upx/releases>. Xem version bằng `upx.exe -V` |

## Chạy từ source

```powershell
.venv\Scripts\python scripts\build_payload.py   # lần đầu hoặc khi đổi APK / platform-tools / driver
.venv\Scripts\python main.py
```

Ở chế độ dev, tool đọc tài nguyên từ `.build/payload.zip`. Script tự bỏ qua bước build nếu input không đổi.

Xem giao diện không cần điện thoại (dữ liệu giả):

```powershell
.venv\Scripts\python scripts\ui_preview.py --scenario running --size 1366x768 --theme light
.venv\Scripts\python scripts\ui_preview.py --scenario multi --size 880x540 --screenshot multi.png   # chụp rồi tự thoát
```

Các scenario có sẵn: `starting`, `empty`, `unauthorized`, `ready`, `multi`, `running`, `done` (hiện bảng tổng kết), `stress` (200 dòng log/giây), `guide` và `fix` (mở sẵn hộp thoại hướng dẫn / xác nhận sửa kết nối).

- `--screenshot <file.png>` chụp giao diện chính sau `--delay` giây (mặc định 5) rồi thoát; `--pixel-ratio` đổi độ phân giải ảnh. Hộp thoại và thông báo nổi nằm ngoài vùng chụp này: với `done`, `guide`, `fix` hãy chụp bằng công cụ chụp màn hình của Windows.
- Preview lưu `settings.json` vào thư mục tạm, không đụng tới cấu hình thật của app. “Sửa lỗi kết nối” và “Driver USB Xiaomi” trong preview chỉ mô phỏng các bước, không đóng ứng dụng hay cài gì lên máy.

## Build file exe

```powershell
.venv\Scripts\python scripts\build_exe.py
```

Các bước script chạy (bước nào lỗi thì dừng ngay):

1. Kiểm tra môi trường: Python 3.14 x64, PyInstaller 6.22.3, có `upx.exe`, đủ dung lượng.
2. `scripts/build_assets.py`: sinh `icon.ico` (10 size) và logo PNG từ `BULL_logo.jpg` / `MTFLASH_logo.png`.
3. `scripts/build_payload.py`: đóng gói `APK/**` (STORED), `platform-tools-latest-windows.zip` và thư mục driver.
4. `flet pack` (PyInstaller onefile + UPX từ `upx.exe`, icon, thông tin version). Script đếm số DLL/PYD thực sự được UPX nén và dừng nếu không nén được file nào. Log ở `.build/pack/pack.log` (giữ lại khi build lỗi hoặc khi chạy với `--keep-work`).
5. `scripts/inject_payload.py`: chèn payload trước archive PKG của PyInstaller, rồi kiểm tra lại bằng `CArchiveReader` và CRC toàn bộ.
6. Chạy `release/BULL-TOOL.exe --self-test --full`, kết quả ghi vào `.build/selftest.json`.

Kết quả: `release/BULL-TOOL.exe` (một file duy nhất; cửa sổ, taskbar và thông tin sản phẩm vẫn mang tên “BULL TOOL”). Tham số thêm:

- `--skip-payload`: dùng payload đã build sẵn;
- `--keep-work`: giữ thư mục `.build/pack`.

Về UPX: build hiện tại nén được 21/64 DLL/PYD (trong đó có `python314.dll`, `libcrypto`, các `.pyd`). PyInstaller tự bỏ qua các DLL bật CFG (`ucrtbase`, `api-ms-win-*`), còn `vcruntime140*.dll` và `python3.dll` được loại trừ chủ động. Hơn 95% dung lượng exe là APK đã nén sẵn, nên UPX chỉ giảm được vài MB. Pillow (chỉ dùng lúc build icon) được loại khỏi exe.

## Kiểm thử

```powershell
.venv\Scripts\python -m pytest -m "not slow"   # nhanh
.venv\Scripts\python -m pytest                 # gồm test build exe thật bằng PyInstaller
.venv\Scripts\ruff check .
```

`tests/test_profiles_parity.py` đối chiếu từng lệnh của 5 profile với `@ANDROID.bat`. Khi sửa danh sách app, sửa **cả hai** file `bull_tool/core/profiles.py` và `@ANDROID.bat`, nếu không test sẽ báo lệch.

## Thay / thêm APK

- **Thay APK cùng tên** (ví dụ YouTube bản mới): chép đè file trong `APK/`, rồi build lại.
- **Đổi tên hoặc thêm APK:** sửa đường dẫn trong `bull_tool/core/profiles.py` (`Install("APK/…")`, `Push(…)`, `InstallMulti(…)`), sửa `@ANDROID.bat` tương ứng, rồi chạy `pytest` trước khi build.
- **Đổi version:** sửa `VERSION` trong `bull_tool/app_info.py`.

## Dữ liệu tool trên máy người dùng

`%LOCALAPPDATA%\BULL-TOOL\` gồm:

| Mục | Nội dung |
| --- | --- |
| `platform-tools\` | `adb.exe` và DLL. Mỗi lần mở tool kiểm tra size + CRC; file hỏng sẽ được giải nén lại |
| `driver\` | Gói driver Xiaomi dùng cho `pnputil` |
| `logs\` | Log từng phiên, giữ 20 file gần nhất |
| `settings.json` | Theme; cờ “đã thử tự cài driver” (UAC bị từ chối hoặc cài lỗi thì không tự hỏi lại) |

Muốn tool hỏi cài driver lại từ đầu: xoá `settings.json`. Xoá cả thư mục cũng an toàn; tool sẽ tạo lại khi mở.

## Phân phối & xử lý sự cố

- **Dung lượng ~1,55 GB:** vượt giới hạn 1 GB/file của Zalo → gửi qua Google Drive hoặc USB.
- **SmartScreen** báo “Windows protected your PC” (exe chưa ký số): bấm *More info → Run anyway*.
- **Defender / AV báo nhầm hoặc xoá exe:** nguyên nhân thường gặp là exe PyInstaller + UPX không ký số. Xử lý bằng cách thêm exclusion hoặc gửi file cho Microsoft xét lại (Microsoft Security Intelligence → Submit a file). Ký số chưa nằm trong phạm vi bản này.
- **Build lỗi "cannot extract USB_DRIVER_XIAOMI.7z":** máy build cần Windows 11 hoặc cài 7-Zip.
- **"flet pack failed":** xem `.build/pack/pack.log`. Lần build đầu cần mạng để Flet tải client desktop.
- **Máy không nhận điện thoại:** dùng “Sửa lỗi kết nối” trong tool. Tính năng này đóng HiSuite, Phone Link, scrcpy… và mọi `adb.exe`, rồi khởi động lại ADB của tool.

## Nguồn font (SIL Open Font License 1.1)

URL đã ghim và SHA-256 nằm trong `bull_tool/assets/fonts/SOURCES.txt`. Muốn tải lại thì chạy `scripts/fetch_fonts.py`.

- Be Vietnam Pro: google/fonts @ `c13390277dfb1fcc7415d84ef7ef9cfc1e52f8c1`
- JetBrains Mono: JetBrains/JetBrainsMono @ `v2.304`
