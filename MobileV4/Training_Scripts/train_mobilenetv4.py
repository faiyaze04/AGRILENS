"""
AGRILENS - MobileNetV4 24-Class Training Pipeline & ONNX Exporter
Architecture: MobileNetV4-Conv-Small (Universal Inverted Bottleneck - UIB)
Single Source of Truth: MobileV4/datasets (4 species folders, 24 classes, 23,893 images)
Author: AGRILENS AI Team
"""

import os
import random
import shutil
import time
import argparse
from collections import defaultdict
from pathlib import Path

import onnx
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import Dataset, DataLoader, Subset
from torchvision import transforms

try:
    import timm
except ImportError:
    timm = None


SPECIES_FOLDERS = [
    ("apple dataset", {
        "rust": "Apple_Rust",
        "scab": "Apple_Scab",
        "healthy": "Apple_healthy",
    }),
    ("mango dataset", {
        "Anthracnose": "Mango_Anthracnose",
        "Bacterial Canker": "Mango_Bacterial_Canker",
        "Cutting Weevil": "Mango_Cutting_Weevil",
        "Die Back": "Mango_Die_Back",
        "Gall Midge": "Mango_Gall_Midge",
        "Healthy": "Mango_Healthy",
        "Powdery Mildew": "Mango_Powdery_Mildew",
        "Sooty Mould": "Mango_Sooty_Mould",
    }),
    ("Potato Dataset", {
        "Potato_Early_blight": "Potato_Early_blight",
        "Potato_Late_blight": "Potato_Late_blight",
        "Potato_healthy": "Potato_healthy",
    }),
    ("Tomato dataset", {
        "Tomato_Bacterial_spot": "Tomato_Bacterial_spot",
        "Tomato_Early_blight": "Tomato_Early_blight",
        "Tomato_Late_blight": "Tomato_Late_blight",
        "Tomato_Leaf_Mold": "Tomato_Leaf_Mold",
        "Tomato_Septoria_leaf_spot": "Tomato_Septoria_leaf_spot",
        "Tomato_Spider_mites_Two_spotted_spider_mite": "Tomato_Spider_mites_Two_spotted_spider_mite",
        "Tomato_Target_Spot": "Tomato_Target_Spot",
        "Tomato_Tomato_YellowLeaf_Curl_Virus": "Tomato_Tomato_YellowLeaf_Curl_Virus",
        "Tomato_Tomato_mosaic_virus": "Tomato_Tomato_mosaic_virus",
        "Tomato_healthy": "Tomato_healthy",
    }),
]


class SpeciesFolderDataset(Dataset):
    """Reads all 24 classes directly from the 4 species folders in MobileV4/datasets."""

    def __init__(self, datasets_root: Path, transform=None):
        self.datasets_root = Path(datasets_root)
        self.transform = transform

        all_labels = []
        for _, cmap in SPECIES_FOLDERS:
            all_labels.extend(cmap.values())
        self.classes = sorted(all_labels)
        self.class_to_idx = {c: i for i, c in enumerate(self.classes)}

        self.samples = []
        for sp_dir, cmap in SPECIES_FOLDERS:
            sp_path = self.datasets_root / sp_dir
            if not sp_path.exists():
                raise FileNotFoundError(f"Missing species folder: {sp_path}")
            for sub_name, label_name in cmap.items():
                sub_path = sp_path / sub_name
                if not sub_path.exists():
                    raise FileNotFoundError(f"Missing class subfolder: {sub_path}")
                target_idx = self.class_to_idx[label_name]
                for f in sorted(sub_path.iterdir()):
                    if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                        self.samples.append((str(f), target_idx))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, target = self.samples[idx]
        with Image.open(img_path) as img:
            img = img.convert("RGB")
        if self.transform is not None:
            img = self.transform(img)
        return img, target


def parse_args():
    parser = argparse.ArgumentParser(description="Train MobileNetV4 for AGRILENS (24 Classes)")
    parser.add_argument(
        "--data_dir",
        type=str,
        default=str(Path(__file__).resolve().parent.parent / "datasets"),
        help="Path to MobileV4/datasets containing the 4 species folders",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(Path(__file__).resolve().parent.parent),
        help="Path to save agrilens.onnx and labels.txt",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="mobilenetv4_conv_small",
        help="timm model architecture name",
    )
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=64, help="Batch size")
    parser.add_argument("--lr", type=float, default=3e-4, help="Peak learning rate")
    parser.add_argument("--weight_decay", type=float, default=1e-2, help="AdamW weight decay")
    parser.add_argument("--val_split", type=float, default=0.20, help="Validation split fraction")
    parser.add_argument("--num_workers", type=int, default=2, help="DataLoader workers")
    return parser.parse_args()


def get_transforms():
    norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.72, 1.0)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.2),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.25, contrast=0.25, saturation=0.25, hue=0.04),
        transforms.ToTensor(),
        norm,
    ])

    val_tf = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        norm,
    ])

    return train_tf, val_tf


def export_single_file_onnx(model, onnx_path: Path):
    print(f"\n[ONNX Export] Exporting single-file ONNX model to {onnx_path}...")
    model.eval()
    model.to("cpu")

    raw_path = onnx_path.with_name("agrilens_raw_tmp.onnx")
    dummy_input = torch.randn(1, 3, 224, 224, dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy_input,
        str(raw_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        dynamo=False,
    )
    proto = onnx.load(str(raw_path), load_external_data=True)
    onnx.save_model(proto, str(onnx_path), save_as_external_data=False)
    for p in [raw_path, Path(str(raw_path) + ".data")]:
        if p.exists():
            p.unlink()
    print(f"[ONNX Export] Saved {onnx_path} ({onnx_path.stat().st_size / (1024*1024):.2f} MB)")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if timm is None:
        raise SystemExit("timm library is required: pip install timm torch torchvision onnx")

    device = torch.device(
        "cuda" if torch.cuda.is_available()
        else ("mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu")
    )
    print("=== AGRILENS MobileNetV4 24-Class Trainer ===")
    print(f"Target Hardware Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    data_dir = Path(args.data_dir)
    train_tf, val_tf = get_transforms()
    base_ds = SpeciesFolderDataset(data_dir, transform=None)
    train_full_ds = SpeciesFolderDataset(data_dir, transform=train_tf)
    val_full_ds = SpeciesFolderDataset(data_dir, transform=val_tf)

    classes = base_ds.classes
    num_classes = len(classes)
    print(f"Loaded dataset: {len(base_ds):,} total images across {num_classes} classes directly from {data_dir}")

    labels_path = output_dir / "labels.txt"
    with open(labels_path, "w", encoding="utf-8") as f:
        for c in classes:
            f.write(f"{c}\n")

    # Stratified 80/20 split per class
    rng = random.Random(42)
    by_class = defaultdict(list)
    for idx, (_, label) in enumerate(base_ds.samples):
        by_class[label].append(idx)

    train_indices, val_indices = [], []
    for label, idxs in sorted(by_class.items()):
        rng.shuffle(idxs)
        n_val = max(1, int(round(args.val_split * len(idxs))))
        val_indices.extend(idxs[:n_val])
        train_indices.extend(idxs[n_val:])

    train_subset = Subset(train_full_ds, train_indices)
    val_subset = Subset(val_full_ds, val_indices)

    train_loader = DataLoader(
        train_subset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
    )
    val_loader = DataLoader(
        val_subset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=(device.type == "cuda"),
    )

    model = timm.create_model(args.model_name, pretrained=True, num_classes=num_classes)
    model.to(device)

    criterion = nn.CrossEntropyLoss(label_smoothing=0.06)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)
    use_amp = device.type == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)

    best_val_acc = 0.0
    best_model_path = output_dir / "best_mobilenetv4.pth"

    print(f"\n--- Starting Training for {args.epochs} Epochs ---")
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        model.train()
        running_loss, correct, total = 0.0, 0, 0

        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()
            with torch.amp.autocast("cuda", enabled=use_amp):
                outputs = model(images)
                loss = criterion(outputs, targets)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            running_loss += loss.item() * images.size(0)
            correct += outputs.argmax(1).eq(targets).sum().item()
            total += targets.size(0)

        scheduler.step()
        train_acc = 100.0 * correct / total

        model.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for images, targets in val_loader:
                images, targets = images.to(device), targets.to(device)
                with torch.amp.autocast("cuda", enabled=use_amp):
                    outputs = model(images)
                val_correct += outputs.argmax(1).eq(targets).sum().item()
                val_total += targets.size(0)

        val_acc = 100.0 * val_correct / val_total
        dt = time.time() - t0
        print(f"Epoch [{epoch:02d}/{args.epochs:02d}] ({dt:.1f}s) | Train Acc: {train_acc:.2f}% | Val Acc: {val_acc:.2f}%")

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), best_model_path)

    print(f"\nTraining Complete! Best Validation Accuracy: {best_val_acc:.2f}%")
    if best_model_path.exists():
        model.load_state_dict(torch.load(best_model_path, map_location="cpu"))
        onnx_dest = output_dir / "agrilens.onnx"
        export_single_file_onnx(model, onnx_dest)
        rpi_dir = output_dir.parent / "AGRILENS_RaspberryPi"
        if rpi_dir.exists():
            shutil.copy2(onnx_dest, rpi_dir / "agrilens.onnx")
            shutil.copy2(labels_path, rpi_dir / "labels.txt")
            print(f"Synced agrilens.onnx & labels.txt -> {rpi_dir}")
        # Update MODEL_SHA256 in main.py so OTA automatically pulls the newly trained model
        import hashlib
        import re
        new_sha = hashlib.sha256(onnx_dest.read_bytes()).hexdigest().lower()
        for main_py in (output_dir / "main.py", rpi_dir / "main.py"):
            if main_py.exists():
                src = main_py.read_text(encoding="utf-8")
                src = re.sub(r'MODEL_SHA256\s*=\s*"[^"]*"', f'MODEL_SHA256 = "{new_sha}"', src)
                main_py.write_text(src, encoding="utf-8")
        print(f"Updated MODEL_SHA256 = {new_sha} in main.py for remote OTA model updates.")


if __name__ == "__main__":
    main()
