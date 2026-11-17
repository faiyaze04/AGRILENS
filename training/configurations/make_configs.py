"""Generate the YAML configurations of the AGRILENS-MULTICROP 1.0.0 training runs (R1, R2 x seeds 42, 43). Run once; configs are committed with the results."""
import os, yaml
HERE = os.path.dirname(os.path.abspath(__file__))
for recipe in ("R1_last_stage", "R2_last_two_stages"):
    for seed in (42, 43):
        c = {"run_id": f"multicrop1_{recipe.split('_')[0]}_s{seed}", "recipe": recipe, "seed": seed, "model": "mobilenetv4_conv_small.e2400_r224_in1k (ImageNet-1k, timm)", "num_classes": 24,
             "dataset": {"id": "AGL-MULTICROP-MD", "version": "1.0.0", "root": r"D:\AGRILENS_Training\datasets\AGL-MULTICROP-MD\AGL-MULTICROP-MD-1.0.0"},
             "cache": r"D:\AGRILENS_Training\training_cache\AGL-MULTICROP-MD-1.0.0", "output_dir": r"D:\AGRILENS_Training\training_runs\agrilens-multicrop-1.0.0",
             "data": {"train": "splits/train.csv", "validation": "splits/val.csv (selection and early stopping only)", "never_read": ["splits/test_known_device.csv", "splits/test_heldout_device.csv"]},
             "sampling": {"rule": "class uniform -> leaf group uniform -> image uniform", "samples_per_epoch": 12000},
             "augmentation": {"rotation_degrees": 30, "crop_scale": [0.6, 1.0], "colour_jitter": {"brightness": 0.25, "contrast": 0.25, "saturation": 0.25, "hue": 0.02}, "blur_p": 0.2, "jpeg_p": 0.3, "jpeg_quality": [60, 95]},
             "optim": {"optimiser": "AdamW", "lr_head": 1.0e-3, "lr_backbone": 3.0e-4, "weight_decay": 0.01, "label_smoothing": 0.06, "batch_size": 32, "epochs_max": 15, "patience": 3, "schedule": "1-epoch warm-up, cosine"},
             "compute": {"torch_threads": 10, "workers": 8}}
        yaml.safe_dump(c, open(os.path.join(HERE, c["run_id"] + ".yaml"), "w"), sort_keys=False)
print(sorted(f for f in os.listdir(HERE) if f.endswith(".yaml")))
