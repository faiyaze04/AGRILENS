#!/usr/bin/env python3
"""Build the model experiment register (CSV + Markdown) from the run folders."""
import json, os, sys
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import *

ROOT = r"D:\AGRILENS_Training\AGL-MANGO-MD"; rows = []
sel = json.load(open(EXP + r"\SELECTION.json"))["selected_run"]
for r in sorted(os.listdir(EXP + r"\runs")):
    p = EXP + rf"\runs\{r}"; s = json.load(open(p + r"\summary.json")) if os.path.exists(p + r"\summary.json") else {}
    ck = p + r"\best.pt" if os.path.exists(p + r"\best.pt") else p + r"\last.pt"
    kind = "exploratory diagnostic (throw-away, trained on diagnostic manifests)" if r.startswith("DIAG") else ("reproducibility re-run" if "repro" in r else "official experiment run")
    rows.append({"id": r, "kind": kind, "mode": s.get("mode", ""), "seed": s.get("seed", ""), "epochs_run": s.get("epochs_run", ""), "best_epoch": s.get("best_epoch", ""),
                 "val_macro_f1": round(s["val_macro_f1"], 4) if "val_macro_f1" in s else "", "val_accuracy": round(s["val_accuracy"], 4) if "val_accuracy" in s else "", "train_minutes": round(s.get("train_seconds", 0) / 60, 1),
                 "checkpoint": os.path.relpath(ck, EXP).replace(os.sep, "/"), "checkpoint_sha256": sha256(ck), "config": f"configs/{r}.yaml", "config_sha256": sha256(EXP + rf"\configs\{r}.yaml"),
                 "status": ("SELECTED CANDIDATE (experimental)" if r == sel else ("exploratory, not a candidate" if r.startswith("DIAG") else "not selected")), "note": ""})
df = pd.DataFrame(rows)
df.loc[df.id == "A_frozen_head_s42_repro", "note"] = "identical to A_frozen_head_s42 to 5 decimals"
df.loc[df.id.str.startswith("DIAG"), "note"] = "see CROSS_SOURCE_DIAGNOSTICS_DISCLOSURE.md; results not official; never used for selection"
extra = [
    {"id": "A_frozen_head_s42 (first start)", "kind": "aborted", "status": "stopped after 1 epoch, discarded", "note": "random-initialised head gave loss 5.06; restarted with zero-initialised head; no test data involved; outputs deleted"},
    {"id": "ABL1_device_capped_sampling", "kind": "proposal", "status": "NOT EXECUTED; explicitly NOT AUTHORISED (user, 2026-11-17)", "note": "proposals/ABL1_device_capped_sampling.yaml"},
    {"id": "ABL2a/ABL2b_reduced_colour_jitter", "kind": "proposal", "status": "NOT EXECUTED; explicitly NOT AUTHORISED (user, 2026-11-17)", "note": "proposals/ABL2_reduced_colour_jitter.yaml"},
    {"id": "C270 field collection", "kind": "data collection", "status": "APPROVED 2026-11-17; collector and kiosk-path evaluation tool built and tested on synthetic data; collection not started (needs C270 in enclosure, operator, trees, expert)", "note": "field_validation/C270_COLLECTION_READINESS_REPORT.md"},
    {"id": "Raspberry Pi 5 benchmark", "kind": "benchmark", "status": "APPROVED 2026-11-17; Pi package built (single view + actual six-view kiosk path), desktop dry run only; NOT yet run on a Pi (needs access)", "note": "pi5_package_v1.zip, kiosk_path/README_PI_PACKAGE.md, kiosk_path/KIOSK_PATH_FINDINGS.md"},
    {"id": "Kiosk-path check of the candidate (desktop)", "kind": "evaluation tooling", "status": "done on 100 validation-derived crops, read-only use of main.py", "note": "single view = kiosk path (100% agreement); logit gate at 6.0 rejects all, at 1.4 rejects 4%"},
    {"id": "OOD / confidence calibration study (train, validation, OOD calibration half)", "kind": "analysis", "status": "done; proposal ood_logit 1.5 (conf 0.40, margin 0.12), not applied anywhere", "note": "ood/OOD_CALIBRATION_REPORT.md"},
    {"id": "Formal kiosk-path evaluation of the frozen test tiers", "kind": "evaluation", "status": "APPROVED and EXECUTED ONCE 2026-11-17: P1 pass, P2 FAIL, P3 FAIL, P4 pass, P5 pass; recorded as secondary; run-once lock set; not to be repeated", "note": "KIOSK_PATH_EVALUATION_CONCISE_REPORT.md, kiosk_eval/test_run_ONCE/"},
    {"id": "Integrated model training", "kind": "strategy", "status": "NOT STARTED; needs review of Mango findings and an approved plan", "note": "DECISION_LOG.md"},
    {"id": "Expert review package", "kind": "label verification", "status": "APPROVED 2026-11-17; 235 blinded items in two tranches, analysis tool tested on simulated answers; awaiting expert", "note": "expert_review_package/, key in expert_review_package_KEY/"},
]
full = pd.concat([df, pd.DataFrame(extra)], ignore_index=True).fillna(""); full.to_csv(ROOT + r"\experiments\EXPERIMENT_REGISTER.csv", index=False)
cand = json.load(open(EXP + rf"\models\mango5_exp001_{sel}_candidate_VERSION_MANIFEST_v2.json"))
md = ["# Model experiment register\n", "Updated 2026-11-17. Production app, 24-class model, labels and thresholds are unchanged by every entry. `EXPERIMENT_REGISTER.csv` has the same table with checksums.\n",
      "## Candidates\n", "| Candidate | Status | Model SHA-256 | Checkpoint SHA-256 | Preserved at |\n|---|---|---|---|---|",
      f"| mango5_exp001 / {sel} | EXPERIMENTAL CANDIDATE, accepted for study, not approved for production | `{cand['onnx']['sha256']}` | `{cand['checkpoint']['sha256']}` | `candidates/mango5_exp001_B_partial_ft_s43_v1/` (write-protected, checksums listed) |\n",
      "## Runs and activities\n", full[["id", "kind", "mode", "seed", "best_epoch", "val_macro_f1", "val_accuracy", "status", "note"]].to_markdown(index=False), "\n",
      "## Results at a glance (selected candidate; tiers never pooled)\n", "- Validation (used for selection): macro-F1 0.984, accuracy 98.3%.\n- Known-device test: accuracy 93.4%, macro-F1 0.934 (574 images).\n- Held-out-device test (Anthracnose, Gall Midge only): accuracy 79.4%, macro-F1 0.809 (597 images).\n- Cross-source figures: exploratory only (see disclosure).\n- Field (C270): none.\n",
      "## Governance notes\n", "- Test tiers were run once for the selected candidate (`TEST_TIERS_RUN_ONCE.json`).\n- Cross-source diagnostic models were trained on diagnostic manifests contrary to the training-data instruction; documented in `CROSS_SOURCE_DIAGNOSTICS_DISCLOSURE.md`.\n- `v1` version manifest and as-built evaluation are preserved unchanged; `v2` manifest and the report carry the corrected classification.\n- No further training is authorised.\n"]
open(ROOT + r"\experiments\EXPERIMENT_REGISTER.md", "w", encoding="utf-8").write("\n".join(md)); print(len(full), "register rows")
