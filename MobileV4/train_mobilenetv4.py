"""
AGRILENS - MobileNetV4 Training Pipeline & ONNX Exporter
Architecture: MobileNetV4-Conv-Small (Universal Inverted Bottleneck - UIB)
Classes: 27 Crop & Disease Classes (Apple, Mango, Tomato, Pepper, Potato, Other_Plant)
Author: AGRILENS AI Team
"""

import os
import sys
import time
import argparse
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split
from torchvision import datasets, transforms

try:
    import timm
except ImportError:
    timm = None


def parse_args():
    parser = argparse.ArgumentParser(description="Train MobileNetV4 for AGRILENS")
    parser.add_argument(
        "--data_dir",
        type=str,
        default=str(Path(__file__).parent / "datasets" / "unified_dataset"),
        help="Path to unified dataset root directory",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(Path(__file__).parent / "output"),
        help="Path to save checkpoints and training artifacts",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default="mobilenetv4_conv_small",
        help="timm model architecture name",
    )
    parser.add_argument("--epochs", type=int, default=15, help="Number of training epochs")
    parser.add_argument("--batch_size", type=int, default=32, help="Batch size")
    parser.add_argument("--lr", type=float, default=3e-4, help="Peak learning rate")
    parser.add_argument("--weight_decay", type=float, default=1e-2, help="AdamW weight decay")
    parser.add_argument("--val_split", type=float, default=0.20, help="Validation split fraction")
    parser.add_argument("--num_workers", type=int, default=2, help="DataLoader workers")
    parser.add_argument(
        "--export_onnx",
        action="store_true",
        default=True,
        help="Automatically export best checkpoint to ONNX format",
    )
    return parser.parse_args()


def get_transforms():
    # Standard ImageNet normalization for MobileNetV4
    norm = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])

    train_tf = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.75, 1.0)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
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


def export_to_onnx(model, num_classes, onnx_path, device):
    print(f"\n[ONNX Export] Exporting model to {onnx_path}...")
    model.eval()
    model.to("cpu")

    dummy_input = torch.randn(1, 3, 224, 224, dtype=torch.float32)
    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
    )
    print(f"[ONNX Export] Successfully saved ONNX model ({os.path.getsize(onnx_path) / (1024*1024):.2f} MB)")


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if timm is None:
        raise SystemExit(
            "timm library is not installed! Install via:\n"
            "pip install timm torch torchvision"
        )

    device = torch.device(
        "cuda" if torch.cuda.is_available()
        else ("mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu")
    )
    print(f"=== AGRILENS MobileNetV4 Trainer ===")
    print(f"Target Hardware Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Dataset folder '{data_dir}' not found!\n"
            "Please run 'python consolidate_datasets.py' first to prepare the dataset."
        )

    # Prepare datasets
    train_tf, val_tf = get_transforms()
    full_dataset = datasets.ImageFolder(root=str(data_dir))
    classes = full_dataset.classes
    num_classes = len(classes)
    print(f"Loaded dataset: {len(full_dataset)} total images across {num_classes} classes.")

    # Save labels.txt
    labels_path = output_dir / "labels.txt"
    with open(labels_path, "w", encoding="utf-8") as f:
        for c in classes:
            f.write(f"{c}\n")
    print(f"Saved class labels mapping to: {labels_path}")

    # Train / Val Split
    val_size = int(len(full_dataset) * args.val_split)
    train_size = len(full_dataset) - val_size
    train_subset, val_subset = random_split(
        full_dataset,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(42),
    )

    train_subset.dataset.transform = train_tf
    val_subset.dataset.transform = val_tf

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

    # Initialize MobileNetV4
    print(f"\nInstantiating {args.model_name} with {num_classes} output classes...")
    model = timm.create_model(args.model_name, pretrained=True, num_classes=num_classes)
    model.to(device)

    criterion = nn.CrossEntropyLoss(label_smoothing=0.1)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs, eta_min=1e-6)
    scaler = torch.amp.GradScaler("cuda", enabled=(device.type == "cuda"))

    best_val_acc = 0.0
    best_model_path = output_dir / "best_mobilenetv4.pth"

    print(f"\n--- Starting Training for {args.epochs} Epochs ---")
    for epoch in range(1, args.epochs + 1):
        t0 = time.time()
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0

        for images, targets in train_loader:
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()

            with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                outputs = model(images)
                loss = criterion(outputs, targets)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            running_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()

        scheduler.step()
        train_loss = running_loss / total
        train_acc = 100.0 * correct / total

        # Validation
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0

        with torch.no_grad():
            for images, targets in val_loader:
                images, targets = images.to(device), targets.to(device)
                with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
                    outputs = model(images)
                    loss = criterion(outputs, targets)

                val_loss += loss.item() * images.size(0)
                _, predicted = outputs.max(1)
                val_total += targets.size(0)
                val_correct += predicted.eq(targets).sum().item()

        val_loss = val_loss / val_total
        val_acc = 100.0 * val_correct / val_total
        dt = time.time() - t0

        print(
            f"Epoch [{epoch:02d}/{args.epochs:02d}] ({dt:.1f}s) | "
            f"Train Loss: {train_loss:.4f} Acc: {train_acc:.2f}% | "
            f"Val Loss: {val_loss:.4f} Acc: {val_acc:.2f}%"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "classes": classes,
                "val_acc": val_acc,
            }, best_model_path)
            print(f"  --> Saved new best checkpoint (Val Acc: {best_val_acc:.2f}%)")

    print(f"\nTraining Complete! Best Validation Accuracy: {best_val_acc:.2f}%")

    if args.export_onnx and best_model_path.exists():
        checkpoint = torch.load(best_model_path, map_location="cpu")
        model.load_state_dict(checkpoint["model_state_dict"])
        onnx_dest = output_dir / "agrilens_retrained.onnx"
        export_to_onnx(model, num_classes, str(onnx_dest), device)


if __name__ == "__main__":
    main()
