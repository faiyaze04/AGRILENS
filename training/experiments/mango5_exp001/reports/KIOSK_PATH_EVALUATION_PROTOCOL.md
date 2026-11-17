# Formal kiosk-path evaluation protocol (DRAFT FOR APPROVAL)

Status: **not approved, not run.** No frozen test image has been passed through the kiosk path. The evaluation runs once, after you approve this protocol. It is recorded as a **secondary kiosk-path evaluation**; the original single-view results of the frozen test tiers remain the primary record and are not changed.

## 1. Purpose
Establish how the candidate behaves through the application's real inference and decision code (six views, logit ensemble, rejection gates), and separate classification errors from rejections, using the frozen test tiers and an independent unsupported-image set.

## 2. What is frozen (hash-checked at run time; the run refuses if any differs)
| Item | Frozen as |
|---|---|
| Candidate | ONNX SHA-256 `a241d91c8b06352f3185343dd0371680e4c4f6c6c1257b151dc3c9d775e55aba` |
| Preprocessing and inference implementation | the application's own `main.py` (`Classifier.predict`, `_enhance_mobile_screen`, `_prep_val_crop`, `_prep_tensor`, `_render_diagnosis`), imported unchanged: SHA-256 `b600d71c…deb`; the Phase A harness copy and `kiosk_clf.py` |
| Labels | experiment-only labels file `mango5_labels_kiosk_format.txt`, same class order as training |
| Calibration parameters | `ood/proposed_candidate_gate_profile.json`: confidence 0.40, margin 0.12, `ood_logit` 1.5, chosen on validation data and the OOD calibration half only |
| Acceptance criteria | `kiosk_eval/acceptance_criteria_PROPOSED.json` (section 5) |
| Test data | `splits/test_known_device.csv`, `splits/test_heldout_device.csv` of the frozen dataset (checked against `FREEZE_CHECKSUMS.sha256`) |
| OOD evaluation data | the evaluation half of `ood/ood_sets_manifest.csv` (755 images), fingerprint `OOD_EVALUATION_SET_FROZEN.sha256`; never scored before this run |
| Evaluation code | `kiosk_eval/formal_kiosk_eval.py` |
| Environment | recorded in the output (Python, onnxruntime, cv2, Pillow, numpy versions) |

Approval mechanism: after you approve, I write `kiosk_eval/PROTOCOL_APPROVED.json` containing these hashes. The script refuses to run in `test` mode without it, if any hash differs, or if the run-once lock file exists.

## 3. Data and inputs
- **Known-device tier:** 574 images (five classes). **Held-out-device tier:** the 597 images of the two evaluable classes (Anthracnose, Gall Midge); the 4 Powdery Mildew images stay excluded, as in the original evaluation.
- **OOD evaluation half:** Apple, Potato and Tomato leaves (450 images), non-leaf images (155: synthetic, two sample photographs, background-only windows), and Mango leaves with unsupported conditions (150, informational).
- **Input form:** the cached full image resized to a shorter side of 256, the same form used to calibrate. The kiosk receives a user crop of a 640 x 480 frame in the field; this approximates it. The C270 evaluation (separate) uses the real crops.
- These test images were already scored once through the single-view path (a first look). This is a second look at the same images through a different path. It is permitted once, with no tuning afterwards.

## 4. Metrics
For each tier, from the kiosk path:
1. **Classification-only** (argmax, gates ignored): accuracy, per-class precision, recall and F1, macro-F1, confusion matrix, 95% intervals resampling leaf groups. The same inputs through the single view are reported alongside, so path effects are not confused with input-form effects.
2. **Decision level** (gates applied, with the frozen profile): accept rate; **accepted-correct**; **accepted-wrong (classification errors that pass the gates)**; **rejected although the argmax was correct (false rejection)**; **rejected and the argmax was wrong (useful rejection)**; false-rejection rate with Wilson interval; accuracy among accepted; per-class decision-level recall, precision and rejection rate; rejections split by gate (logit, confidence, margin).
3. **OOD:** per group, fraction accepted (false acceptance) with Wilson interval and the gate that rejected the rest.
Classification errors and rejections are always reported in separate columns and are never merged into a single accuracy.
4. Informational: per-source and per-device breakdown, timing.

## 5. Acceptance criteria (proposed; fixed before the test run)
| ID | Criterion |
|---|---|
| P1 | Classification-only macro-F1 through the kiosk path is at least 0.914 on the known-device tier and 0.789 on the held-out-device tier (the original single-view values 0.934 and 0.809 minus 0.02) |
| P2 | False-rejection rate (rejected although argmax correct) is at most 5% on the known-device tier and 10% on the held-out-device tier |
| P3 | For every class and tier, decision-level recall is at least the classification-only recall minus 0.10 |
| P4 | At most 35% of the pooled Apple, Potato and Tomato leaves are accepted |
| P5 | At most 35% of the pooled non-leaf images are accepted |

All of P1 to P5 must hold for the verdict "compatible with the calibrated profile; may proceed to kiosk-path field validation". Anything less is reported as a failure. Mango leaves with unsupported conditions are informational: a closed five-class gate cannot be expected to reject them (53% were accepted on the calibration half).

Basis for the numbers: P4 and P5 sit above the calibration-half values (24% and 29%) to leave room for the shift between halves; background-only windows alone were 51% accepted on the calibration half, which is a known weakness the evaluation will quantify rather than hide. The thresholds are mine and are open to your amendment before approval.

## 6. Procedure and safeguards
1. You approve, amend or reject this protocol and the criteria.
2. I write the approval file with the hashes, then run `formal_kiosk_eval.py --mode test` once, with the application's Python, in a read-only use of `main.py`.
3. Output: per-image CSV, JSON with all metrics and the criteria verdict, and a report. Nothing is rerun and nothing is tuned afterwards. If a criterion fails, the response is a new calibration set and a new OOD evaluation set, not a new threshold on these data.
4. Production files, labels, configuration and OTA files are not touched. No training. No GitHub publication.

## 7. Known limits
The OOD sets are friendly (laboratory images, one field set of apple, two sample photographs, no other tree species). Test images are dataset images, not C270 captures. The kiosk-path gate only supports a maximum-logit rejection, which separates unsupported images with AUROC of about 0.94 and cannot reject unsupported conditions of Mango itself. The evaluation says nothing about field performance.
