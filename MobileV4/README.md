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
- **`labels.txt`**: Class labels.
- **`run_agrilens_py313.bat`**: Windows Python 3.13 one-click launcher.
- **`consolidate_datasets.py`**: Merges all crop datasets into a unified 27-class folder structure.
- **`train_mobilenetv4.py`**: PyTorch MobileNetV4 training pipeline script with automated ONNX export.
- **`Train_AGRILENS_MobileNetV4.ipynb`**: 1-Click Google Colab / Kaggle training notebook (Free T4 GPU, ~15 mins).
- **`datasets/`**: All consolidated project datasets:
  - `apple dataset.zip` (Apple: Rust, Scab, Healthy)
  - `mango dataset.zip` (Mango: 8 disease & healthy classes)
  - `tomato dataset.zip` (Tomato: 10 disease & healthy classes)
  - `PlantVillage/` (Pepper: 2 classes, Potato: 3 classes, Tomato: 10 classes)
  - `plant village data set old/` (Extracted mango reference data)

---

## 🏋️‍♂️ Retraining MobileNetV4 (27 Classes)

### Option 1: 1-Click Google Colab (Recommended — Free GPU, ~15 mins)
1. Open [Google Colab](https://colab.research.google.com).
2. Upload and open [`Train_AGRILENS_MobileNetV4.ipynb`](file:///g:/My%20Drive/EXPISCOR%202026/MobileV4/Train_AGRILENS_MobileNetV4.ipynb).
3. Set runtime to **T4 GPU** (`Runtime -> Change runtime type -> T4 GPU`).
4. Run all cells (`Runtime -> Run all`).
5. The notebook will train on your Google Drive datasets, export the new `agrilens.onnx`, and update `labels.txt`.

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

### Windows:
Double-click `run_agrilens_py313.bat` or run:
```bash
python main.py
```

### Raspberry Pi / Linux:
```bash
python3 main.py
```
