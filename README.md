# AGRILENS — AI Plant Health & Disease Diagnosis Kiosk

[![Version](https://img.shields.io/badge/version-v4.2.0-16a34a.svg)](file:///g:/My%20Drive/EXPISCOR%202026/REVISION.md)
[![Build](https://img.shields.io/badge/build-2026--11--01%2007%3A12%20IST-0ea5e9.svg)](file:///g:/My%20Drive/EXPISCOR%202026/REVISION.md)
[![Model](https://img.shields.io/badge/backbone-MobileNetV4%20ONNX-22c55e.svg)](file:///g:/My%20Drive/EXPISCOR%202026/MobileV4/agrilens.onnx)
[![Partner](https://img.shields.io/badge/partner-Gundecha%20Education%20Academy-dc2626.svg)](https://www.gundechaedu.org/)

AGRILENS is an edge AI kiosk system engineered for instant, real-time agricultural crop disease diagnosis in rural and field environments. Built for deployment on Raspberry Pi 5 touch kiosks and PC workstations, it pairs a fast MobileNetV4 ONNX vision backbone with an on-device Leaf Image Quality assessment pipeline and Out-of-Distribution (OOD) rejection gating.

---

## 📌 Build Information

| Attribute | Specification |
| :--- | :--- |
| **Current Version** | **`v4.2.0` (Production Release)** |
| **Last Build Date & Time** | **`2026-11-01 07:12:32 IST` (November 1, 2026)** |
| **Vision Model** | MobileNetV4 Universal Inverted Bottleneck (UIB) ONNX (~10 MB) |
| **Inference Latency** | ~24 ms on CPU (Raspberry Pi 5 / PC) |
| **Diagnostic Classes** | 17 Classes across 4 Crops + Negative Out-of-Distribution Background Rejector |
| **Target Hardware** | Raspberry Pi 5 (8 GB) or PC + Waveshare 7" Capacitive Touch Display (1024×600) + USB Webcam |
| **Python Runtime** | Python 3.10 – 3.13+ |
| **Academic Partner** | Gundecha Education Academy ([gundechaedu.org](https://www.gundechaedu.org/)) |
| **Changelog & Revision History** | See [`REVISION.md`](file:///g:/My%20Drive/EXPISCOR%202026/REVISION.md) |

---

## 🌟 Key Features in v4.2.0

- **High-Accuracy Edge Vision:** Powered by MobileNetV4 ONNX (~10 MB) achieving 98.31% validation accuracy across 17 classes with ~24ms inference speed on CPU.
- **Intuitive Dark Foliage Theme:** Modern agricultural dark-mode aesthetic (`#08100a`, `#0e1a12`, `#15261a`) with crisp pure whites (`#ffffff`, `#f8fafc`), lush emerald green accents (`#16a34a`, `#22c55e`), and high-visibility alert reds (`#ef4444`).
- **High-Fidelity Rounded Pill Buttons:** Custom anti-aliased Tkinter canvas component (`RoundedButton`) with 3x supersampling, Pillow Lanczos downscaling, active hover/pressed dynamic state feedback, and parent alpha blending.
- **Official Gundecha Education Academy Crest:** Integrated official school logo on top-right header with interactive web portal redirection and institution tooltip.
- **Admin Calibration Sliders & Mouse-over `(i)` Tooltips:** PIN-protected Admin panel with real-time sliders for Confidence Threshold ($30\% - 95\%$), OOD Margin ($0.10 - 0.80$), OOD Logit Gate ($1.0 - 10.0$), and Leaf Sharpness Focus ($10 - 150$), each accompanied by interactive information tooltips.
- **Persistent Kiosk Settings (`kiosk_config.json`):** Live parameter adjustments are automatically serialized and restored across reboots.
- **Leaf Quality AI Validator:** Real-time pre-inference analysis:
  - **Focus & Motion Blur:** 5-point discrete spatial Laplacian variance ($0-100\%$).
  - **Lighting & Exposure:** Luminance distribution and specular glare check ($0-100\%$).
  - **Foliage Presence:** Excess Green Index ($2G - R - B$) across target alignment ROI ($0-100\%$).
- **Dedicated Capture / Diagnose Workflow:** Touch-optimized UI with separate `CAPTURE LEAF` (freezes frame) and `DIAGNOSE NOW` (runs inference) actions.
- **Out-of-Distribution (OOD) Protection:** Dual-stage logit gating and Softmax margin check plus `Other_Plant_or_Background` 17th class to reject non-leaf objects, hands, and irrelevant backgrounds.
- **Integrated Extension Recommendations:** Farmer-ready cultural and chemical management guidance for identified crop conditions.

---

## 🖥️ Target Hardware

- **Platform:** Raspberry Pi 5 (8 GB) or Windows / Linux PC
- **Display:** 7" Capacitive Touch Display (1024×600 resolution)
- **Camera:** Standard USB UVC Webcam (640×480 @ 25 FPS)
- **Runtime:** Python 3.10 – 3.13+

---

## 📦 Supported Crops & Disease Classes (17 Classes)

The production model diagnoses 16 crop conditions across 4 primary crops plus 1 negative Out-of-Distribution class:

| Crop / Category | Supported Diagnostic Conditions |
| :--- | :--- |
| **Apple** | Apple Rust, Apple Scab, Healthy |
| **Mango** | Anthracnose, Bacterial Canker, Cutting Weevil, Die Back, Gall Midge, Powdery Mildew, Sooty Mould, Healthy |
| **Pepper** | Bacterial Spot, Healthy |
| **Potato** | Early Blight, Late Blight, Healthy |
| **Out-of-Distribution** | `Other_Plant_or_Background` *(flags non-leaf imagery, hands, desk backgrounds, etc.)* |

---

## 📁 Repository Structure

```text
AGRILENS/
├── MobileV4/                               # Production MobileNetV4 Touch Kiosk Application (v4.2.0)
│   ├── assets/
│   │   └── gundecha_logo.png               # Official Gundecha Education Academy crest
│   ├── agrilens.onnx                       # MobileNetV4 ONNX model graph (~10MB)
│   ├── agrilens.onnx.data                  # Model weight tensors
│   ├── kiosk_config.json                   # Persisted Admin calibration parameters
│   ├── labels.txt                          # 17-class model labels (Apple, Mango, Pepper, Potato, OOD)
│   ├── main.py                             # Complete Touch Kiosk GUI application
│   ├── requirements.txt                    # Standalone dependencies
│   ├── run_agrilens_py313.bat              # Windows Python 3.13 launcher
│   ├── consolidate_datasets.py             # Dataset consolidation pipeline for 4 crops
│   ├── train_mobilenetv4.py                # Local PyTorch MobileNetV4 training script
│   ├── Train_AGRILENS_MobileNetV4.ipynb    # 1-Click Google Colab Training Notebook (Free T4 GPU)
│   ├── README.md                           # MobileV4 Technical Documentation
│   └── REVISION.md                         # MobileV4 Specific Revision Log
│
├── MobileV2/                               # Legacy Baseline Prototype (v2.0.0)
│   ├── dataset/PlantVillage/               # 15-class PlantVillage dataset (Pepper, Potato, Tomato)
│   ├── agri_lens_labels.json               # 15-class label mappings
│   ├── run_20_agri_lens.py                 # Baseline training script
│   └── README.md                           # MobileV2 Documentation
│
├── REVISION.md                             # Comprehensive Version Changelog & Build Log
├── README.md                               # Global Project Documentation (This file)
├── requirements.txt                        # Global Python dependencies
├── run_agrilens_py313.bat                  # Root Windows Python 3.13 Launcher
├── Expiscor 2026.pdf                       # Project research & presentation documentation
└── waveshare display.pdf                   # 7" Waveshare display hardware manual
```

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/shreyuPRO/AGRILENS.git
cd AGRILENS
pip install -r requirements.txt
```

### 2. Launching the Application (MobileNetV4)

- **Windows (Python 3.13+):** Double-click [`run_agrilens_py313.bat`](file:///g:/My%20Drive/EXPISCOR%202026/run_agrilens_py313.bat) in the root folder (or inside [`MobileV4/`](file:///g:/My%20Drive/EXPISCOR%202026/MobileV4/run_agrilens_py313.bat)), or run:
  ```bash
  cd MobileV4
  python main.py
  ```
- **Raspberry Pi 5 / Linux:**
  ```bash
  cd MobileV4
  python3 main.py
  ```

---

## 🔒 Admin Access & Calibration

Access the Admin panel via the **`ADMIN`** button in the top-right corner of the kiosk:
- **Default PIN:** `AGRILENS`
- **Admin Capabilities:**
  - **Diagnostic Calibration Sliders:** Adjust Confidence Threshold, OOD Margin, OOD Logit Gate, and Leaf Sharpness Focus with live persistence to `kiosk_config.json`.
  - **Tooltips:** Hover over the `(i)` icons for explanations of each setting.
  - **Hardware Management:** Scan and reconnect USB webcams on the fly.
  - **System Control:** Safely shut down the kiosk application.

---

## 📜 Revision & Build Tracking

For a detailed history of all builds, architectural migrations, and changelogs, please refer to [`REVISION.md`](file:///g:/My%20Drive/EXPISCOR%202026/REVISION.md).

---

## 📄 License & Disclaimer

*Agricultural advice provided by this software is for advisory guidance only. Always consult local agricultural extension officers before applying chemical treatments.*
