"""
AGRILENS - Unified Dataset Consolidation Script
Consolidates all crop datasets into a unified 27-class structure for MobileNetV4:
- Apple: Rust, Scab, Healthy (3 classes)
- Mango: 8 conditions (Anthracnose, Bacterial Canker, Cutting Weevil, Die Back, Gall Midge, Healthy, Powdery Mildew, Sooty Mould)
- Tomato: 10 conditions (Bacterial Spot, Early/Late Blight, Leaf Mold, Septoria, Spider Mites, Target Spot, TYLCV, Mosaic, Healthy)
- Pepper: Bacterial Spot, Healthy (2 classes)
- Potato: Early Blight, Late Blight, Healthy (3 classes)
- Other_Plant_or_Background: Negative class (Money Plant, non-target flora, background) (1 class)
Total: 27 Classes
"""

import os
import shutil
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATASETS_DIR = BASE_DIR / "datasets"
OUTPUT_DIR = DATASETS_DIR / "unified_dataset"

# 27 Target Class Names
TARGET_CLASSES = [
    "Apple___Rust",
    "Apple___Scab",
    "Apple___healthy",
    "Mango___Anthracnose",
    "Mango___Bacterial_Canker",
    "Mango___Cutting_Weevil",
    "Mango___Die_Back",
    "Mango___Gall_Midge",
    "Mango___Healthy",
    "Mango___Powdery_Mildew",
    "Mango___Sooty_Mould",
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites_Two-spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___healthy",
    "Pepper___Bacterial_spot",
    "Pepper___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Other_Plant_or_Background",
]


def extract_apple(zip_path, output_dir):
    print("Extracting Apple dataset...")
    class_map = {
        "rust": "Apple___Rust",
        "scab": "Apple___Scab",
        "healthy": "Apple___healthy",
    }
    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            if member.endswith((".jpg", ".jpeg", ".png", ".JPG", ".PNG")):
                parts = member.split("/")
                for p in parts:
                    clean_p = p.lower().strip()
                    if clean_p in class_map:
                        target_class = class_map[clean_p]
                        dest = output_dir / target_class / Path(member).name
                        if not dest.exists():
                            with z.open(member) as src, open(dest, "wb") as dst:
                                dst.write(src.read())
                        break


def extract_mango(zip_path, output_dir):
    print("Extracting Mango dataset...")
    class_map = {
        "anthracnose": "Mango___Anthracnose",
        "bacterial canker": "Mango___Bacterial_Canker",
        "cutting weevil": "Mango___Cutting_Weevil",
        "die back": "Mango___Die_Back",
        "gall midge": "Mango___Gall_Midge",
        "healthy": "Mango___Healthy",
        "powdery mildew": "Mango___Powdery_Mildew",
        "sooty mould": "Mango___Sooty_Mould",
    }
    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            if member.endswith((".jpg", ".jpeg", ".png", ".JPG", ".PNG")):
                parts = member.split("/")
                top_folder = parts[0].lower().strip()
                if top_folder in class_map:
                    target_class = class_map[top_folder]
                    dest = output_dir / target_class / Path(member).name
                    if not dest.exists():
                        with z.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())


def extract_tomato(zip_path, output_dir):
    print("Extracting Tomato dataset...")
    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            if member.endswith((".jpg", ".jpeg", ".png", ".JPG", ".PNG")):
                parts = member.split("/")
                for p in parts:
                    if "tomato" in p.lower():
                        clean = p.replace(" ", "_").strip()
                        # Normalize class naming
                        target_class = None
                        for tc in TARGET_CLASSES:
                            if tc.startswith("Tomato___") and clean.lower() in tc.lower():
                                target_class = tc
                                break
                        if target_class is None and "tomato" in clean.lower():
                            target_class = clean if clean.startswith("Tomato___") else f"Tomato___{clean}"
                        if target_class and (output_dir / target_class).exists():
                            dest = output_dir / target_class / Path(member).name
                            if not dest.exists():
                                with z.open(member) as src, open(dest, "wb") as dst:
                                    dst.write(src.read())
                        break


def copy_plantvillage_pepper_potato(pv_dir, output_dir):
    print("Copying Pepper and Potato classes from PlantVillage...")
    pv_map = {
        "Pepper__bell___Bacterial_spot": "Pepper___Bacterial_spot",
        "Pepper__bell___healthy": "Pepper___healthy",
        "Potato___Early_blight": "Potato___Early_blight",
        "Potato___Late_blight": "Potato___Late_blight",
        "Potato___healthy": "Potato___healthy",
    }
    for src_name, dst_name in pv_map.items():
        src_folder = pv_dir / src_name
        dst_folder = output_dir / dst_name
        if src_folder.exists():
            for f in src_folder.glob("*.*"):
                if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    dest = dst_folder / f.name
                    if not dest.exists():
                        shutil.copy2(f, dest)


def setup_negative_class(output_dir):
    other_dir = output_dir / "Other_Plant_or_Background"
    other_dir.mkdir(parents=True, exist_ok=True)
    readme = other_dir / "README.txt"
    with open(readme, "w", encoding="utf-8") as f:
        f.write(
            "This folder contains negative / out-of-distribution training samples:\n"
            "- Money Plant (Epipremnum aureum)\n"
            "- Ornamental houseplants, ficus, ferns, and garden weeds\n"
            "- Background textures, soil, hands, and kiosk environment shots\n"
            "Drop photos of non-target leaves here so MobileNetV4 learns to reject them!\n"
        )


def main():
    print(f"Creating unified dataset directory at: {OUTPUT_DIR}")
    for c in TARGET_CLASSES:
        (OUTPUT_DIR / c).mkdir(parents=True, exist_ok=True)

    apple_zip = DATASETS_DIR / "apple dataset.zip"
    if apple_zip.exists():
        extract_apple(apple_zip, OUTPUT_DIR)

    mango_zip = DATASETS_DIR / "mango dataset.zip"
    if mango_zip.exists():
        extract_mango(mango_zip, OUTPUT_DIR)

    tomato_zip = DATASETS_DIR / "tomato dataset.zip"
    if tomato_zip.exists():
        extract_tomato(tomato_zip, OUTPUT_DIR)

    pv_dir = DATASETS_DIR / "PlantVillage"
    if not pv_dir.exists():
        pv_dir = BASE_DIR.parent / "MobileV2" / "dataset" / "PlantVillage"
    if pv_dir.exists():
        copy_plantvillage_pepper_potato(pv_dir, OUTPUT_DIR)

    setup_negative_class(OUTPUT_DIR)

    print("\n--- Summary of Consolidated Classes ---")
    total_imgs = 0
    for c in sorted(TARGET_CLASSES):
        p = OUTPUT_DIR / c
        cnt = len(list(p.glob("*.*")))
        total_imgs += cnt
        print(f"  {c:45}: {cnt:5d} images")
    print(f"\nTotal dataset size: {total_imgs} images across {len(TARGET_CLASSES)} classes.")


if __name__ == "__main__":
    main()
