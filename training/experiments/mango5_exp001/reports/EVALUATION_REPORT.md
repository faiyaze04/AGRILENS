# AGL-MANGO five-class experiment 001: evaluation report

Dataset AGL-MANGO-MD v1.1.0-rc1 (frozen). Model: mobilenetv4_conv_small.e2400_r224_in1k, ImageNet-pretrained, five outputs. Status: EXPERIMENTAL CANDIDATE, not integrated, not deployed. Production model, labels and thresholds untouched.

## 1. Experiments

| | A: frozen features + new head | B: partial fine-tuning |
|---|---|---|
| Trainable | classifier only (6,405 parameters) | blocks.4, conv_head, norm_head, classifier (1.36 M of 2.50 M) |
| LR | head 1e-3 | head 1e-3, unfrozen backbone 3e-4 |
| Max epochs, patience | 30, 6 | 15, 3 |
| Seeds | 42, 43, 44 | 42, 43, 44 |

Common: AdamW (weight decay 0.01), label smoothing 0.06, batch 32, 4,000 samples per epoch drawn class-uniform then leaf-group-uniform, 1-epoch warm-up then cosine, online augmentation (rotation, random-resized crop, flips, colour jitter, blur, JPEG), resize to shorter side 256 and 224 crop, zero-initialised new head, CPU only. Training data `splits/train.csv` (4,340 images); model selection and early stopping on `splits/val.csv` (781 images). Test tiers were not read until selection was complete.

## 2. Validation results by run

| Run | Best epoch | Val loss | Val accuracy | Val macro-F1 | Train time (min) | s/epoch | CPU cores used | System CPU |
|---|---|---|---|---|---|---|---|---|
| A_frozen_head_s42 | 15 | 0.194 | 96.5% | 0.9671 | 8.0 | 20.0 | 7.0 | 90% |
| A_frozen_head_s43 | 11 | 0.190 | 96.5% | 0.9671 | 6.6 | 20.3 | 6.9 | 89% |
| A_frozen_head_s44 | 20 | 0.187 | 96.7% | 0.9678 | 9.0 | 18.1 | 7.7 | 87% |
| B_partial_ft_s42 | 5 | 0.140 | 97.4% | 0.9762 | 3.9 | 26.5 | 6.0 | 86% |
| B_partial_ft_s43 | 13 | 0.130 | 98.3% | 0.9844 | 6.3 | 22.1 | 6.9 | 87% |
| B_partial_ft_s44 | 12 | 0.136 | 98.2% | 0.9835 | 5.9 | 20.8 | 7.3 | 85% |

| Experiment | Mean val macro-F1 (sd) | Mean val accuracy | Mean val loss | Mean train minutes |
|---|---|---|---|---|
| A_frozen_head | 0.9673 (0.0004) | 96.6% | 0.191 | 7.9 |
| B_partial_ft | 0.9814 (0.0045) | 98.0% | 0.135 | 5.4 |

Pre-declared rule: the experiment with the higher mean validation macro-F1 wins unless the gap is under 0.01. Gap = 0.0141, so **B_partial_ft** is selected; best seed **B_partial_ft_s43** (best epoch 13). Seeds differ by at most 0.01 within an experiment, and B is above A for every seed. Reproducibility check: re-running A seed 42 gave identical per-epoch loss and F1 (to 5 decimals) on the same machine.

### Validation per class (mean over three seeds)

| Class | A recall | A precision | A F1 | B recall | B precision | B F1 |
|---|---|---|---|---|---|---|
| MNG001 Anthracnose | 0.938 | 0.911 | 0.925 | 0.954 | 0.946 | 0.950 |
| MNG002 Bacterial Canker | 1.000 | 0.983 | 0.991 | 1.000 | 1.000 | 1.000 |
| MNG005 Gall Midge (provisional) | 0.947 | 0.962 | 0.954 | 0.974 | 0.976 | 0.975 |
| MNG006 Healthy | 0.960 | 0.983 | 0.971 | 0.977 | 0.994 | 0.986 |
| MNG007 Powdery Mildew | 0.997 | 0.993 | 0.995 | 0.999 | 0.994 | 0.996 |

Validation is not independent of the training sources and devices (its devices also appear in training), so it measures the same thing as the known-device tier.

### Selected model validation confusion matrix (B_partial_ft_s43, rows = true class)

|        |   MNG001 |   MNG002 |   MNG005 |   MNG006 |   MNG007 |
|:-------|---------:|---------:|---------:|---------:|---------:|
| MNG001 |      139 |        0 |        6 |        0 |        1 |
| MNG002 |        0 |       58 |        0 |        0 |        0 |
| MNG005 |        3 |        0 |      229 |        0 |        0 |
| MNG006 |        2 |        0 |        0 |      115 |        0 |
| MNG007 |        0 |        0 |        0 |        1 |      227 |

Validation: accuracy 98.3%, macro-F1 0.9844, 95% interval (leaf groups) accuracy 97.3% to 99.2%.

## 3. Test tiers for the selected model (run once, reported separately)

The two official tiers (known-device and held-out-device) are not pooled. Each answers a different question (see `docs/EVALUATION_TIERS.md` in the dataset). Cross-source figures are exploratory and kept separate.

### Tier 1: known-device evaluation (leaf, burst and augmented-family disjoint; devices seen in training)

Images scored: 574. Accuracy **93.4%** (95% interval 90.6% to 95.6%), macro-F1 **0.934** (0.906 to 0.957); intervals resample leaf groups. Classes scored: MNG001, MNG002, MNG005, MNG006, MNG007.

| Class | Support | Precision | Recall | F1 | Mean confidence when correct | Mean confidence when wrong | Abstain at conf 0.40 or margin 0.12 |
|---|---|---|---|---|---|---|---|
| MNG001 Anthracnose | 145 | 0.914 | 0.959 | 0.936 | 0.886 | 0.594 | 1.4% |
| MNG002 Bacterial Canker | 29 | 0.967 | 1.000 | 0.983 | 0.958 | n/a | 0.0% |
| MNG005 Gall Midge (provisional) | 94 | 0.790 | 0.883 | 0.834 | 0.829 | 0.536 | 7.4% |
| MNG006 Healthy | 137 | 0.984 | 0.876 | 0.927 | 0.858 | 0.464 | 6.6% |
| MNG007 Powdery Mildew | 169 | 1.000 | 0.976 | 0.988 | 0.926 | 0.656 | 0.6% |

Confusion matrix (rows = true class):

|        |   MNG001 |   MNG002 |   MNG005 |   MNG006 |   MNG007 |
|:-------|---------:|---------:|---------:|---------:|---------:|
| MNG001 |      139 |        0 |        6 |        0 |        0 |
| MNG002 |        0 |       29 |        0 |        0 |        0 |
| MNG005 |        8 |        1 |       83 |        2 |        0 |
| MNG006 |        4 |        0 |       13 |      120 |        0 |
| MNG007 |        1 |        0 |        3 |        0 |      165 |

By device (accuracy): samsung SM-G935S 100.0% (n=37); vivo vivo 1906 100.0% (n=29); HUAWEI RNE-L22 92.5% (n=53); samsung SM-G570F 91.3% (n=127); realme realme 5i 93.1% (n=262); unknown 92.4% (n=66)

### Tier 2: held-out-device evaluation (five devices never seen in training; Anthracnose and Gall Midge only)

Images scored: 597. Accuracy **79.4%** (95% interval 75.5% to 83.0%), macro-F1 **0.809** (0.769 to 0.843); intervals resample leaf groups. Classes scored: MNG001, MNG005.

Not evaluable and excluded from the scores (fewer than 100 images or 50 leaf groups): {'MNG007': 4}.

| Class | Support | Precision | Recall | F1 | Mean confidence when correct | Mean confidence when wrong | Abstain at conf 0.40 or margin 0.12 |
|---|---|---|---|---|---|---|---|
| MNG001 Anthracnose | 321 | 0.833 | 0.822 | 0.828 | 0.845 | 0.647 | 5.3% |
| MNG005 Gall Midge (provisional) | 276 | 0.820 | 0.761 | 0.789 | 0.835 | 0.640 | 10.5% |

Confusion matrix (rows = true class):

|        |   MNG001 |   MNG002 |   MNG005 |   MNG006 |   MNG007 |
|:-------|---------:|---------:|---------:|---------:|---------:|
| MNG001 |      264 |        0 |       46 |        4 |        7 |
| MNG002 |        0 |        0 |        0 |        0 |        0 |
| MNG005 |       53 |        0 |      210 |        6 |        7 |
| MNG006 |        0 |        0 |        0 |        0 |        0 |
| MNG007 |        0 |        0 |        0 |        0 |        0 |

By device (accuracy): samsung SM-A525F 82.8% (n=476); vivo V2204 66.1% (n=121)

### Exploratory cross-source diagnostics (NOT official evaluation results of the selected candidate)

These come from two separate throw-away models, each trained on one source with the selected recipe and tested on the other. They were trained on diagnostic manifests, which the instruction of 2026-11-17 on training data excluded; see `CROSS_SOURCE_DIAGNOSTICS_DISCLOSURE.md`. They were run after the selection and the two official test tiers were complete, were not used for selection, and describe different models, not the candidate. Treat them as exploratory only.

**MANGOLEAFBD to SAR25**: images 3757, accuracy 67.1% (60.6% to 72.9%), macro-F1 0.618. Per-class recall: MNG001 0.553; MNG005 0.139; MNG006 0.952; MNG007 0.998.

**SAR25 to MANGOLEAFBD**: images 1974, accuracy 78.0% (75.7% to 80.6%), macro-F1 0.767. Per-class recall: MNG001 0.464; MNG005 0.652; MNG006 1.000; MNG007 0.988.

Bacterial Canker cannot be assessed here (no SAR images, and ABCGMP overlaps MangoLeafBD).

### C270 field validation

No field data yet. No field-accuracy claim is made.

## 4. Training time and hardware

CPU only (20 logical CPUs, torch 10 threads, 8 data-loading workers, no GPU). Peak process memory about 0.8 to 0.9 GB. System CPU use averaged 85 to 90%, and the training process used about 6 to 7.7 cores. A run took 4 to 9 minutes; a first epoch takes about 80 s because of worker start-up. See the table in section 2.

Figures: `figures/loss_curves.png`, `figures/test_known_device_confusion.png`, `figures/test_heldout_device_confusion.png`.
