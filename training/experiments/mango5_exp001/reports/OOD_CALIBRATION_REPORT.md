# OOD and confidence compatibility of the Mango candidate with the kiosk gates

Candidate: `mango5_exp001 / B_partial_ft_s43` (ONNX SHA-256 `a241d91c…e55aba`). Path: the application's own `Classifier.predict` (six views, logit ensemble), imported read-only from `main.py` (`B600D71C…`). Status: investigation. Nothing in the production configuration, labels, model or app was changed. No GitHub publication. No training.

Data used: **train (4,340) and validation (781) images** for the in-distribution side, and the **calibration half** of the OOD sets (755 images) for the false-acceptance side. No test tier and no OOD evaluation half was read. Files: `outputs_train_val_oodcal.csv`, `ood_analysis_results.json`, `ood_logit_sweep.csv`, `figures/`.

## 1. Output distribution of the candidate

| Quantity (kiosk path) | Train | Validation | Validation, correct | Validation, wrong |
|---|---|---|---|---|
| Median maximum logit | 3.17 | 2.89 | 2.90 | 1.49 |
| 5th percentile of maximum logit | 2.31 | 1.69 | 1.74 | 0.67 |
| 1st percentile | 1.73 | 1.06 | 1.22 | 0.39 |
| Median confidence (softmax) | | 0.953 | 0.954 | 0.689 |

- The maximum logit is small on this model (median 2.9, 99th percentile 4.3) and **never reaches 6.0**. The production 24-class model lives on a different logit scale.
- Wrong predictions have clearly lower logits (median 1.5) and confidence (0.69) than correct ones, so both carry error information on the validation images.
- By source the scale varies: ABCGMP median 3.36, MangoLeafBD 2.89, SAR 2.77 (5th percentile 1.55). SAR is the source closest to field conditions, and its logits are the lowest. By class, Healthy (median 2.56) and Gall Midge (2.70) are the lowest, Bacterial Canker the highest (3.22).
- Single view against kiosk path: validation accuracy 98.3% against 98.5%; maximum logits are about 0.15 higher on the kiosk path (it selects the best of eight candidate outputs).

## 2. Effect of the current thresholds (production values, gate code verified)

I checked the vectorised gate against the application's own decision code (`_render_diagnosis` through the Phase A harness): 2,000 comparisons, 0 mismatches.

| Setting | Validation images | Train images | OOD calibration images |
|---|---|---|---|
| `ood_logit` 6.0 (working-tree device profile) | **100% rejected as Unknown** | 100% | 100% rejected |
| `ood_logit` 1.4 (code default) | 2.4% rejected | 0.4% | 36% accepted |
| Confidence 0.40 and margin 0.12 alone | 0.1% rejected | | 1 to 10% rejected |

The 6.0 setting makes the candidate unusable. The code default 1.4 already works acceptably. The low-confidence gate (0.40 and 0.12) rarely fires on this model, because the model is confident on most images, including unsupported ones; the logit gate does almost all the OOD work.

## 3. How well can the gates separate unsupported images? (AUROC, validation against each OOD group, calibration half)

| Score | Other-crop leaves (Apple / Potato / Tomato) | Deferred Mango conditions | Background-only | Sample photographs | Synthetic | All OOD |
|---|---|---|---|---|---|---|
| Maximum logit | 0.97 / 0.98 / 0.95 | 0.83 | 0.92 | 0.97 | 0.995 | **0.936** |
| Confidence | 0.97 / 0.98 / 0.97 | 0.82 | 0.93 | 0.98 | 0.99 | 0.938 |
| Energy (logsumexp) | 0.97 / 0.97 / 0.94 | 0.83 | 0.91 | 0.97 | 1.00 | 0.933 |
| Negative entropy | 0.97 / 0.98 / 0.97 | 0.82 | 0.94 | 0.99 | 1.00 | 0.941 |

All four scores rank in-distribution leaves above unsupported images about equally well (AUROC about 0.94). Switching to another score would not help, and the kiosk only supports the maximum-logit gate in any case. Mango leaves with a condition outside the five classes are the hardest group (0.83), which is expected: they look like leaves.

## 4. Trade-off and recommendation

Selection rule, written before the numbers were seen: choose the largest `ood_logit` whose false rejection of correctly classified **validation** images is at most 2%. Confidence 0.40 and margin 0.12 are kept as in production.

| `ood_logit` | False rejection, correct validation images | Validation wrong predictions rejected | OOD accepted (all groups) | Other-crop leaves accepted (Apple / Potato / Tomato) | Non-leaf accepted (background / photos / synthetic) | Deferred Mango accepted |
|---|---|---|---|---|---|---|
| 1.2 (1% rule) | 0.9% | 25% | 46% | 26% / 35% / 54% | 59% / 52% / 0% | 72% |
| 1.4 (code default) | 1.7% | 50% | 36% | 21% / 23% / 41% | 55% / 30% / 0% | 59% |
| **1.5 (recommended)** | **1.95%** | **50%** | **31%** | **17% / 17% / 37%** | **51% / 14% / 0%** | **53%** |
| 1.7 (5% rule) | 4.4% | 67% | 24% | 13% / 11% / 28% | 44% / 12% / 0% | 43% |
| 6.0 | 100% | 100% | 0% | 0% | 0% | 0% |

**Recommended candidate-specific profile (proposal, not applied anywhere): confidence 0.40, margin 0.12, `ood_logit` 1.5** (`proposed_candidate_gate_profile.json`). 1.5 lies inside the range the application accepts for that setting (1.0 to 6.5).

Justification:
1. It follows the pre-declared rule and rejects half of the wrong validation predictions at a cost of 2% of correct ones.
2. It is close to the code default (1.4), which the application's authors chose; the gain over 1.4 is small (false acceptance 36% to 31%, false rejection 1.7% to 2.0%). The important result is that the device-calibrated 6.0 is wrong for this candidate by a wide margin, not that 1.5 is precise.
3. Larger values cost correct leaves quickly (4.4% at 1.7) and the candidate's Healthy and Gall Midge leaves are already the most exposed.

## 5. What the gate cannot do, and the limits of this evidence

- **It does not solve the OOD problem.** At the recommended point 31% of the unsupported images are still accepted, 51% of background-only windows, and 53% of Mango leaves with an unsupported condition. A logit threshold on a closed five-class model cannot reject "a Mango leaf with another disease". That needs an explicit "other" class or a separate detector, which belongs to the integrated-model plan, not to threshold tuning.
- **False rejection is not uniform.** At 1.5 the false rejection of correct validation images is 4.3% for Healthy and 3.5% for Gall Midge (against 0 to 0.7% for the others), and 2.8% for SAR images (0% for ABCGMP). Field images look more like SAR than ABCGMP, so the real rate may be higher. The threshold should be re-checked on a separate field calibration split, not on the field test set.
- **The unsupported sets are friendly.** Tomato and Potato images are laboratory photographs on plain backgrounds, Apple images come from one field set, the two sample photographs give only 50 crops each, the background windows come from the same sources as the training images, and no leaves of other tree species (guava, jackfruit and so on) were available. The false-acceptance figures are therefore likely to be optimistic for real unsupported leaves.
- **Validation was used twice** (model selection, and now the threshold). With 781 images the 2% target has a wide interval; 1.5 is a point estimate. Per-class and per-source rates above come from small counts.
- **Only the maximum-logit gate was optimised.** Confidence and margin were not tuned.

## 6. Decision needed

Approve or amend the profile for the formal kiosk-path evaluation (`../KIOSK_PATH_EVALUATION_PROTOCOL.md`). Until then nothing is frozen and no test tier has been looked at through the kiosk path. The production configuration is untouched; the 6.0 value in the working-tree `kiosk_config.json` is documented here only as incompatible with this candidate.
