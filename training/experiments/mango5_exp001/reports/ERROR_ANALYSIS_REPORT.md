# Error analysis: candidate mango5_exp001 / B_partial_ft_s43

Scope: the already-run test tiers of the selected candidate (known-device 574 images, held-out-device 597 scored images). Predictions were read, nothing was re-scored, retrained or relabelled. Image observations below are mine and are not agronomic judgements; the expert review package asks the expert to decide.

Data: `error_table_*.csv` (every image), `errors_tagged_*.csv`, `device_accuracy_*.csv`, `device_colour_stats.csv`, `error_analysis_stats.json`, figures in `figures/`.

## 1. Summary

1. The 46 + 53 Anthracnose/Gall Midge errors are concentrated in particular sessions and devices, not spread evenly. 67 of the 99 fall on one day, 2024-01-13. On other days the same devices score 88 to 100% on the same classes.
2. Image quality does not explain them. Sharpness, exposure, framing and brightness show little or no relation to error (AUROC 0.35 to 0.63, where 0.5 means none; the larger values are for image width and saturation, which differ by device).
3. Label ambiguity is the strongest correlate. Errors have much lower agreement with their own nearest same-source neighbours (AUROC 0.28, so low agreement predicts error). 46% of the Anthracnose images called Gall Midge have neighbours that mostly belong to another class, against 9% of correctly classified Anthracnose images.
4. A colour and lighting shift is plausible: the held-out devices' images are darker and less saturated than the SAR training devices (saturation 0.18 against about 0.26).
5. The 13 Healthy leaves called Gall Midge are all from one realme 5i session (2024-01-08), where Healthy accuracy is 71% against 96 to 100% on every other day. Most show specular glare, and two are yellow senescent leaves.
6. The production abstention thresholds (confidence 0.40, margin 0.12) offer little protection once the device changes: they catch 23% of the errors on held-out devices, and 17% of the answers that are still given are wrong.
7. No cause can be settled from images alone. The Anthracnose and Gall Midge definitions need the expert.

## 2. Held-out devices: Anthracnose and Gall Midge (597 images, 79.4%)

| | Anthracnose called Gall Midge | Gall Midge called Anthracnose |
|---|---|---|
| Errors | 46 of 321 images | 53 of 276 images |
| Distinct leaf groups | 42 of 284 | 43 of 216 |
| By device | vivo V2204 27, SM-A525F 19 | SM-A525F 43, vivo V2204 10 |
| By date | 2024-01-13: 27, 2023-12-30: 9, 2024-01-03: 8, other 2 | 2024-01-13: 40, 2024-01-08: 11, other 2 |
| Confidence of the wrong answer (median, p10 to p90) | 0.62 (0.43 to 0.88) | 0.71 (0.47 to 0.84) |
| Margin (median) | 0.38 | 0.52 |
| Probability given to the true class (median) | 0.15 | 0.17 |
| Confidence of 0.8 or more | 22% of the errors | 21% |
| Would be abstained at 0.40 / 0.12 | 24% | 17% |
| Own-class agreement among 10 neighbours, errors vs correct | 5.1 vs 8.1 | 7.5 vs 8.7 |
| Errors with neighbour majority in the other class, vs correct | 46% vs 9% | 17% vs 8% |

Leaf-level consistency: of the 284 Anthracnose leaf groups, 47 were wrong on every image and 6 mixed. Of the 216 Gall Midge groups, 47 were wrong on every image and 7 mixed. The model's mistakes are mostly consistent per leaf, so they come from what the leaf looks like (or how it is labelled), not from random image noise.

Representative images are in `figures/heldout_anth_as_gm_*.jpg`, `heldout_gm_as_anth_*.jpg` and correct examples in `heldout_anth_correct.jpg`, `heldout_gm_correct.jpg`. What I see:
- Anthracnose called Gall Midge (highest confidence): dull, dark, mottled leaves with scattered holes or margin damage, photographed on crumpled white paper, mostly vivo V2204 and SM-A525F. The surface texture resembles the dark bumpy patterns of the Gall Midge training images.
- Gall Midge called Anthracnose (highest confidence): SM-A525F leaves on white paper with small, flat, dark-brown round spots. These look like leaf-spot lesions rather than raised galls, so the source label `Golmichi` may cover a different symptom than the training images show.

## 3. Device and session

| Device | Class | Images | Recall (95% Wilson) | Leaf groups |
|---|---|---|---|---|
| SM-A525F | Anthracnose | 268 | 0.899 (0.857 to 0.930) | 240 |
| SM-A525F | Gall Midge | 208 | 0.736 (0.672 to 0.791) | 161 |
| vivo V2204 | Anthracnose | 53 | 0.434 (0.310 to 0.567) | 44 |
| vivo V2204 | Gall Midge | 68 | 0.838 (0.733 to 0.907) | 55 |
| SM-A525F, all | | 476 | 0.828 | 401 |
| vivo V2204, all | | 121 | 0.661 | 99 |

Session matters more than the device label:

| Device | Date | Class | Images | Accuracy |
|---|---|---|---|---|
| SM-A525F | 2024-01-13 | Gall Midge | 45 | 0.244 |
| SM-A525F | 2024-01-08 | Gall Midge | 136 | 0.904 |
| SM-A525F | 2024-01-13 | Anthracnose | 93 | 0.925 |
| vivo V2204 | 2024-01-13 | Anthracnose | 35 | 0.286 |
| vivo V2204 | 2024-01-13 | Gall Midge | 22 | 0.500 |
| vivo V2204 | 2024-01-08 | Gall Midge | 46 | 1.000 |

The device difference and the session difference cannot be separated in this data, because each held-out device was used on few days. The V2204 Anthracnose figure rests on 53 images from 44 leaf groups, mostly from 2024-01-13, so it is imprecise.

Colour statistics (mean of the 224 crop; saturation is HSV):

| Group | Mean R / G / B | Saturation |
|---|---|---|
| SAR training devices (realme 5i, SM-G570F) | 0.60 to 0.63 / 0.60 to 0.66 / 0.54 to 0.57 | 0.26 |
| Held-out SM-A525F | 0.56 / 0.59 / 0.58 | 0.18 |
| Held-out vivo V2204 | 0.57 / 0.57 / 0.55 | 0.19 |

The held-out devices are darker and have weaker colour. Together with the session pattern this makes a lighting or white-balance shift likely. I did not test it directly.

## 4. Healthy called Gall Midge (known-device tier, 13 of 137 Healthy images)

- All 13 come from SAR realme 5i on 2024-01-08, 8 leaf groups. On that date Healthy accuracy was 0.71 (59 images). On every other date it was 0.96 to 1.00 (realme 5i 2023-12-24 to 2024-01-03: 1.00).
- Confidence is low (median 0.44, margin 0.14, p(true class) 0.24). 38% would be abstained at production thresholds.
- The labels look consistent with their neighbours (9 of the 13 have a majority of Healthy neighbours). Sharpness is above the Healthy median, so blur is not the cause.
- In `figures/known_healthy_as_gm.jpg`, most leaves show bright specular glare patches and two (S000308, S000310) are yellow or orange senescent leaves. Glare can imitate a powdery or pitted lesion. The statistical link between highlight area and error is weak (AUROC 0.58), so glare is a hypothesis from the images, not a result.
- Open label question: is a senescent yellow leaf Healthy? The dataset defines no rule.

## 5. Confidence and margin of incorrect predictions

| | Known-device | Held-out-device |
|---|---|---|
| Correct: median confidence / margin | 0.94 / 0.92 | 0.89 / 0.84 |
| Incorrect: median confidence / margin | 0.52 / 0.22 | 0.64 / 0.42 |
| Errors with confidence of 0.8 or more | 2.6% | 21.1% |
| Errors caught by the production thresholds | 31.6% | 22.8% |
| Correct answers wrongly withheld | 1.3% | 3.8% |
| Error rate of answers still given | 4.7% (overall 6.6%) | 17.2% (overall 20.6%) |
| Coverage (answers given) | 96.7% | 92.3% |
| Confidence as an error detector (AUROC) | 0.96 | 0.82 |

On known devices, low confidence is a good error signal. Under device shift, confidence stays high for a fifth of the errors and a threshold cannot separate them. The production thresholds were not changed or tuned.

## 6. Image quality and other attributes (association with error, AUROC where 0.5 is none)

| Attribute | Known-device | Held-out-device |
|---|---|---|
| Sharpness | 0.50 | 0.52 |
| Mean brightness | 0.62 | 0.49 |
| Foreground fraction | 0.44 | 0.60 |
| Border contact (cropped framing) | 0.35 | 0.60 |
| Highlights clipped | 0.58 | 0.50 |
| Image width | 0.63 | 0.63 |
| Mean saturation | 0.61 | 0.61 |
| **Neighbour agreement (low predicts error)** | **0.22** | **0.28** |

Only neighbour agreement stands out.

## 7. Likely causes (rule-based tags, not mutually exclusive; the first matching rule is the primary tag)

Rules: image quality = sharpness below the source 10th percentile, foreground under 5%, strong highlight clipping or very dark; label ambiguity suspected = 4 or fewer of 10 same-source neighbours share the label; confident model error = confidence 0.8 or more, good quality and 7 or more agreeing neighbours; otherwise unexplained or low margin.

| Tier | Errors | Image quality | Label ambiguity suspected | Confident model error | Unexplained / low margin |
|---|---|---|---|---|---|
| Held-out-device | 123 | 16 | 37 | 10 | 60 |
| Known-device | 38 | 4 | 7 | 0 | 27 |

By device (held-out, primary tag): vivo V2204 mostly label ambiguity (21 of 41), SM-A525F mostly unexplained or low margin (44 of 82).

Reading, with the limits stated:
- **Label ambiguity** is the best-supported cause for Anthracnose images called Gall Midge. It agrees with earlier findings: 20 identical SAR files filed under both classes, and the class pair overlapping in the neighbour screen.
- **Device or session shift** is the best-supported cause for Gall Midge called Anthracnose and for the Healthy errors. The date concentration is strong; the mechanism (lighting, colour, collector, leaf condition) is not established.
- **Image quality** is a minor cause (13% of held-out errors) and is not the main driver.
- **Model limitation** (confident errors on clear images) accounts for 8% of held-out errors by the strict rule. A large part of the remaining 49% unexplained errors are low-margin cases at the boundary between similar classes, which can reflect model limits and class overlap together. The model is trained on a small set with few leaves per class, so some limitation is expected.

## 8. What I did not do

No image was relabelled, released from quarantine or removed. The tags are not labels. No model was retrained. Resolving label ambiguity needs the agronomic review (`../expert_review_package/`).

## 9. Suggested follow-up (for your decision)

1. Expert review of the Anthracnose and Gall Midge confusion images (package prepared).
2. A definition for senescent and glossy Healthy leaves.
3. Check the SAR collection sessions of 2024-01-08 and 2024-01-13 with the dataset authors, if possible (collector, lighting, label procedure).
4. C270 field data, scored with the kiosk's actual inference path (see the readiness report).
5. The two ablation proposals (device-capped sampling, reduced colour jitter) once this analysis and the field collection have been reviewed.
