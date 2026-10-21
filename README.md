# BULL TOOL

![Logo Di Động BULL](bull_tool/assets/bull_logo_64.png)

BULL TOOL là ứng dụng Windows của Di Động BULL, dùng để dọn ứng dụng rác và cài ứng dụng cho điện thoại Android qua cáp USB (ADB), chủ yếu là máy nội địa Trung Quốc và máy Sony thị trường Nhật. Người dùng cuối chỉ nhận một file `BULL-TOOL.exe` giao diện tiếng Việt, chạy offline vì APK, platform-tools và driver USB Xiaomi đã được nhúng sẵn trong exe. Tool thay cho script [`@ANDROID.bat`](@ANDROID.bat).

README này dành cho người bảo trì và cộng tác viên của repo, kể cả AI agent.

## Ràng buộc cần biết

- **Chỉ Windows 10/11 64-bit**, cho cả máy chạy exe lẫn máy build (Flet/Flutter và bản Python mà tool dùng không hỗ trợ Windows 7/8). Yêu cầu đầy đủ của máy build nằm ở mục “Yêu cầu máy build” trong [docs/build-and-release.md](docs/build-and-release.md).
- **Các file đầu vào lớn không nằm trong git.** Thư mục `APK/`, file zip platform-tools, gói driver USB Xiaomi và `upx.exe` phải được cung cấp riêng và đặt ở thư mục gốc repo; tên file, nguồn và việc cần sao lưu xem mục “File đầu vào không có trong git” trong [docs/build-and-release.md](docs/build-and-release.md). Thiếu APK, platform-tools hoặc driver thì không tạo được payload (gói tài nguyên nhúng vào exe, xem mục “Payload nhúng trong exe” trong [docs/architecture.md](docs/architecture.md)), nên chạy từ source sẽ dừng ngay ở bước khởi động và không build được exe; thiếu `APK/` thì [`tests/test_profiles_parity.py`](tests/test_profiles_parity.py) cũng báo lỗi. Muốn xem giao diện khi chưa có các file này thì dùng [`scripts/ui_preview.py`](scripts/ui_preview.py) với dữ liệu giả.
- **`@ANDROID.bat` phải ở lại repo** làm chuẩn đối chiếu (parity); đừng xoá hay đổi tên file này. Các profile (trên giao diện gọi là “dòng máy”) trong [`bull_tool/core/profiles.py`](bull_tool/core/profiles.py) được chép 1:1 từ file `.bat`, danh sách tiến trình mà “Sửa lỗi kết nối” đóng cũng vậy. [`tests/test_profiles_parity.py`](tests/test_profiles_parity.py) và [`tests/test_connection_fixer.py`](tests/test_connection_fixer.py) đọc file `.bat` rồi so từng mục, nên sửa lệnh của profile hay danh sách tiến trình đó thì phải sửa **cả** `@ANDROID.bat` cho khớp; thêm hoặc bớt mục thì cập nhật luôn các con số ghi cứng trong hai file test này. Những chỗ profile cố ý chạy khác `.bat` nằm ở mục “Profile & parity” trong [docs/architecture.md](docs/architecture.md); bước mà “Sửa lỗi kết nối” làm thêm so với `.bat` được ghi trong docstring của [`bull_tool/core/connection_fixer.py`](bull_tool/core/connection_fixer.py).
- **Profile thay đổi điện thoại thật.** Chạy nhầm dòng máy có thể gỡ nhầm ứng dụng, và tool không có chức năng khôi phục ứng dụng đã gỡ. Cảnh báo lệch máy, lệch hãng nằm ở [`bull_tool/ui/view_state.py`](bull_tool/ui/view_state.py) (nội dung cảnh báo, điều kiện khoá nút Bắt đầu) và [`bull_tool/ui/controller.py`](bull_tool/ui/controller.py) (hộp thoại xác nhận, kiểm tra lại máy ngay trước khi chạy); quy tắc chọn máy khi cắm nhiều máy xem mục “Chọn máy & profile (khi cắm nhiều máy)” trong [docs/architecture.md](docs/architecture.md).

## Việc thường gặp

| Việc | Xem ở đâu |
| --- | --- |
| Cài môi trường, chạy từ source, xem giao diện bằng dữ liệu giả | [docs/build-and-release.md](docs/build-and-release.md), mục “Cài đặt môi trường” (đọc trước khi nâng version thư viện) và “Chạy từ source” |
| Sửa danh sách app của một dòng máy | [`bull_tool/core/profiles.py`](bull_tool/core/profiles.py) và [`@ANDROID.bat`](@ANDROID.bat), rồi chạy test theo mục “Kiểm thử” trong [docs/build-and-release.md](docs/build-and-release.md) |
| Thay hoặc thêm APK | [docs/build-and-release.md](docs/build-and-release.md), mục “Thay / thêm APK” |
| Đổi version, link liên hệ, quảng cáo đối tác hoặc logo hiển thị trong app | [`bull_tool/app_info.py`](bull_tool/app_info.py); exe và giao diện lấy version từ đây, không phải từ `pyproject.toml`. Icon và ảnh logo sinh từ `BULL_logo.jpg` và `MTFLASH_logo.png` ở gốc repo bằng [`scripts/build_assets.py`](scripts/build_assets.py) |
| Build `BULL-TOOL.exe` | [docs/build-and-release.md](docs/build-and-release.md), mục “Yêu cầu máy build” và “Build file exe” |
| Tự kiểm tra một exe đã build mà không mở giao diện | [`bull_tool/core/self_test.py`](bull_tool/core/self_test.py): chạy exe (hoặc [`main.py`](main.py)) với tham số `--self-test` |
| Gửi exe cho người dùng; SmartScreen hoặc antivirus cảnh báo; máy tính không nhận điện thoại | [docs/build-and-release.md](docs/build-and-release.md), mục “Phân phối & xử lý sự cố” |
| Tìm log hoặc reset cài đặt của tool trên máy người dùng | [docs/build-and-release.md](docs/build-and-release.md), mục “Dữ liệu tool trên máy người dùng” |
| Hiểu kiến trúc trước khi sửa code | [docs/architecture.md](docs/architecture.md), bắt đầu từ mục “Sơ đồ module” |
| Sửa giao diện | [docs/architecture.md](docs/architecture.md), mục “Luồng sự kiện & threading”; câu chữ hiển thị cho người dùng viết bằng tiếng Việt có dấu |
| Nguồn và giấy phép của font đi kèm | [docs/build-and-release.md](docs/build-and-release.md), mục “Nguồn font (SIL Open Font License 1.1)” |

Thư mục `plans/` là hồ sơ kế hoạch, review và nhật ký ghi theo từng thời điểm: đọc để hiểu lý do của các quyết định, không coi là mô tả hành vi hiện tại. Hành vi hiện tại xem ở source, `tests/`, `scripts/` và `docs/`.
