# MobileNetV4 — Production Edge Vision Kiosk (v4.2.0)

This directory contains the production-grade **AGRILENS** kiosk application powered by MobileNetV4 ONNX.

---

## 📌 Build Information

| Detail | Specification |
| :--- | :--- |
| **Application Version** | **`v4.2.0` (Production Release)** |
| **Last Build Date & Time** | **`2026-11-01 07:12:32 IST` (November 1, 2026)** |
| **Vision Backbone** | MobileNetV4 Universal Inverted Bottleneck (UIB) in ONNX format |
| **Model Size** | ~10 MB (`agrilens.onnx` + `agrilens.onnx.data`) |
| **Inference Latency** | ~24 ms on CPU (Raspberry Pi 5 & Windows PC) |
| **Hardware Target** | Raspberry Pi 5 (8 GB) or PC with 7" Touch Display (1024×600) and USB Webcam |
| **Institutional Partner** | Gundecha Education Academy ([gundechaedu.org](https://www.gundechaedu.org/)) |
| **Full Version History** | See [`REVISION.md`](file:///g:/My%20Drive/EXPISCOR%202026/MobileV4/REVISION.md) |

---

## 🌟 Key Capabilities in v4.2.0

- **Intuitive Dark Foliage Theme**: High-contrast, dark agricultural interface (`#08100a`, `#0e1a12`, `#15261a`) with crisp pure white text (`#ffffff`, `#f8fafc`), lush emerald green accents (`#16a34a`, `#22c55e`), and high-visibility alert reds (`#ef4444`).
- **High-Fidelity Rounded Pill Buttons (`RoundedButton`)**: Custom anti-aliased Tkinter canvas component with 3x supersampling, Pillow Lanczos downscaling, active hover/pressed dynamic state feedback, and parent alpha blending.
- **Official Gundecha Education Academy Crest**: Integrated official school logo on top-right header with interactive web portal redirection and institution tooltip.
- **Admin Calibration Sliders & Mouse-over `(i)` Tooltips**: PIN-protected Admin panel with real-time sliders for Confidence Threshold ($30\% - 95\%$), OOD Margin ($0.10 - 0.80$), OOD Logit Gate ($1.0 - 10.0$), and Leaf Sharpness Focus ($10 - 150$), each accompanied by interactive information tooltips.
- **Persistent Kiosk Settings (`kiosk_config.json`)**: Live parameter adjustments are automatically saved and restored across reboots.
- **Leaf Quality AI Validator**: Real-time pre-inference analysis:
  - **Focus & Motion Blur:** 5-point discrete spatial Laplacian variance ($0-100\%$).
  - **Lighting & Exposure:** Luminance distribution and specular glare check ($0-100\%$).
  - **Foliage Presence:** Excess Green Index ($2G - R - B$) across target alignment ROI ($0-100\%$).
- **Out-of-Distribution (OOD) Protection**: Dual-stage post-processing logic (Softmax margin and unnormalized logit gating) coupled with the `Other_Plant_or_Background` 17th class to reject non-leaf imagery, fingers, and desk surfaces.

---

## 📦 Supported Crops & Diagnostic Classes (17 Classes)

The production model diagnoses 16 crop conditions across 4 major crops plus 1 negative Out-of-Distribution class:

| Crop / Category | Supported Diagnostic Classes |
| :--- | :--- |
| **Apple** | Apple Rust, Apple Scab, Healthy |
| **Mango** | Anthracnose, Bacterial Canker, Cutting Weevil, Die Back, Gall Midge, Powdery Mildew, Sooty Mould, Healthy |
| **Pepper** | Bacterial Spot, Healthy |
| **Potato** | Early Blight, Late Blight, Healthy |
| **Out-of-Distribution** | `Other_Plant_or_Background` *(automatically triggers OOD advisory guidance)* |

---

## 📁 Active File Manifest

```text
MobileV4/
├── assets/
│   └── gundecha_logo.png               # Official Gundecha Education Academy crest
├── agrilens.onnx                       # MobileNetV4 model architecture graph (~10MB)
├── agrilens.onnx.data                  # Exported ONNX model weight tensors
├── kiosk_config.json                   # Persisted Admin calibration parameters
├── labels.txt                          # 17-class model labels
├── main.py                             # Complete Touch Kiosk GUI application
├── requirements.txt                    # Standalone dependencies
├── run_agrilens_py313.bat              # Windows Python 3.13 one-click launcher
├── consolidate_datasets.py             # Dataset consolidation script for 4 crops
├── train_mobilenetv4.py                # Local PyTorch MobileNetV4 training script
├── Train_AGRILENS_MobileNetV4.ipynb    # 1-Click Google Colab / Kaggle training notebook (Free T4 GPU, ~15 mins)
├── README.md                           # This technical documentation
└── REVISION.md                         # Detailed version changelog and build log
```

---

## 🏋️‍♂️ Retraining MobileNetV4 (17 Classes)

### Option 1: 1-Click Google Colab (Recommended — Free GPU, ~15 mins)
1. Open [Google Colab](https://colab.research.google.com).
2. Upload and open [`Train_AGRILENS_MobileNetV4.ipynb`](file:///g:/My%20Drive/EXPISCOR%202026/MobileV4/Train_AGRILENS_MobileNetV4.ipynb).
3. Set runtime to **T4 GPU** (`Runtime -> Change runtime type -> T4 GPU`).
4. Run all cells (`Runtime -> Run all`).
5. The notebook mounts Google Drive, trains on the consolidated datasets, exports the new `agrilens.onnx`, and updates `labels.txt`.

### Option 2: Local Machine Training
1. Consolidate all datasets into the unified structure:
   ```bash
   python consolidate_datasets.py
   ```
2. Run the training script:
   ```bash
   python train_mobilenetv4.py --epochs 15 --batch_size 32
   ```

---

## 🚀 Running the Application

### Windows (Python 3.13+):
Double-click [`run_agrilens_py313.bat`](file:///g:/My%20Drive/EXPISCOR%202026/MobileV4/run_agrilens_py313.bat) or run:
```bash
python main.py
```

### Raspberry Pi 5 / Linux:
```bash
python3 main.py
```

---

## 🔒 Admin Access & Calibration

Access the Admin console by clicking the **`ADMIN`** button in the top-right header:
- **Default PIN:** `AGRILENS`
- **Capabilities:**
  - Adjust Confidence, OOD Margin, OOD Logit, and Leaf Sharpness thresholds using real-time sliders.
  - Hover over the `(i)` icons to view detailed parameter explanations.
  - Scan and hot-plug USB webcams on the fly.
  - Safely shut down the kiosk application.
