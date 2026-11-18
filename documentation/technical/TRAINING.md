# Dataset, training and evaluation (AGRILENS-MULTICROP 1.0.0)

## Master dataset

`AGL-MULTICROP-MD 1.0.0` is the single authoritative dataset for all four crops. It is stored outside git at
`<AGRILENS_5.0.0>\Model_Trainer_Program\datasets\AGL-MULTICROP-MD\AGL-MULTICROP-MD-1.0.0` (29,982 files listed in `FREEZE_CHECKSUMS.sha256`, freeze-file SHA-256 `12449a5c…5f8c0a`).
Its manifests and card are mirrored in `datasets/master/AGL-MULTICROP-MD/`. AGL-MANGO-MD (v1.0.0 and v1.1.0-rc1) remains the frozen Mango provenance baseline; it is not a second training dataset.

| Tool | Purpose |
|---|---|
| `datasets/dataset_tools/extract_source_archive.py` | Re-extracts a source archive and verifies every file against its SHA-256. |
| `datasets/dataset_tools/build_agl_multicrop_md.py` | Builds the release from the source archives and AGL-MANGO-MD. Refuses to write into a frozen release. |
| `datasets/dataset_tools/freeze_agl_multicrop_md.py` | Writes `FREEZE_CHECKSUMS.sha256`. |
| `datasets/dataset_tools/verify_agl_multicrop_md.py` | Read-only check of checksums, counts, splits, leakage and provenance. |

Training never copies or modifies the dataset. Scripts read `splits/*.csv` and `manifests/*.csv` of the named version, refuse to start if any of them differs from `FREEZE_CHECKSUMS.sha256` (`training/scripts/agl_common.py`), and record the hashes in each run's `run_info.json`. The trainer opens the test split files only to assert that their image ids are disjoint from train; it never loads test images. Decoded images are cached as `.npy` in `<AGRILENS_5.0.0>\Model_Trainer_Program\training_cache\AGL-MULTICROP-MD-1.0.0` (`training/scripts/prepare_cache.py`); the cache is disposable.

Splits are by leaf group, derivative/copy group and split unit, with no group in two splits. `test_heldout_device` holds Mango Anthracnose images from capture devices that do not appear in train or val.

## Training

```bash
python training/configurations/make_configs.py            # writes multicrop1_{R1,R2}_s{42,43}.yaml
python training/scripts/train_integrated.py training/configurations/multicrop1_R1_s42.yaml
python training/scripts/export_onnx.py --checkpoint <run>/best.pt --dataset <dataset> --cache <cache> --out models/candidates/agrilens-multicrop-1.0.0 --prod-labels models/production/agrilens-24class-4.9.4/labels.txt
python training/scripts/report_runs.py --runs <training_runs/agrilens-multicrop-1.0.0> --out training/reports/agrilens-multicrop-1.0.0
```

Training environment: Python with torch, timm, onnx, onnxruntime, pandas, PyYAML, psutil (CPU is sufficient: about 1–2 minutes per epoch of 12,000 samples on a 20-thread desktop CPU).

- Architecture: MobileNetV4-Conv-Small (`timm` `mobilenetv4_conv_small.e2400_r224_in1k`, ImageNet-1k initialisation), 24-class head. This is the production architecture: it runs on the Raspberry Pi 5 with onnxruntime, exports to a 10 MB single-file ONNX, and the export path is proven. No other architecture was tried in 1.0.0.
- One integrated model for all crops is trained from scratch on the master dataset (from ImageNet weights). Weights from 4.9.4 or the Mango candidate are not merged.
- Recipes: R1 trains `blocks.4`, `conv_head`, `norm_head` and the classifier; R2 additionally trains `blocks.3`. Seeds 42 and 43.
- Sampling: class-uniform, then leaf-group-uniform, then image-uniform, 12,000 samples per epoch, so large PlantVillage classes do not dominate.
- Augmentation: rotation ±30°, random resized crop 0.6–1.0, flips, colour jitter, blur, JPEG re-compression.
- Optimiser: AdamW (head 1e-3, backbone 3e-4), weight decay 0.01, label smoothing 0.06, batch 32, up to 15 epochs, early stopping with patience 3 on validation macro-F1, 1-epoch warm-up then cosine.
- Class order is the production `labels.txt` order; `export_onnx.py` refuses any other order.

## Selection and calibration (pre-declared)

`training/configurations/SELECTION_RULE.md` was written before training. Selection uses validation only. Gate calibration (`training/evaluation/calibrate_gates.py`) uses validation images and the calibration half of the unsupported-image set `ood_v2`, through the application's own six-view path, and freezes the thresholds before any test tier is read.

## Release evaluation

`training/evaluation/RELEASE_EVALUATION_CRITERIA.md` (criteria C1–C9) was written before the test tiers were read. `training/evaluation/evaluate_release.py` runs once (lock file `RELEASE_EVALUATION_RUN_ONCE.json`) on `test_known_device`, `test_heldout_device` and the `ood_v2` evaluation half, for the release model and the 4.9.4 model through the release application's code. Tiers are reported separately and never pooled. `--smoke` exercises the code on a few validation images without reading any test tier.

Results: `training/reports/agrilens-multicrop-1.0.0/` and `training/evaluation/release_eval_1.0.0/`.
