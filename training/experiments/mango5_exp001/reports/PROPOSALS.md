# Ablation proposals for experiment 002 (PREPARED, NOT EXECUTED)

Status: proposals only. No training will start until the error analysis and the C270 field collection have been reviewed and you give a separate go-ahead. The current candidate (`B_partial_ft_s43`) is not touched by either proposal; any run writes to new folders.

Configurations: `ABL1_device_capped_sampling.yaml`, `ABL2_reduced_colour_jitter.yaml`. Sampler draft and preview: `device_capped_sampler_draft.py`, `device_cap_preview.csv`.

## 1. Evidence behind the proposals (from `error_analysis/ERROR_ANALYSIS_REPORT.md`)

- Held-out-device accuracy is 79.4%, against 93.4% on known devices.
- Held-out images are darker and less saturated than the SAR training devices (saturation 0.18 against about 0.26).
- Errors concentrate in sessions, and many show weak neighbour agreement, so part of the gap is label ambiguity that no sampling or augmentation change will fix.
- The experiment-001 sampler draws leaf groups uniformly. That makes the training mix per class depend on how many leaf groups each device has: Healthy draws are 57% from one MangoLeafBD phone (Samsung SM-G935S) and 7% from the SAR realme 5i, although realme 5i contributes 522 of the 1,343 Healthy images. Gall Midge draws are 58% Huawei RNE-L22 (MangoLeafBD).

## 2. Proposal A: device-capped sampling

**Hypothesis.** Capping the share any one device (and so, indirectly, any one source) can supply to a class reduces the model's reliance on device-specific cues and improves performance on unseen devices.

**Change.** The sampler draws class, then a device (probability proportional to min(share, 0.40), re-normalised), then a leaf group inside that class and device, then an image. Nothing else changes: same architecture, partial fine-tuning, augmentations, seeds and epochs. Preview of the resulting draw mix (`device_cap_preview.csv`):
- Healthy: Samsung SM-G935S 57% to 40%, unknown (ABCGMP and SAR) 36% to 40%, realme 5i 7% to 20%.
- Gall Midge: Huawei RNE-L22 58% to 40%, realme 5i 23% to 32%, SM-G570F 18% to 25%.
- Bacterial Canker has two devices, so the cap is infeasible and the mix becomes 50/50.
- Anthracnose and Powdery Mildew change little.

**Expected benefit.** A modest gain in held-out-device and cross-device recall for Healthy and Gall Midge, at a small cost on known-device accuracy for the dominant phones.

**Risks.**
- Devices are tied to sources, sessions and classes here, so a device cap also changes the source mix and cannot separate device from session effects.
- Under-sampling the large device groups discards information from many images, and over-sampling small groups (realme 5i Healthy: 59 leaf groups) invites memorisation of a few leaves.
- It does nothing about label ambiguity, which the error analysis names as the strongest factor for Anthracnose.
- Classes with few devices (Bacterial Canker) get no benefit.

**Variant held back.** Equal device shares per class are not proposed: they over-weight tiny groups (for example 8 "unknown" Anthracnose leaf groups).

## 3. Proposal B: reduced or removed colour jitter

**Hypothesis (two-sided, deliberately).** The current jitter (brightness, contrast and saturation 0.25, hue 0.02) may be hiding the colour and texture cues that separate Anthracnose from Gall Midge (brown spots against dark mottling), so reducing it could improve discrimination. Equally, the held-out devices differ in brightness and saturation, so jitter may be what keeps device colour from becoming a shortcut, and removing it could hurt. The experiment decides; I do not know the direction.

**Variants.** ABL2a: jitter 0.10 and hue 0. ABL2b: no colour jitter. Everything else stays as in the candidate.

**Expected benefit.** If jitter hurts, a few points on Anthracnose and Gall Midge recall on known devices, perhaps on held-out devices too.

**Risks.**
- More reliance on device colour: known-device scores may rise while held-out-device scores fall, which is the pattern this project is trying to avoid.
- A gain on a small, noisy validation set can be chance. Seed spread in experiment 001 was 0.004 to 0.008 macro-F1.
- Dropping jitter does not address the lighting shift. A targeted alternative (matching the held-out brightness and saturation range, or a grey-world normalisation) is not proposed here and would need its own approval.

## 4. Evaluation methodology (shared, pre-registered)

1. **Data.** Same frozen dataset, same train and validation manifests, same recipe as the candidate, seeds 42, 43 and 44. A run is a new experiment folder; the candidate is never overwritten.
2. **Primary comparison without touching any test tier.** Leave-one-device-out cross-validation inside train and validation: hold out one SAR device (SM-G570F, then realme 5i) from training and validation, train, and score on that device's train and validation images. Reported as macro-F1 and per-class recall, mean over folds and seeds. This gives a device-shift signal for choosing between variants. It cannot use the held-out test devices or the cross-source manifests.
3. **Secondary.** Standard validation macro-F1 and loss (as in experiment 001), and the metadata-only shortcut control (class predicted from device, size and month), which must stay far below the image model.
4. **Decision rule.** A variant is preferred over the candidate recipe only if (i) mean leave-one-device-out macro-F1 improves by at least 0.01, (ii) standard validation macro-F1 does not fall by more than 0.005, (iii) no class recall falls by more than 3 points in either, and (iv) the gain is positive in at least two of three seeds. Otherwise the candidate recipe stands.
5. **Test tiers.** After a variant is chosen on the rules above, the known-device and held-out-device tiers are run once for the chosen model only, as in experiment 001, and reported separately and labelled as exploratory against the experiment-001 numbers. They are not used to choose. Cross-source models are not trained.
6. **Field data.** C270 data stays untouched until a model is frozen for field evaluation.
7. **Reporting.** Per-class precision, recall and F1, confusion matrices, confidence and margin of the errors, the error-analysis tables on the same images (so the Anthracnose and Gall Midge confusion can be compared directly), training time and hardware.

## 5. Cost

Each run takes about 4 to 9 minutes on this CPU. Proposal A needs 3 runs plus 6 leave-one-device-out runs, proposal B needs 6 runs plus 12 leave-one-device-out runs, plus the baseline leave-one-device-out folds for the candidate recipe (6 runs): about 33 runs, roughly 4 hours of CPU.

## 6. What would change these proposals

The expert review may change the Anthracnose and Gall Midge labels, and the C270 pilot may show that the kiosk path matters more than either change. Both should be reviewed before anything is run.
