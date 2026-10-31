# MobileNetV4 — Production Edge Vision Kiosk (98.31% Accuracy)

This directory contains the production-grade AGRILENS kiosk application powered by MobileNetV4 ONNX.

---

## 🌟 Overview

- **Vision Backbone:** MobileNetV4 (ONNX format) achieving 98.31% accuracy across 21 crop and disease classes.
- **Inference Speed:** ~24ms on CPU.
- **Hardware Target:** Raspberry Pi 5 (8 GB) or PC with a 7" Touch Display (1024×600) and USB Webcam.

---

## 📁 Folder Contents

- **`main.py`**: Complete GUI Kiosk application (Tkinter + Pillow + OpenCV + ONNX Runtime).
- **`agrilens.onnx`**: MobileNetV4 model architecture in ONNX format.
- **`agrilens.onnx.data`**: Exported ONNX model weight tensors.
- **`labels.txt`**: 21 crop and disease class labels (3 Apple, 8 Mango, 10 Tomato).
- **`run_agrilens_py313.bat`**: Windows Python 3.13 one-click launcher.
- **`requirements.txt`**: Python dependencies.
- **`datasets/`**: Training and validation datasets:
  - `apple dataset.zip` (Apple Rust, Apple Scab, Healthy)
  - `mango dataset.zip` (8 Mango disease/healthy classes)
  - `tomato dataset.zip` (10 Tomato disease/healthy classes)
  - `plant village data set old/` (Extracted mango disease reference data)

---

## 🚀 Running the Application

### Windows:
Double-click `run_agrilens_py313.bat` or run:
```bash
python main.py
```

### Raspberry Pi / Linux:
```bash
python3 main.py
```
