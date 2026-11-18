# Model training, hand-over and evaluation (AGRILENS-MULTICROP 1.0.0)

## The trainer is a separate program

Model training is not part of this repository and never runs on a kiosk. Since 2026-11-18 (CR-0006) the trainer, its run configurations,
the dataset tools and the training experiments live in the separate **Model Trainer Program**:

`<AGRILENS_5.0.0>\Model_Trainer_Program\` (guide: `Model_Trainer_Program\README.md`)

| There | Content |
|---|---|
| `trainer\scripts\` | `train_integrated.py`, `agl_common.py`, `prepare_cache.py`, `export_onnx.py`, `report_runs.py` |
| `trainer\configurations\` | `multicrop1_*.yaml` (paths relative to `Model_Trainer_Program`), `make_configs.py`, `SELECTION_RULE.md`, `kiosk_labels_24class.txt` |
| `trainer\dataset_tools\` | Builders and freeze/verify tools of AGL-MANGO-MD and AGL-MULTICROP-MD |
| `trainer\experiments\`, `trainer\legacy_4.9.4\` | Earlier experiments and the 4.9.4 training code (history) |
| `datasets\`, `training_cache\`, `training_runs\`, `exports\` | Frozen datasets, image cache, training output, ONNX exports |

The trainer has its own Python environment (`Model_Trainer_Program\.venv_train`, pinned in
`trainer\requirements-train-lock.txt`) and needs nothing from this repository. It is its own git repository (code, configurations and records only; datasets, images, caches, checkpoints and environments are excluded by its `.gitignore`); on GitHub it is the private repository https://github.com/faiyaze04/AGRILENS-Model-Trainer. The history of these files up to the move is in this
repository's git history (former folders training/scripts, training/configurations, training/experiments, training/legacy_4.9.4 and
datasets/dataset_tools, removed in CR-0006).

## Master dataset

`AGL-MULTICROP-MD 1.0.0` is the training set of the kiosk model, stored with the trainer at
`<AGRILENS_5.0.0>\Model_Trainer_Program\datasets\AGL-MULTICROP-MD\AGL-MULTICROP-MD-1.0.0` (29,982 files listed in `FREEZE_CHECKSUMS.sha256`,
freeze-file SHA-256 `12449a5c…5f8c0a`). Its manifests and card are mirrored in `datasets/master/AGL-MULTICROP-MD/` here. Splits are by leaf
group, copy group and split unit, with no group in two splits. `test_heldout_device` holds Mango Anthracnose images from phones that do not
appear in train or val.

## Hand-over of a trained model to the kiosk

1. In the trainer: export with a new model version (`export_onnx.py --model-version 1.1.0`). The export checks that the class order equals the
   kiosk's `labels.txt` and that ONNX and PyTorch agree on 256 validation images.
2. Copy the export folder (`agrilens.onnx`, `labels.txt`, `MODEL_MANIFEST.json`) to `models/candidates/<model-id>/` and add an entry to
   `models/manifests/MODEL_REGISTRY.json`. Released model files are never overwritten.
3. Calibrate the rejection gates and run the release evaluation below with the candidate, then decide on a kiosk release. A kiosk only gets
   a new model through a published release (`MODEL_SHA256` in `main.py` and a rebuilt `AGRILENS_RaspberryPi/`).

## Selection and calibration (pre-declared)

`SELECTION_RULE.md` (now in `Model_Trainer_Program\trainer\configurations\`) was written before training; selection uses validation only.
Gate calibration (`training/evaluation/calibrate_gates.py`, in this repository) uses validation images and the calibration half of the
unsupported-image set `ood_v2`, through the application's own six-view path, and freezes the thresholds before any test tier is read.

## Release evaluation

`training/evaluation/RELEASE_EVALUATION_CRITERIA.md` (criteria C1–C9) was written before the test tiers were read.
`training/evaluation/evaluate_release.py` runs once (lock file `RELEASE_EVALUATION_RUN_ONCE.json`) on `test_known_device`,
`test_heldout_device` and the `ood_v2` evaluation half, for the release model and the 4.9.4 model through the release application's code.
Tiers are reported separately and never pooled. `--smoke` exercises the code on a few validation images without reading any test tier.
These scripts stay in this repository because they run the kiosk's `main.py` and because the release tooling reads their frozen results.

Results: `training/reports/agrilens-multicrop-1.0.0/` and `training/evaluation/release_eval_1.0.0/`.
