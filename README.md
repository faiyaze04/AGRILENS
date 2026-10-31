# AGRILENS — AI Plant Health & Disease Diagnosis Kiosk

AGRILENS is an edge AI kiosk system designed for instant, real-time plant disease diagnosis in agricultural environments. Built for deployment on Raspberry Pi 5 touch kiosks and PC workstations, it pairs a fast MobileNetV4 ONNX vision backbone with an on-device Leaf Image Quality assessment pipeline.

---

## 🌟 Key Features

- **High-Accuracy Edge Vision:** Powered by MobileNetV4 ONNX (98.31% accuracy across 21 crop and disease classes) with ~24ms inference speed on CPU.
- **Leaf Quality AI Validator:** Real-time pre-inference analysis:
  - **Focus & Motion Blur Detection:** 5-point discrete spatial Laplacian variance.
  - **Lighting & Exposure Check:** Luminance distribution and specular glare detection.
  - **Foliage Presence Validation:** Excess Green Index ($2G - R - B$) across target alignment ROI.
- **Dedicated Capture / Diagnose Workflow:** Touch-optimized UI with separate `[CAPTURE]` / `[RETAKE]` and `[DIAGNOSE]` actions.
- **Plant Filtering & Auto Mode:** Auto detection mode with crop filtering (Apple, Mango, Tomato) to narrow diagnosis scope.
- **Integrated Extension Recommendations:** Farmer-ready cultural and chemical management guidance for identified crop conditions.
- **Admin Control Panel:** PIN-protected admin interface with USB camera re-detection and safe system shutdown.

---

## 🖥️ Target Hardware

- **Platform:** Raspberry Pi 5 (8 GB) or Windows/Linux PC
- **Display:** 7" Capacitive Touch Display (1024×600 resolution)
- **Camera:** Standard USB UVC Webcam (640×480 @ 25 FPS)
- **Runtime:** Python 3.10 – 3.13+

---

## 📦 Supported Crops & Disease Classes

The model diagnoses 21 conditions across 3 primary crops:

| Crop | Supported Conditions |
| :--- | :--- |
| **Apple** | Apple Rust, Apple Scab, Healthy |
| **Mango** | Anthracnose, Bacterial Canker, Cutting Weevil, Die Back, Gall Midge, Powdery Mildew, Sooty Mould, Healthy |
| **Tomato** | Bacterial Spot, Early Blight, Late Blight, Leaf Mold, Septoria Leaf Spot, Spider Mites (Two-spotted), Target Spot, Yellow Leaf Curl Virus (TYLCV), Mosaic Virus, Healthy |

---

## 📁 Repository Structure

```text
AGRILENS/
├── MobileV2/                         # MobileNetV2 architecture & training baseline
│   ├── dataset/PlantVillage/         # 15-class PlantVillage dataset (Pepper, Potato, Tomato)
│   ├── agri_lens_labels.json         # 15-class label mappings
│   ├── agri_lens_plant_disease.keras # Trained MobileNetV2 base checkpoint
│   ├── agri_lens_plant_disease_20epoch.keras # 20-epoch checkpoint (95.78% accuracy)
│   ├── run_20_agri_lens.py           # Training & fine-tuning pipeline
│   └── README.md
│
├── MobileV4/                         # MobileNetV4 production edge kiosk application
│   ├── agrilens.onnx                 # MobileNetV4 ONNX model graph
│   ├── agrilens.onnx.data            # Model weight tensors
│   ├── labels.txt                    # 21-class labels (Apple, Mango, Tomato)
│   ├── main.py                       # Touch kiosk GUI application
│   ├── run_agrilens_py313.bat        # Direct Windows batch launcher
│   ├── requirements.txt              # Standalone requirements
│   ├── datasets/                     # Training & reference datasets
│   │   ├── apple dataset.zip
│   │   ├── mango dataset.zip
│   │   ├── tomato dataset.zip
│   │   └── plant village data set old/
│   └── README.md
│
├── Expiscor 2026.pdf                 # Project research & presentation documentation
├── waveshare display.pdf             # 7" Waveshare display hardware manual
├── requirements.txt                  # Workspace-wide dependencies
├── run_agrilens_py313.bat            # Root launcher (runs MobileV4/main.py)
└── README.md
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

- **Windows:** Double-click `run_agrilens_py313.bat` in the root folder (or inside `MobileV4/`), or run:
  ```bash
  cd MobileV4
  python main.py
  ```
- **Raspberry Pi / Linux:**
  ```bash
  cd MobileV4
  python3 main.py
  ```

---

## 🔒 Admin Access

The Admin panel can be accessed via the **`[ADMIN]`** button in the top-right corner.
- **Default System PIN:** `AGRILENS`
- **Admin Capabilities:**
  - Detect and reconnect USB webcams on the fly.
  - Safely close the kiosk application and exit to the desktop.

---

## 📄 License & Disclaimer

*Agricultural advice provided by this software is for advisory guidance only. Always consult local agricultural extension officers before applying chemical treatments.*
