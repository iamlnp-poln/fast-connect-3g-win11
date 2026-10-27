# Fast Connect 3G — Windows 11 Control Center & Driver Fix
### Reverse Engineered for Huawei E173 (MobiFone Fast Connect) on Windows 11 HVCI

[![Platform](https://img.shields.io/badge/Platform-Windows%2011%20%7C%20Windows%2010-0078D4?logo=windows)](https://github.com/iamlnp-poln/fast-connect-3g-win11)
[![Design](https://img.shields.io/badge/UI-WinUI%203%20Fluent%20Design-0067C0)](https://github.com/iamlnp-poln/fast-connect-3g-win11)
[![Driver](https://img.shields.io/badge/Driver-Microsoft%20In--Box%20(usbser%20%2B%20modem)-107C41)](https://github.com/iamlnp-poln/fast-connect-3g-win11)
[![Security](https://img.shields.io/badge/Security-HVCI%20%2F%20Memory%20Integrity%20Compatible-green)](https://github.com/iamlnp-poln/fast-connect-3g-win11)

---

## 📖 Giới thiệu (Overview)

**Fast Connect 3G** là dự án dịch ngược (Reverse Engineering) và phát triển phần mềm điều khiển thế hệ mới dành cho các thiết bị USB DCom 3G Huawei (điển hình là **Huawei E173 / MobiFone Fast Connect**), chạy mượt mà trên **Windows 11 22H2 / 23H2 / 24H2**.

### ⚠️ Vấn đề trên Windows 11 gốc
Khi cắm DCom 3G Huawei cổ (sản xuất giai đoạn 2010–2013) vào Windows 11:
1. **Bị chặn Driver (Code 39 / HVCI Block)**: Tính năng **Memory Integrity (Core Isolation)** của Windows 11 chặn triệt để các driver kernel cũ của Huawei (`ewusbmdm.sys`, `ewusbnet.sys`, `ew_hwusbdev.sys`) do vi phạm cấm thực thi vùng nhớ ghi được (W+X permissions trong section `INIT`).
2. **Xung đột mạng với Wi-Fi**: Khi kết nối 3G qua phần mềm cũ, tuyến định tuyến (Default Gateway Metric) bị chiếm quyền, dẫn tới Wi-Fi báo *"No Internet"* hoặc 3G không vào được mạng.
3. **Phần mềm cũ lỗi thời**: Giao diện MobiFone Fast Connect cũ từ 2011 không tương thích tỉ lệ màn hình hiện đại, thiếu tính năng và thường xuyên treo tiến trình.

---

## ✨ Giải pháp & Tính năng nổi bật

### 1. Giải pháp Driver Microsoft In-Box (100% An toàn HVCI)
- **Không cần tắt Core Isolation / Memory Integrity**: Không hạ thấp bảo mật hệ thống.
- **1-Click Driver Patch**: Tự động gỡ bỏ các driver `.sys` cũ vi phạm và ép Windows 11 ánh xạ thẳng thiết bị sang driver chuẩn chính chủ của Microsoft:
  - **3G Modem (`MI_00`)**: Ánh xạ sang `modem.sys` + `usbser.sys`.
  - **Giao diện điều khiển AT (`MI_03` / `MI_01`)**: Chạy qua `usbser.sys`.
  - **Khởi chạy tức thì**: Tương thích cả `PID_1436` và `PID_1003`.

### 2. Giao diện WinUI 3 Fluent Design hiện đại
- Được xây dựng trên nền tảng PyQt6 và QFluentWidgets với chuẩn Fluent Design Dark Mode của Windows 11.
- **Tự động nhận diện Cắm / Rút phần cứng**: Quét phần cứng thời gian thực qua Windows SetupAPI native (< 1ms), không bao giờ báo lỗi driver giả khi rút thiết bị.
- **Chuyển mạch hai chiều ZeroCD ⇄ User Mode**:
  - Khi ở chế độ Ổ đĩa ảo ZeroCD (`PID_1446` / `E:\`): Nút trung tâm tự động đổi thành `⚡ CHUYỂN SANG USER MODE (MODEM 3G)`.
  - Khi ở chế độ Modem (`PID_1436`): Cung cấp nút chuyển về ổ đĩa ảo bất cứ lúc nào.

### 3. Kết nối mạng ổn định & Quản lý toàn diện
- **Windows RAS PPP Dial-Up (*99#)**: Kích hoạt `Default Gateway 0.0.0.0` với Metric tự động, song hành mượt mà cùng Wi-Fi.
- **Quản lý SMS**: Đọc hộp thư đến, gửi tin nhắn SMS trực tiếp trên SIM DCom.
- **Khóa dải tần sóng (Radio Lock)**: Tùy chọn khóa chip baseband ở chế độ 3G Only (WCDMA) hoặc Tự động (Auto 2G/3G).
- **Cấu hình APN đa nhà mạng**: Tích hợp sẵn profile APN cho **MobiFone**, **Viettel**, **Vinaphone**, **Vietnamobile**.

---

## 📥 Tải về & Cài đặt (Download)

| Phiên bản | Định dạng | Tải về |
| :--- | :--- | :--- |
| **Bản Cài Đặt (Setup Installer)** | `.exe` (~55 MB) | Tự động tạo Desktop shortcut, Start Menu, tích hợp Windows Apps. |
| **Bản Chạy Ngay (Portable Standalone)** | `.zip` (~55 MB) | Giải nén và mở `FastConnect3G.exe` chạy ngay, không cần cài đặt. |

---

## 🛠️ Cấu trúc thư mục dự án

```
Fast Connect/
├── assets/
│   └── icon.ico                    # Biểu tượng 3G chính hãng
├── drivers/
│   ├── Install-All-Recommended.bat # Bộ cài đặt driver tự động (UAC Admin)
│   └── huawei_clean_repack/        # INF mẫu chuẩn Microsoft
├── installer/
│   └── SetupInstaller.cs           # Mã nguồn C# của bộ cài đặt Setup
├── src/
│   ├── at_engine.py                # Engine giao tiếp lệnh AT qua cổng COM
│   ├── dialer.py                   # Quản lý quay số RAS Dial-Up Windows
│   ├── modeswitch.py               # Quét trạng thái PnP & Chuyển mạch ZeroCD SCSI
│   └── winui3_app.py               # Giao diện chính WinUI 3 Fluent Design
├── tools/
│   ├── FixWin11Driver.cs           # Source C# vá driver HVCI bằng SetupAPI
│   ├── FixWin11Driver.exe          # Binary vá driver đã biên dịch
│   ├── ZeroCD_Switch.cs            # Source C# gửi lệnh SCSI CDB chuyển mạch
│   └── ZeroCD_Switch.exe           # Binary gửi SCSI đã biên dịch
├── FastConnectManager.py           # Entry point khởi chạy ứng dụng
├── FastConnect3G.spec              # Cấu hình đóng gói PyInstaller
└── README.md
```

---

## 💻 Hướng dẫn chạy từ mã nguồn (Developers)

### 1. Yêu cầu hệ thống
- Windows 10 / Windows 11 (64-bit)
- Python 3.10 trở lên

### 2. Cài đặt thư viện
```bash
pip install PyQt6 PyQt6-Fluent-Widgets pyserial psutil
```

### 3. Khởi chạy ứng dụng
```bash
python FastConnectManager.py
```

### 4. Đóng gói ứng dụng thành file .exe độc lập
```bash
python -m PyInstaller --clean FastConnect3G.spec
```

---

## 📜 Giấy phép (License)
Dự án được phân phối dưới giấy phép [MIT License](LICENSE). Hoàn toàn miễn phí và mã nguồn mở.
