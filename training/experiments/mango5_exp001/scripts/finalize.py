#!/usr/bin/env python3
"""Add the test-tier summary to the model version manifest, write the experiment README and checksum all experiment artefacts."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

sel = json.load(open(EXP + r"\SELECTION.json")); R = sel["selected_run"]; mp = EXP + rf"\models\mango5_exp001_{R}_candidate_VERSION_MANIFEST.json"
man = json.load(open(mp)); T = EXP + r"\test_results"; summ = {}
for t in ("test_known_device", "test_heldout_device"):
    m = json.load(open(T + rf"\{t}_metrics.json")); summ[t] = {"images": m["n"], "accuracy": round(m["accuracy"], 4), "macro_f1": round(m["macro_f1"], 4), "classes": m["classes_with_support"],
                                                              "accuracy_95ci": [round(x, 4) for x in m["bootstrap"]["accuracy_95ci"]], "per_class_recall": {c: round(p["recall"], 3) for c, p in m["per_class"].items() if p["support"]}}
for f in sorted(os.listdir(T)):
    if f.startswith("diagnostic_crosssource") and f.endswith("_metrics.json"):
        m = json.load(open(T + rf"\{f}")); summ[f.replace("_metrics.json", "")] = {"images": m["n"], "accuracy": round(m["accuracy"], 4), "macro_f1": round(m["macro_f1"], 4), "per_class_recall": {c: round(p["recall"], 3) for c, p in m["per_class"].items() if p["support"]}}
man["test_tiers_run_once"] = summ; man["test_tiers_note"] = "reported separately, never pooled; tier 4 (C270 field validation) not yet available; no field-accuracy claim"
man["selection"] = sel; json.dump(man, open(mp, "w"), indent=1)
open(EXP + r"\README.md", "w", encoding="utf-8").write("""# mango5-exp001: controlled five-class Mango training (EXPERIMENTAL)

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
""")
lines = []
for d in ("configs", "scripts", "runs", "logs", "test_results", "models", "figures"):
    for dp, _, fs in os.walk(os.path.join(EXP, d)):
        for f in sorted(fs):
            if "__pycache__" in dp: continue
            p = os.path.join(dp, f); lines.append(f"{sha256(p)}  {os.path.relpath(p, EXP).replace(os.sep, '/')}")
for f in ("EVALUATION_REPORT.md", "SELECTION.json", "reports_val_runs.csv", "PI5_INFERENCE_BENCHMARK_PLAN.md", "README.md", "TEST_TIERS_RUN_ONCE.json"):
    lines.append(f"{sha256(os.path.join(EXP, f))}  {f}")
open(EXP + r"\ARTIFACT_CHECKSUMS.sha256", "w", encoding="utf-8").write("\n".join(sorted(lines, key=lambda x: x.split('  ', 1)[1])) + "\n"); print(len(lines), "files checksummed")
