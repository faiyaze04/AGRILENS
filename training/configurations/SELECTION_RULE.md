# AGRILENS-MULTICROP 1.0.0: pre-declared selection rule

Written before any training run started. Not to be changed after results are seen.

1. Candidates: recipes R1 (last stage + head trainable, as the Mango candidate) and R2 (last two stages + head), seeds 42 and 43. Same data, sampling, augmentation and optimiser. Architecture: MobileNetV4-Conv-Small, the production architecture (Pi-compatible, 10 MB ONNX, timm/ONNX path already proven). No other architecture is tried in 1.0.0.
2. Selection uses VALIDATION only (`splits/val.csv`, single view).
3. Recipe: the recipe with the higher mean validation macro-F1 over the two seeds. If the difference is below 0.005, R1 (fewer trainable parameters) is chosen.
4. Run: the seed of the chosen recipe with the higher validation macro-F1.
5. Gate calibration (after selection, validation only, through the application's six-view path): choose the largest `ood_logit` for which the false rejection of correctly classified validation images is at most 3% in EVERY crop and in every Mango source with at least 50 validation images (worst group, not pooled; lesson of the Mango kiosk-path evaluation). Confidence 0.40 and margin 0.12 stay as in production. The resulting values are frozen before any test tier is read.
6. Test tiers (`test_known_device`, `test_heldout_device`) and the unsupported-image evaluation half are run once, after the release criteria (`training/evaluation/RELEASE_EVALUATION_CRITERIA.md`) are written.
