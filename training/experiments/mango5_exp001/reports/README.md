# mango5-exp001: controlled five-class Mango training (EXPERIMENTAL)

Dataset: AGL-MANGO-MD v1.1.0-rc1 (frozen, read-only). Production app, 24-class model, labels and thresholds are untouched. Nothing is deployed.

| Path | Content |
|---|---|
| `configs/` | one YAML per run (A/B, seeds 42, 43, 44; repro run; two cross-source diagnostics) |
| `scripts/` | `prepare_cache.py`, `train.py`, `summarise.py` (selection rule), `eval_test.py` (run once), `run_diagnostics.py`, `export_onnx.py`, `make_report.py`, `finalize.py`, `common.py`, queue scripts |
| `runs/<run>/` | `epochs.csv`, `run_info.json`, `summary.json`, `val_metrics.json`, `val_predictions.csv`, `val_confusion_matrix.csv`, `best.pt`, `last.pt` |
| `logs/` | stdout and stderr of every run and step |
| `test_results/` | frozen test tiers, run once (metrics, confusion matrices, per-image predictions) |
| `models/` | ONNX candidate, labels file, version manifest |
| `EVALUATION_REPORT.md`, `SELECTION.json`, `reports_val_runs.csv`, `figures/` | results |
| `PI5_INFERENCE_BENCHMARK_PLAN.md` | plan only, not executed |
| `ARTIFACT_CHECKSUMS.sha256` | SHA-256 of every file above except the image cache |
| `cache/` | resized copies of dataset images (derived, can be rebuilt with `prepare_cache.py`) |

Reproduce: `python scripts/make_configs.py`, `python scripts/prepare_cache.py`, `python scripts/train.py configs/<run>.yaml`, `python scripts/summarise.py`, `python scripts/eval_test.py <selected run>`, `python scripts/run_diagnostics.py`, `python scripts/export_onnx.py <selected run>`, `python scripts/make_report.py`.
Environment: torch 2.11.0+cpu, timm 1.0.31, CPU only. Re-running A seed 42 reproduced every epoch to five decimals on this machine.
