# 📋 MobileV4 — Kiosk Application Revision History

This document chronicles all release builds, architecture updates, and UI enhancements specific to the **MobileV4** production kiosk deployment of AGRILENS.

---

## 📌 Active Build Specification

| Parameter | Specification |
| :--- | :--- |
| **Active Version** | **`v4.2.0` (Production Release)** |
| **Last Build Date & Time** | **`2026-11-01 07:12:32 IST` (November 1, 2026)** |
| **Model Format** | MobileNetV4 Universal Inverted Bottleneck (UIB) ONNX (`agrilens.onnx` + `agrilens.onnx.data`) |
| **Model Footprint** | ~10 MB (~24ms CPU inference latency) |
| **Classes Supported** | 17 Classes across 4 Crops + Out-of-Distribution Background Rejector |
| **Kiosk Configuration** | Calibrated via `kiosk_config.json` |
| **Institutional Partner** | Gundecha Education Academy ([gundechaedu.org](https://www.gundechaedu.org/)) |

---

## 📜 Build Changelog

### Version 4.2.0 — 2026-11-01 07:12:32 IST
- **Theme Revamp**: Replaced grey panels with Dark Foliage Obsidian theme (`#08100a`, `#0e1a12`, `#15261a`, `#213d29`). High-contrast pure white text (`#ffffff`) and vivid alert red (`#ef4444`).
- **Rounded Pill Buttons**: Developed `RoundedButton(tk.Canvas)` with 3x supersampling, Pillow Lanczos downscaling, active hover/pressed dynamic state feedback, and parent alpha blending.
- **Official Gundecha Education Academy Logo**: Top-right header logo badge linking to `https://www.gundechaedu.org/` with institutional tooltip.
- **Admin Parameter Sliders**: 4 real-time calibration sliders with mouse-over `(i)` info tooltips:
  - Confidence Threshold Slider ($30\% - 95\%$)
  - OOD Margin Slider ($0.10 - 0.80$)
  - OOD Logit Gate Slider ($1.0 - 10.0$)
  - Leaf Sharpness Minimum Focus Slider ($10 - 150$)
- **Configuration Persistence**: Live slider changes automatically saved to `kiosk_config.json`.
- **Robust Webcam Detection Engine (DirectShow & V4L2 Cascading)**:
  - Resolved Windows Media Foundation (MSMF) frame grabbing failure (`CvCapture_MSMF::grabFrame -1072873822`) by implementing platform-prioritized backend cascading: `cv2.CAP_DSHOW` (DirectShow) -> `cv2.CAP_MSMF` -> `cv2.CAP_ANY` on Windows, and `cv2.CAP_V4L2` -> `cv2.CAP_ANY` on Linux/Raspberry Pi.
  - Eliminated OpenCV Orbbec sensor console warning spam (`obsensor_uvc_stream_channel.cpp Camera index out of range`) by setting OpenCV log level to `LOG_LEVEL_ERROR` and using explicit backends.
  - Integrated friendly device hardware discovery via Windows PnP (`Get-PnpDevice`) and Linux sysfs, showing real device names (e.g. `C270 HD WEBCAM (Port 0, DirectShow, 640x480)`).
  - Pre-configured 640x480 resolution and zero-lag single-frame buffer (`CAP_PROP_BUFFERSIZE = 1`) prior to stream initialization.
  - Added multi-frame sensor warmup loop (5 reads with AGC/AEC stabilization) and automatic fault-tolerant recovery if a camera is disconnected.
- **Build Metadata**: App version `4.2.0` and build date `2026-11-01 07:12:32 IST` displayed in title bar, header tooltip, and Admin system card.

---

### Version 4.1.0 — 2026-10-31 21:45:00 IST
- **Negative Class & OOD Rejection**: Added `Other_Plant_or_Background` as 17th class with logit margin filtering.
- **Colab 1-Click Retraining Notebook**: Created `Train_AGRILENS_MobileNetV4.ipynb` for automated T4 GPU training and ONNX export.
- **Dataset Consolidation**: Created `consolidate_datasets.py` unifying Apple, Mango, Pepper, and Potato image folders.

---

### Version 4.0.0 — 2026-10-30 18:30:00 IST
- **Initial MobileNetV4 Migration**: Replaced MobileNetV2 Keras model with MobileNetV4 ONNX.
- **Dedicated Touch Controls**: Separate `[CAPTURE LEAF]` and `[DIAGNOSE NOW]` buttons.
- **Leaf Quality AI**: Integrated focus (Laplacian), lighting (luminance), and foliage presence ($2G - R - B$) pre-inference checks.
- **Platform Packaging**: Added `run_agrilens_py313.bat` Windows launcher.
