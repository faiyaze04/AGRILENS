# 📋 AGRILENS — Build Revision & Version History

This document provides a comprehensive build log and changelog for the **AGRILENS** AI Plant Health & Disease Diagnosis Kiosk system.

---

## 📌 Current Build Information

| Attribute | Specification |
| :--- | :--- |
| **Current Version** | **`v4.2.0` (Production Release)** |
| **Last Build Date & Time** | **`2026-11-01 07:12:32 IST` (November 1, 2026)** |
| **Build Hash / Identifier** | `BUILD-20261101-0712-V420` |
| **Vision Backbone** | MobileNetV4 Universal Inverted Bottleneck (UIB) in ONNX format |
| **Model Weights** | `MobileV4/agrilens.onnx` (10,032,141 bytes) & `agrilens.onnx.data` (10,028,544 bytes) |
| **Supported Classes** | 17 Classes (4 Crops + Out-of-Distribution Background Class) |
| **Runtime Target** | Python 3.10 – 3.13+ (Tested on Windows 11 & Raspberry Pi OS 64-bit) |
| **Target Hardware** | Raspberry Pi 5 (8GB) or PC + 7" Capacitive Touch Display (1024×600) + USB Webcam |
| **Academic Partner** | Gundecha Education Academy ([gundechaedu.org](https://www.gundechaedu.org/)) |

---

## 🏷️ Version Summary & Evolution

| Version | Release Date & Time | Primary Engine | Classes | Latency (CPU) | Key Highlights |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`v4.2.0`** | **2026-11-01 07:12:32 IST** | **MobileNetV4 ONNX** | **17 Classes** | **~24 ms** | **Dark Foliage Theme, Rounded Pill Buttons, GEA Official Logo, Admin Parameter Sliders & Tooltips, Config Persistence** |
| `v4.1.0` | 2026-10-31 21:45:00 IST | MobileNetV4 ONNX | 17 Classes | ~24 ms | Negative Class Gating (`Other_Plant_or_Background`), 1-Click Colab Retraining Notebook, OOD Margin & Logit Thresholding |
| `v4.0.0` | 2026-10-30 18:30:00 IST | MobileNetV4 ONNX | 17 Classes | ~24 ms | Migration from V2 to V4, Touch-optimized `[CAPTURE]` / `[DIAGNOSE]` workflow, Leaf Image Quality AI (Sharpness, Glare, Foliage Coverage) |
| `v2.0.0` | 2026-10-25 14:00:00 IST | MobileNetV2 Keras | 15 Classes | ~140 ms | Legacy baseline prototype using TensorFlow/Keras on PlantVillage dataset (54MB model) |

---

## 📜 Detailed Changelog by Build

### [v4.2.0] — 2026-11-01 07:12:32 IST
#### ✨ Added & Enhanced
1. **Dark Foliage Obsidian Color Palette**:
   - Replaced generic grey interface with an agricultural dark-mode aesthetic:
     - Background: Deep Obsidian Forest (`#08100a`)
     - Panels: Dark Foliage Slate (`#0e1a12`)
     - Cards: Deep Leaf Card (`#15261a`)
     - Borders: Crisp Dark Green (`#213d29`)
     - Primary / Healthy: Emerald Lush Green (`#16a34a` / `#22c55e`)
     - Disease Alert / Critical: High-contrast Alert Red (`#ef4444` / `#dc2626`)
     - Typography: Crisp Pure White (`#ffffff` / `#f8fafc`) and Muted Slate (`#94a3b8`)
2. **High-Fidelity Rounded Pill Buttons (`RoundedButton`)**:
   - Built a bespoke anti-aliased Tkinter canvas component (`RoundedButton(tk.Canvas)`) replacing blocky rectangular widgets.
   - Features 3x supersampling with Pillow Lanczos downscaling, active hover/press brightness transitions, and parent background alpha blending.
3. **Official Gundecha Education Academy Logo Badge**:
   - Embedded official GEA institution crest (`MobileV4/assets/gundecha_logo.png`) on the top-right header.
   - Rendered inside an anti-aliased white rounded pill badge with clickable portal redirection to [gundechaedu.org](https://www.gundechaedu.org/) and hover tooltip.
4. **Admin Console Calibration Parameter Sliders**:
   - Integrated 4 interactive sliders within the PIN-protected Admin panel:
     - **Confidence Threshold Slider** ($30\% - 95\%$): Adjusts minimum threshold for positive disease identification.
     - **OOD Margin Threshold Slider** ($0.10 - 0.80$): Sets minimum gap between top-1 and top-2 Softmax probabilities.
     - **OOD Logit Gate Slider** ($1.0 - 10.0$): Raw unnormalized logit threshold to reject ambiguous leaf inputs.
     - **Leaf Sharpness Min Slider** ($10 - 150$): Adjusts focus threshold for the spatial Laplacian blur detector.
5. **Interactive Mouse-Over `(i)` Information Tooltips**:
   - Added hover information icons with non-blocking tooltip popups explaining each parameter's agricultural and computer vision function.
6. **Persistent Configuration (`kiosk_config.json`)**:
   - Live calibration adjustments are serialized to `MobileV4/kiosk_config.json` and restored automatically on next kiosk boot.
7. **Build Versioning & Metadata**:
   - Integrated `APP_VERSION` (`4.2.0`) and `BUILD_TIMESTAMP` (`2026-11-01 07:12:32 IST`) into kiosk window title, header bar tooltip, and Admin System card.

#### 🧹 Maintenance & Cleanup
- **Redundant File Cleanup**:
  - Removed obsolete intermediate image scratch files from `MobileV4/assets/`: `gea_header_badge.png`, `gundecha_badge.png`, `gundecha_logo_cropped.png`, `logo_thumb.png`.
  - Removed duplicate root `MobileV4/gundecha_logo.png`, consolidating all static assets into `MobileV4/assets/gundecha_logo.png`.
- **Character Encoding Fix**:
  - Replaced non-BMP emoji symbols in button labels with clean text (`CAPTURE LEAF`, `RETAKE LEAF`, `DIAGNOSE NOW`, `ADMIN`) to eliminate Windows CP1252 stdout encoding errors.

---

### [v4.1.0] — 2026-10-31 21:45:00 IST
#### ✨ Added & Enhanced
1. **Out-of-Distribution (OOD) Protection**:
   - Added class `Other_Plant_or_Background` as the 17th model output to reject fingers, desks, hands, and irrelevant backgrounds.
   - Implemented dual-stage OOD gating: Softmax probability thresholding combined with top-1/top-2 logit margin checks.
2. **1-Click Google Colab Retraining Pipeline (`Train_AGRILENS_MobileNetV4.ipynb`)**:
   - Jupyter notebook for automated retraining on Google Colab with free T4 GPU (~15 minutes).
   - Direct Google Drive mounting and automated export to `agrilens.onnx` and `labels.txt`.
3. **Automated Dataset Consolidation (`consolidate_datasets.py`)**:
   - Automated folder consolidation script standardizing Apple, Mango, Pepper, and Potato image folders into a unified training hierarchy.

---

### [v4.0.0] — 2026-10-30 18:30:00 IST
#### ✨ Added & Enhanced
1. **MobileNetV4 Universal Inverted Bottleneck (UIB) Architecture**:
   - Upgraded from legacy MobileNetV2 to state-of-the-art MobileNetV4 ONNX.
   - Reduced model weight footprint from 54MB to ~10MB while slashing CPU inference latency from ~140ms to ~24ms.
2. **Two-Stage Touch Workflow**:
   - Separated inspection into `[CAPTURE LEAF]` (freezes camera feed into high-res diagnostic buffer) and `[DIAGNOSE NOW]` (runs ONNX model inference).
3. **Leaf Image Quality AI Validator**:
   - Real-time pre-inference analysis:
     - Spatial Laplacian focus check (sharpness score $0-100\%$).
     - Luminance distribution & specular glare detector (lighting score $0-100\%$).
     - Excess Green Index ($2G - R - B$) foliage presence detector (centering score $0-100\%$).
4. **Hardware Optimization**:
   - Custom fullscreen layout designed specifically for the Waveshare 7" Capacitive Touch Display ($1024 \times 600$) and Raspberry Pi 5.

---

### [v2.0.0] — 2026-10-25 14:00:00 IST
#### 📦 Baseline Release
- Initial prototype developed using TensorFlow/Keras MobileNetV2 (`agri_lens_plant_disease_20epoch.keras`).
- Trained on 15 classes from PlantVillage dataset (Pepper, Potato, Tomato).
- Achieved 95.78% validation accuracy on desktop GPU.
- Archived under `MobileV2/` as research baseline.

---

## 📂 Active Production File Manifest (v4.2.0)

```text
EXPISCOR 2026/
├── MobileV4/                               # Production Kiosk Application (v4.2.0)
│   ├── assets/
│   │   └── gundecha_logo.png               # Official Gundecha Education Academy crest
│   ├── agrilens.onnx                       # MobileNetV4 ONNX Model Architecture
│   ├── agrilens.onnx.data                  # MobileNetV4 ONNX Weight Tensors
│   ├── kiosk_config.json                   # Saved Admin Calibration Parameters
│   ├── labels.txt                          # 17-Class Model Labels
│   ├── main.py                             # Touch Kiosk GUI Application
│   ├── requirements.txt                    # Python Dependencies
│   ├── run_agrilens_py313.bat              # Windows Python 3.13 Launcher
│   ├── consolidate_datasets.py             # Dataset Consolidation Pipeline
│   ├── train_mobilenetv4.py                # Local PyTorch MobileNetV4 Trainer
│   ├── Train_AGRILENS_MobileNetV4.ipynb    # 1-Click Google Colab Training Notebook
│   ├── README.md                           # MobileV4 Kiosk Technical Documentation
│   └── REVISION.md                         # MobileV4 Specific Revision Log
│
├── MobileV2/                               # Legacy Baseline Prototype (v2.0.0)
│   ├── dataset/PlantVillage/               # 15-Class PlantVillage Dataset
│   ├── agri_lens_labels.json               # Legacy Labels Mapping
│   ├── run_20_agri_lens.py                 # Fine-tuning Script
│   └── README.md                           # MobileV2 Documentation
│
├── REVISION.md                             # Global Project Revision Log (This file)
├── README.md                               # Global Project README
├── requirements.txt                        # Global Dependencies
├── run_agrilens_py313.bat                  # Root Windows 1-Click Launcher
├── Expiscor 2026.pdf                       # Project Research & Hardware Report
└── waveshare display.pdf                   # 7" Waveshare Hardware Manual
```
