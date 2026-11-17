#!/usr/bin/env python3
"""Write the YAML configuration of every run. Edit here, regenerate, commit the output with the results (configs are copied into each run folder)."""
import os, yaml
EXP = r"D:\AGRILENS_Training\AGL-MANGO-MD\experiments\mango5_exp001"


def base(run_id, mode, seed):
    return {
        "run_id": run_id, "mode": mode, "seed": seed, "experiment": "mango5-exp001",
        "authorisation": {"training_authorised": True, "authorised_by": "user", "authorised_on": "2026-11-17",
                          "scope": "controlled five-class experimental training; no production change, no deployment"},
        "dataset": {"id": "AGL-MANGO-MD", "version": "v1.1.0-rc1", "root": r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.1.0-rc1"},
        "model": {"name": "mobilenetv4_conv_small.e2400_r224_in1k", "pretrained": "ImageNet (timm)", "num_classes": 5,
                  "classes": ["MNG001_ANTHRACNOSE", "MNG002_BACTERIAL_CANKER", "MNG005_GALL_MIDGE (provisional)", "MNG006_HEALTHY", "MNG007_POWDERY_MILDEW"]},
        "data": {"train_manifest": "splits/train.csv", "val_manifest": "splits/val.csv"},
        "input": {"resize": "shorter side 256 (cached once), eval: centre crop 224; train: random-resized crop 224", "normalise": "ImageNet mean/std"},
        "sampling": {"unit": "class uniform -> leaf group uniform -> image uniform", "samples_per_epoch": 4000},
        "augmentation": {"rotation_degrees": 30, "crop_scale": [0.6, 1.0], "colour_jitter": {"brightness": 0.25, "contrast": 0.25, "saturation": 0.25, "hue": 0.02},
                         "blur_p": 0.2, "jpeg_p": 0.3, "jpeg_quality": [60, 95], "flips": "horizontal and vertical"},
        "optim": {"optimiser": "AdamW", "weight_decay": 0.01, "label_smoothing": 0.06, "batch_size": 32, "schedule": "1 epoch warm-up, cosine to 0 over epochs_max"},
        "compute": {"torch_threads": 10, "workers": 8},
        "selection": {"monitor": "val_macro_f1 (ties: lower val_loss)", "test_tiers_used": False},
    }


for seed in (42, 43, 44):
    a = base(f"A_frozen_head_s{seed}", "A_frozen_head", seed)
    a["optim"].update(lr_head=1e-3, lr_backbone=0.0, epochs_max=30, patience=6)
    a["trainable"] = "classifier only (6,405 parameters); backbone, conv_head and norm_head frozen, BatchNorm in eval mode"
    b = base(f"B_partial_ft_s{seed}", "B_partial_ft", seed)
    b["optim"].update(lr_head=1e-3, lr_backbone=3e-4, epochs_max=15, patience=3)
    b["trainable"] = "blocks.4, conv_head, norm_head, classifier; stem and blocks 0-3 frozen (BatchNorm eval)"
    for c in (a, b): yaml.safe_dump(c, open(os.path.join(EXP, "configs", c["run_id"] + ".yaml"), "w"), sort_keys=False)
print(sorted(os.listdir(os.path.join(EXP, "configs"))))
