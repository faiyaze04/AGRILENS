#!/usr/bin/env python3
"""Compare experiments on VALIDATION data only and apply the pre-declared selection rule.
Rule (declared before any test tier was read): experiment = the one with the higher mean validation macro-F1 over seeds 42, 43, 44;
if the means differ by less than 0.01, the simpler experiment A (frozen features, new head) is chosen. Checkpoint = the seed of that experiment with the best validation macro-F1."""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import EXP, CLASSES

rows = []
for r in sorted(os.listdir(EXP + r"\runs")):
    p = EXP + rf"\runs\{r}\summary.json"
    if os.path.exists(p) and "_s4" in r and not r.startswith("DIAG") and "repro" not in r:
        s = json.load(open(p)); v = json.load(open(EXP + rf"\runs\{r}\val_metrics.json"))
        row = {"run": r, "experiment": s["mode"], "seed": s["seed"], "best_epoch": s["best_epoch"], "epochs_run": s["epochs_run"], "val_loss": s["val_loss"], "val_accuracy": s["val_accuracy"], "val_macro_f1": s["val_macro_f1"],
               "train_minutes": s["train_seconds"] / 60, "mean_epoch_s": s["mean_epoch_seconds"], "cpu_cores_used": s["mean_process_cpu_cores_used"], "system_cpu_pct": s["mean_system_cpu_percent"], "peak_rss_gb": s["peak_rss_gb"]}
        for c in CLASSES: row[f"f1_{c}"] = v["per_class"][c]["f1"]; row[f"recall_{c}"] = v["per_class"][c]["recall"]; row[f"precision_{c}"] = v["per_class"][c]["precision"]
        rows.append(row)
df = pd.DataFrame(rows); df.to_csv(EXP + r"\reports_val_runs.csv", index=False)
g = df.groupby("experiment").agg(n=("seed", "size"), val_macro_f1_mean=("val_macro_f1", "mean"), val_macro_f1_sd=("val_macro_f1", "std"), val_acc_mean=("val_accuracy", "mean"),
                                 val_loss_mean=("val_loss", "mean"), train_min_mean=("train_minutes", "mean"), best_epoch_mean=("best_epoch", "mean"))
print(df.round(4).to_string()); print(g.round(4).to_string())
means = g.val_macro_f1_mean.to_dict()
if "A_frozen_head" in means and "B_partial_ft" in means:
    sel = "B_partial_ft" if means["B_partial_ft"] - means["A_frozen_head"] >= 0.01 else "A_frozen_head"
    d = df[df.experiment == sel].sort_values("val_macro_f1", ascending=False).iloc[0]
    out = {"rule": __doc__.split("\n")[1], "mean_val_macro_f1": means, "selected_experiment": sel, "selected_run": d.run, "selected_seed": int(d.seed), "selected_best_epoch": int(d.best_epoch)}
    json.dump(out, open(EXP + r"\SELECTION.json", "w"), indent=1); print(json.dumps(out, indent=1))
