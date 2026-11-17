# Controlled kiosk-path evaluation: concise report for the decision gate

Executed once on 2026-11-17 (run-once lock written 10:34:19 UTC), after the protocol and criteria were approved. Recorded as a **secondary** evaluation; the original single-view results are unchanged and remain the primary record. Full tables: `kiosk_eval/test_run_ONCE/KIOSK_PATH_EVALUATION_REPORT.md`; per-image outputs and checksums are in the same folder (write-protected).

Frozen and verified before the run: candidate ONNX `a241d91c…`, the application's own six-view `Classifier.predict` and decision code (`main.py` `b600d71c…`, imported read-only), `ood_logit` 1.5, confidence 0.40, margin 0.12, the frozen test manifests, the reserved OOD evaluation half. Production files, labels and configuration, the frozen dataset and the candidate bundle are unchanged (checked after the run). Nothing was trained, tuned, repeated or published.

## 1. Verdict against the approved criteria

| Criterion | Limit | Result | Verdict |
|---|---|---|---|
| P1 known-device macro-F1 | at least 0.914 | 0.956 | PASS |
| P1 held-out-device macro-F1 | at least 0.789 | 0.820 | PASS |
| P2 false rejection, known-device | at most 5% | 6.0% (33 of 548 correct images) | **FAIL** |
| P2 false rejection, held-out-device | at most 10% | 12.4% (60 of 484) | **FAIL** |
| P3 decision-level recall within 0.10 of classification-only recall | every class and tier | Healthy, known-device: 0.796 against 0.934 (drop 0.138); Anthracnose, held-out-device: 0.763 against 0.866 (drop 0.103) | **FAIL** |
| P4 other-crop leaves accepted | at most 35% | 20.4% (92 of 450) | PASS |
| P5 non-leaf images accepted | at most 35% | 33.5% (52 of 155) | PASS, 1.5 points below the limit |

**Overall: criteria failed (P2 and P3).** Recorded as a failure. No threshold or criterion was changed.

## 2. Classification and rejection, kept apart

| | Known-device (574) | Held-out-device (597) |
|---|---|---|
| Classification accuracy (gates ignored) | 95.5% (93.5 to 97.2) | 81.1% (77.1 to 84.7) |
| Classification macro-F1 | 0.956 | 0.820 |
| Same inputs, single view | 93.4%, 0.934 | 79.4%, 0.809 |
| Accepted and correct | 515 (89.7%) | 424 (71.0%) |
| Accepted but wrong (classification errors passing the gates) | 13 (2.3%) | 75 (12.6%) |
| Correctly classified images rejected | 33 (6.0% of the correct) | 60 (12.4%) |
| Incorrect predictions rejected | 13 (50% of the wrong) | 38 (33.6%) |
| Accuracy among accepted images | 97.5% | 85.0% |

- The single-view row reproduces the original single-view results exactly, which confirms the evaluation uses the same images and preprocessing.
- The kiosk path classifies about 2 points better than the single view (whole image, six views). That gain mixes the path with the use of the whole image rather than the centre crop.
- Per-class precision, recall, F1 and confusion matrices are in the full report. Known-device recall: Anthracnose 0.979, Bacterial Canker 1.000, Gall Midge 0.894, Healthy 0.934, Powdery Mildew 0.976. Held-out-device: Anthracnose 0.866, Gall Midge 0.746.
- Decision-level recall (rejection counted as a miss): known-device Anthracnose 0.972, Bacterial Canker 1.000, Gall Midge 0.798, Healthy 0.796, Powdery Mildew 0.953; held-out-device Anthracnose 0.763, Gall Midge 0.649.
- All 144 rejections came from the logit gate. The confidence and margin gates never fired.
- By device (classification accuracy): held-out SM-A525F 84.9%, vivo V2204 66.1%; known-device HUAWEI RNE-L22 94.3%, realme 5i 96.2%, SM-G570F 93.7%, SM-G935S 100%, unknown 92.4% (vivo 1906 has 29 images, too few).

## 3. Unsupported images (reserved evaluation half, 755 images)

| Group | n | Accepted |
|---|---|---|
| Other-crop leaves, pooled | 450 | 20.4% (Apple 12.7%, Potato 21.3%, Tomato 27.3%) |
| Non-leaf images, pooled | 155 | 33.5% |
| Background-only windows (reported separately) | 75 | **50.7%** (39.6 to 61.7) |
| Sample photographs | 50 | 28.0% |
| Synthetic images | 30 | 0% |
| All unsupported images except the informational group | 605 | 23.8% |
| Mango leaves with unsupported conditions (informational) | 150 | 58.7% |
| All 755 | 755 | 30.7% |

P5 passed only because the synthetic images (all rejected) and photographs pull the pooled figure down. Half of the background-only windows would receive a diagnosis.

## 4. What the descriptive breakdown shows (not used for any decision)

- False rejection is concentrated in SAR images: 7.9% of correctly classified known-device SAR images against 0.9% for MangoLeafBD and 0% for ABCGMP. By class, Healthy 14.8% and Gall Midge 10.7% on known devices; on held-out devices vivo V2204 21.2% and SM-A525F 10.6%.
- Logits fall under device shift: median maximum logit 2.89 (validation), 2.81 (known-device test), 2.35 (held-out-device test).
- The 2% false rejection set on validation (a mixture of sources) became 6% on the known-device test and 12% on the held-out devices. Validation under-represented the shift. One global logit threshold interacts with source and device.

## 5. Limitations
- Inputs are dataset images in the cached form, not C270 frames or user crops. Unsupported sets are friendly. P5's margin is thin and its interval (26.6 to 41.3%) spans the limit.
- These images were scored once before through the single-view path; this is a second look, done once.
- Nothing here measures field performance, the Pi, or label correctness.

## 6. Recommendations (for the decision gate; none acts on the test data)
1. Treat the profile as **not yet adequate**. The kiosk rejects too many correct Healthy, Gall Midge and shifted-device images, and still accepts half of the empty-background windows.
2. Do **not** adjust `ood_logit` on these results. Any change needs a new calibration set that includes device and source shift (for example validation split by device, and the field calibration trees) and a new, unseen OOD evaluation set.
3. The gate type is the constraint: a single maximum-logit threshold on a closed five-class model cannot reject unsupported Mango conditions and empty frames, and penalises classes with lower logits. Options for you to consider (nothing is started): an explicit "other / not a leaf" class in the integrated model; per-class or source-aware gating (needs an application change, which is not authorised); separate leaf-presence and quality checks before diagnosis.
4. Carry the lesson into the integrated plan: gates must be calibrated on shifted data and evaluated per class and per source.
5. The Raspberry Pi benchmark, the expert review and the C270 collection are the next evidence and remain pending. C270 data should include out-of-scope captures and a tree-level calibration split.

No ablation or integrated training is started. Waiting for your explicit approval.
