# MobileNetV2 — Plant Disease Classification (95.78% Accuracy)

This folder contains the earlier MobileNetV2 architecture implementation, training scripts, checkpoints, and dataset for AGRILENS.

---

## 📁 Folder Contents

- **`dataset/PlantVillage/`**: 15-class PlantVillage dataset covering:
  - **Pepper bell:** Bacterial Spot, Healthy
  - **Potato:** Early Blight, Late Blight, Healthy
  - **Tomato:** Bacterial Spot, Early Blight, Late Blight, Leaf Mold, Septoria Leaf Spot, Spider Mites (Two-spotted spider mite), Target Spot, Tomato Yellow Leaf Curl Virus (TYLCV), Mosaic Virus, Healthy
- **`agri_lens_labels.json`**: JSON list of the 15 class label mappings.
- **`agri_lens_plant_disease.keras`**: Trained base Keras checkpoint.
- **`agri_lens_plant_disease_20epoch.keras`**: Fine-tuned 20-epoch Keras checkpoint (95.78% validation accuracy).
- **`run_20_agri_lens.py`**: Model fine-tuning and checkpoint training script.

---

## 🚀 Running Training / Fine-tuning

Ensure TensorFlow is installed:
```bash
pip install tensorflow
```

Run the fine-tuning script:
```bash
python run_20_agri_lens.py
```
*(The script automatically resolves the dataset path relative to this directory).*
