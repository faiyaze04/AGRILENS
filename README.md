# AGRILENS — AI Plant Health & Disease Diagnosis Kiosk

[![Version](https://img.shields.io/badge/version-v4.8.6-16a34a.svg)](Documentation_and_References/REVISION.md)
[![Build](https://img.shields.io/badge/build-2026--11--15%2014%3A01%20IST-0ea5e9.svg)](Documentation_and_References/REVISION.md)
[![Model](https://img.shields.io/badge/backbone-MobileNetV4--Conv--Small%20ONNX-22c55e.svg)](MobileV4/agrilens.onnx)
[![Classes](https://img.shields.io/badge/classes-24%20Classes%20(4%20Crops)-f59e0b.svg)](MobileV4/labels.txt)
[![Partner](https://img.shields.io/badge/partner-Gundecha%20Education%20Academy-dc2626.svg)](https://www.gundechaedu.org/)

**AGRILENS** is an edge AI kiosk system engineered for instant, real-time agricultural crop disease diagnosis in rural and field environments. Built for deployment on **Raspberry Pi 5** touch kiosks and **Windows/Linux PC** workstations, it pairs a single-file **MobileNetV4-Conv-Small ONNX** vision backbone with training-aligned full-frame multi-scale inference, an on-device **Leaf Image Quality AI** validator, a real-time **Camera Control & ISP Panel**, and **Out-of-Distribution (OOD)** rejection gating.

---

## 📌 Build Information

| Attribute | Specification |
| :--- | :--- |
| **Current Version** | **`v4.8.6` (Production Release)** |
| **Last Build Date** | **`2026-11-15 14:01 IST` (November 15, 2026)** |
| **Vision Model** | MobileNetV4-Conv-Small (`mobilenetv4_conv_small`) Single-File ONNX (~10.07 MB) |
| **Training Dataset** | 23,893 images across 24 classes (15 Epochs, 97.28% – 98.31% Val Accuracy) |
| **Inference Latency** | ~24–40 ms on CPU (3-view training-aligned ensemble on Raspberry Pi 5 / PC) |
| **Diagnostic Classes** | **24 Classes** across **4 Crops** (`Apple`, `Mango`, `Potato`, `Tomato`) + OOD Logit & Margin Gating |
| **Target Hardware** | Raspberry Pi 5 (8 GB) or PC + Waveshare 7" Capacitive Touch Display (1024×600) + USB Webcam |
| **Python Runtime** | Python 3.10 – 3.13+ |
| **Academic Partner** | Gundecha Education Academy ([gundechaedu.org](https://www.gundechaedu.org/)) |
| **Changelog & History** | See [`Documentation_and_References/REVISION.md`](Documentation_and_References/REVISION.md) |

---

## 🌟 Key Features

- **24-Class MobileNetV4 Edge Vision:** Single-file ONNX model (`agrilens.onnx`, ~10.07 MB with all weights embedded) trained across 24 healthy and diseased conditions for Apple, Mango, Potato, and Tomato.
- **Interactive Manual Crop Selection Handles & Mobile Screen Optimization:** Upon capturing a leaf (`CAPTURE LEAF`) or loading an image (`PICK FROM FILE`), an adjustable 8-handle crop selection box appears on the image (pre-inset by 14% to exclude mobile phone bezels and fingers). Pressing **`DIAGNOSE NOW`** runs a dual-stream MobileNetV4 ensemble (Natural RGB + Mobile-Screen De-Moiré / Anti-Glare / Blue-Backlight-Neutralized RGB) strictly on the cropped selection.
- **Direct 1-Tap Admin & Camera Control Panel:** Tapping **`ADMIN`** opens the Admin Console directly (password lock disabled for quick access).
- **Over-The-Air (OTA) Software Updater & Remote Internet Connectivity:** Triggers **immediately on reboot/startup** (`_trigger_ota_update(silent_boot=True)` and `agrilens-ota.service`) and **immediately on manual tap** via the **`☁ OTA UPDATE (INTERNET)`** button in the Admin Console (with strict anti-downgrade version protection and per-file SHA-256 verification). Also includes automated Raspberry Pi remote provisioning (`setup_remote_ota.sh` configuring **Raspberry Pi Connect** and **SSH**).
- **5-Second Startup Splash Logo & 30-Second Inactivity Standby (Camera Auto-Off / Touch-to-Wake):** Loads all branding graphics exclusively from the dedicated `logos/` folder (`logos/agrilens_logo.jpg` and `logos/gundecha_logo.png`). Displays the official **AGRILENS EXPISCOR 2026** logo in the main image window for **5 seconds** on startup, and after **30 seconds of inactivity** automatically displays the logo and turns off the USB camera. Touching anywhere on the screen turns the camera back on and resumes **Live Mode**.
- **Live Mode vs. File Mode Dropdown (`MODE: LIVE MODE ▾` / `MODE: FILE MODE ▾`):** Top-bar dropdown selector allowing instant switching between **Live Mode** (webcam feed) and **File Mode** (browsing default sample images in `diagnosis_samples/{Apple,Mango,Potato,Tomato}`). Defaults to **Live Mode** when a camera is connected, and automatically defaults to **File Mode** when no camera is connected.
- **Full-FoV 4:3 Camera Viewport:** Displays 100% of the 640×480 webcam field of view without cropping on the 1024×600 touch display.
- **Camera Control Panel & Real-Time ISP Pipeline:** Accessible from the Admin Console (`📷 CAMERA CONTROL PANEL`):
  - **Manual Focus Helper & Focus Peaking:** Live focus sharpness meter ($0-100\%$) and optional neon-green edge highlight (`PEAKING: ON`) for calibrating manual-focus lenses.
  - **6 Real-Time ISP Sliders:** Contrast ($50-200\%$), Brightness ($-50\%$ to $+50\%$), Color Saturation ($0-200\%$), Sharpness & Vein Crisping ($50-250\%$), White Balance Temp (Cool $-50$ to Warm $+50$), and Macro Digital Zoom ($1.00\times - 2.00\times$).
  - **Hardware & Orientation Toggles:** Horizontal Mirror (`MIRROR H`), Vertical Flip (`FLIP 180°`), USB Auto-Exposure (`USB AUTO-EXP` with 50Hz power-line anti-flicker via `v4l2-ctl`), and USB Auto White Balance (`USB AUTO-WB`).
- **Admin Calibration Sliders & `(i)` Tooltips:** PIN-protected Admin Console (`PIN: AGRILENS`) with live sliders for Confidence Threshold ($30\% - 95\%$), OOD Ambiguity Margin ($10\% - 60\%$), Neural Logit Energy Gate ($1.00 - 6.50$), and Sharpness Quality Gate ($20 - 120$).
- **Dual-Path Persistent Configuration:** Automatically saves and restores all AI thresholds and camera ISP settings to both `kiosk_config.json` and `~/.agrilens_kiosk_config.json` with value clamping and legacy config migration.
- **Leaf Quality AI Validator:** Real-time pre-inference check scoring **Sharpness/Focus** (40%), **Lighting/Exposure** (30%), and **Center Foliage Presence** (30%).
- **Resilient Cross-Platform Runtime:** Includes automatic missing-package installer (`_auto_install_package`), pure-PNG `ImageTk` fallback when Linux `_imagingtk` is missing, non-blocking async startup, and automatic Raspberry Pi desktop autostart registration (`~/.config/autostart/agrilens.desktop`).

---

## 📦 Supported Crops & Disease Classes (24 Classes)

| Crop | Classes | Supported Conditions |
| :--- | :---: | :--- |
| **Apple** | 3 | `Apple_Rust`, `Apple_Scab`, `Apple_healthy` |
| **Mango** | 8 | `Mango_Anthracnose`, `Mango_Bacterial_Canker`, `Mango_Cutting_Weevil`, `Mango_Die_Back`, `Mango_Gall_Midge`, `Mango_Healthy`, `Mango_Powdery_Mildew`, `Mango_Sooty_Mould` |
| **Potato** | 3 | `Potato_Early_blight`, `Potato_Late_blight`, `Potato_healthy` |
| **Tomato** | 10 | `Tomato_Bacterial_spot`, `Tomato_Early_blight`, `Tomato_Late_blight`, `Tomato_Leaf_Mold`, `Tomato_Septoria_leaf_spot`, `Tomato_Spider_mites_Two_spotted_spider_mite`, `Tomato_Target_Spot`, `Tomato_Tomato_YellowLeaf_Curl_Virus`, `Tomato_Tomato_mosaic_virus`, `Tomato_healthy` |

---

## 📁 Repository Structure

```text
AGRILENS/
├── MobileV4/                                    # PC & Development Touch Kiosk Application
│   ├── logos/
│   │   ├── agrilens_logo.jpg                    # Official AGRILENS EXPISCOR 2026 Startup & Standby Logo
│   │   └── gundecha_logo.png                    # Official Gundecha Education Academy crest
│   ├── diagnosis_samples/                       # 24 Reference test images for File Mode (Apple, Mango, Potato, Tomato)
│   ├── Training_Scripts/
│   │   ├── consolidate_datasets.py              # Dataset verification & consolidation script (24 classes)
│   │   ├── train_mobilenetv4.py                 # Local PyTorch MobileNetV4 15-epoch training & single-file ONNX exporter
│   │   └── Train_AGRILENS_MobileNetV4.ipynb     # 1-Click Google Colab T4 GPU retraining notebook
│   ├── agrilens.onnx                            # Single-file MobileNetV4 ONNX model (~10.07 MB)
│   ├── kiosk_config.json                        # Persisted AI & Camera ISP calibration parameters
│   ├── labels.txt                               # 24-class model label definitions
│   ├── main.py                                  # Main Touch Kiosk GUI application
│   ├── requirements.txt                         # Python dependencies
│   └── run_agrilens_py313.bat                   # Windows Python 3.13 1-click launcher
│
├── AGRILENS_RaspberryPi/                        # Standalone Deployment Package for Raspberry Pi 5
│   ├── logos/
│   │   ├── agrilens_logo.jpg                    # Official AGRILENS EXPISCOR 2026 Startup & Standby Logo
│   │   └── gundecha_logo.png                    # Official Gundecha Education Academy crest
│   ├── diagnosis_samples/                       # 24 Reference test images for offline File Mode testing
│   ├── agrilens.onnx                            # Single-file MobileNetV4 ONNX model (~10.07 MB)
│   ├── HOW_TO_RUN_ON_RASPBERRY_PI.md            # Complete Raspberry Pi 5, Remote Internet & OTA guide
│   ├── kiosk_config.json                        # Raspberry Pi calibrated config defaults
│   ├── labels.txt                               # 24-class model label definitions
│   ├── main.py                                  # Main Touch Kiosk GUI application
│   ├── ota_update.sh                            # Over-The-Air (OTA) GitHub software updater script
│   ├── requirements.txt                         # Python dependencies
│   ├── run_agrilens.sh                          # Linux / Raspberry Pi shell launcher
│   ├── setup_remote_ota.sh                      # Remote Internet (RPi Connect + SSH) & Auto-OTA Timer setup
│   ├── setup_rpi.sh                             # Automated apt + pip + OTA dependency installer for Raspberry Pi OS
│   └── test_deps.py                             # 2-second environment & library diagnostic script
│
├── Documentation_and_References/                # Project Documentation & Changelog
│   ├── README.md                                # Detailed Project Overview
│   └── REVISION.md                              # Comprehensive Build & Version History
│
├── .gitignore                                   # Git exclusions for large datasets and caches
└── README.md                                    # Root Repository Documentation (This file)
```

---

## 🚀 Quick Start

### 1. Windows PC Setup & Launch
```bash
cd MobileV4
pip install -r requirements.txt
python main.py
```
*(Or double-click [`MobileV4/run_agrilens_py313.bat`](MobileV4/run_agrilens_py313.bat) on Windows with Python 3.13 installed.)*

### 2. Raspberry Pi 5 Setup & Launch
See [`AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md`](AGRILENS_RaspberryPi/HOW_TO_RUN_ON_RASPBERRY_PI.md) for full details:
```bash
cd ~/AGRILENS_RaspberryPi
chmod +x setup_rpi.sh run_agrilens.sh
./setup_rpi.sh
python3 test_deps.py
./run_agrilens.sh
```

---

## ⌨️ Controls & Admin Access

- **Touch / Mouse Workflow:**
  - Tap **`SELECT CROP (AUTO)`** in the top-left to either use Auto-Detect across all 4 crops or lock onto a specific crop (`APPLE`, `MANGO`, `POTATO`, `TOMATO`).
  - Tap **`CAPTURE LEAF`** (or **`PICK FROM FILE`** when no camera is attached), drag the **green selection handles** on the image to frame the exact leaf area (double-tap for full image), and tap **`DIAGNOSE NOW`** to run MobileNetV4 inference strictly on the cropped area.
- **Keyboard Shortcuts:**
  - `Space`: Capture Leaf / Retake Leaf
  - `Escape`: Close active overlay panel (or exit application from main screen)
  - `A–Z`, `0–9`, `Backspace`, `Enter`: Type password directly on the Admin lock screen
- **Admin Console (`ADMIN` button in top-right):**
  - **Direct Entry:** Opens directly on tap (password screen disabled).
  - **AI Diagnostic Sliders:** Confidence Threshold, OOD Ambiguity Margin, Neural Logit Energy Gate, Sharpness Quality Gate.
  - **Camera Control Panel (`📷 CAMERA CONTROL PANEL`):** Live focus sharpness bar, neon Focus Peaking, Mirror/Flip toggles, USB Auto-Exposure/Auto-WB toggles, and 6 ISP sliders.

---

## 📄 License & Disclaimer

*Agricultural advice provided by this software is for advisory guidance only. Always consult local agricultural extension officers before applying chemical treatments.*

