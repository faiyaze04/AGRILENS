"""
AGRILENS - Dataset Consolidation & Verification Script
Single Source of Truth: MobileV4/datasets
Species Folders:
- apple dataset: Rust, Scab, Healthy (3 classes)
- mango dataset: Anthracnose, Bacterial Canker, Cutting Weevil, Die Back, Gall Midge, Healthy, Powdery Mildew, Sooty Mould (8 classes)
- Potato Dataset: Early Blight, Late Blight, Healthy (3 classes)
- Tomato dataset: Bacterial Spot, Early Blight, Late Blight, Leaf Mold, Septoria, Spider Mites, Target Spot, TYLCV, Mosaic Virus, Healthy (10 classes)
Total: 24 Classes (23,893 images) — Strictly from MobileV4/datasets (no external PlantVillage or synthetic sources).
"""

import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATASETS_DIR = BASE_DIR / "datasets"
OUTPUT_DIR = DATASETS_DIR / "unified_dataset"

# Map of (Species Parent Folder, Subfolder) -> Standardized Single-Underscore Class Name
SPECIES_CLASS_MAP = [
    ("apple dataset", "rust", "Apple_Rust"),
    ("apple dataset", "scab", "Apple_Scab"),
    ("apple dataset", "healthy", "Apple_healthy"),
    ("mango dataset", "Anthracnose", "Mango_Anthracnose"),
    ("mango dataset", "Bacterial Canker", "Mango_Bacterial_Canker"),
    ("mango dataset", "Cutting Weevil", "Mango_Cutting_Weevil"),
    ("mango dataset", "Die Back", "Mango_Die_Back"),
    ("mango dataset", "Gall Midge", "Mango_Gall_Midge"),
    ("mango dataset", "Healthy", "Mango_Healthy"),
    ("mango dataset", "Powdery Mildew", "Mango_Powdery_Mildew"),
    ("mango dataset", "Sooty Mould", "Mango_Sooty_Mould"),
    ("Potato Dataset", "Potato_Early_blight", "Potato_Early_blight"),
    ("Potato Dataset", "Potato_Late_blight", "Potato_Late_blight"),
    ("Potato Dataset", "Potato_healthy", "Potato_healthy"),
    ("Tomato dataset", "Tomato_Bacterial_spot", "Tomato_Bacterial_spot"),
    ("Tomato dataset", "Tomato_Early_blight", "Tomato_Early_blight"),
    ("Tomato dataset", "Tomato_Late_blight", "Tomato_Late_blight"),
    ("Tomato dataset", "Tomato_Leaf_Mold", "Tomato_Leaf_Mold"),
    ("Tomato dataset", "Tomato_Septoria_leaf_spot", "Tomato_Septoria_leaf_spot"),
    ("Tomato dataset", "Tomato_Spider_mites_Two_spotted_spider_mite", "Tomato_Spider_mites_Two_spotted_spider_mite"),
    ("Tomato dataset", "Tomato_Target_Spot", "Tomato_Target_Spot"),
    ("Tomato dataset", "Tomato_Tomato_YellowLeaf_Curl_Virus", "Tomato_Tomato_YellowLeaf_Curl_Virus"),
    ("Tomato dataset", "Tomato_Tomato_mosaic_virus", "Tomato_Tomato_mosaic_virus"),
    ("Tomato dataset", "Tomato_healthy", "Tomato_healthy"),
]

TARGET_CLASSES = [cls_name for _, _, cls_name in SPECIES_CLASS_MAP]


def main(copy_to_unified=False):
    print(f"=== AGRILENS Single Source of Truth Dataset Check ({DATASETS_DIR}) ===")
    total_imgs = 0
    for species_folder, subfolder, cls_name in SPECIES_CLASS_MAP:
        src_dir = DATASETS_DIR / species_folder / subfolder
        if not src_dir.exists():
            print(f"  [MISSING] {species_folder}/{subfolder}")
            continue
        imgs = [f for f in src_dir.iterdir() if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png")]
        total_imgs += len(imgs)
        print(f"  {species_folder:16s} / {subfolder:44s} -> {cls_name:44s}: {len(imgs):5d} images")

        if copy_to_unified:
            dst_dir = OUTPUT_DIR / cls_name
            dst_dir.mkdir(parents=True, exist_ok=True)
            for img_file in imgs:
                dest = dst_dir / img_file.name
                if not dest.exists():
                    shutil.copy2(img_file, dest)

    print(f"\nTotal verified dataset size: {total_imgs} images across {len(TARGET_CLASSES)} classes (4 species folders).")


if __name__ == "__main__":
    main()
