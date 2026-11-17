#!/usr/bin/env python3
"""Assemble EVALUATION_REPORT.md (+ figures if matplotlib is available) from run outputs. Tiers are reported separately, never pooled."""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from common import *

sel = json.load(open(EXP + r"\SELECTION.json")); R = sel["selected_run"]
runs = pd.read_csv(EXP + r"\reports_val_runs.csv")
try:
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; HAVE = True
except Exception: HAVE = False
os.makedirs(EXP + r"\figures", exist_ok=True)
pc = lambda x: "n/a" if x is None or x != x else f"{100 * x:.1f}%"
f3 = lambda x: "n/a" if x is None or x != x else f"{x:.3f}"
L = []
a = L.append
a("# AGL-MANGO five-class experiment 001: evaluation report\n")
a(f"Dataset AGL-MANGO-MD v1.1.0-rc1 (frozen). Model: {MODEL_NAME}, ImageNet-pretrained, five outputs. Status: EXPERIMENTAL CANDIDATE, not integrated, not deployed. Production model, labels and thresholds untouched.\n")
a("## 1. Experiments\n")
a("| | A: frozen features + new head | B: partial fine-tuning |\n|---|---|---|\n| Trainable | classifier only (6,405 parameters) | blocks.4, conv_head, norm_head, classifier (1.36 M of 2.50 M) |\n| LR | head 1e-3 | head 1e-3, unfrozen backbone 3e-4 |\n| Max epochs, patience | 30, 6 | 15, 3 |\n| Seeds | 42, 43, 44 | 42, 43, 44 |\n")
a("Common: AdamW (weight decay 0.01), label smoothing 0.06, batch 32, 4,000 samples per epoch drawn class-uniform then leaf-group-uniform, 1-epoch warm-up then cosine, online augmentation (rotation, random-resized crop, flips, colour jitter, blur, JPEG), resize to shorter side 256 and 224 crop, zero-initialised new head, CPU only. Training data `splits/train.csv` (4,340 images); model selection and early stopping on `splits/val.csv` (781 images). Test tiers were not read until selection was complete.\n")
a("## 2. Validation results by run\n")
a("| Run | Best epoch | Val loss | Val accuracy | Val macro-F1 | Train time (min) | s/epoch | CPU cores used | System CPU |\n|---|---|---|---|---|---|---|---|---|")
for r in runs.itertuples(): a(f"| {r.run} | {r.best_epoch} | {r.val_loss:.3f} | {pc(r.val_accuracy)} | {r.val_macro_f1:.4f} | {r.train_minutes:.1f} | {r.mean_epoch_s:.1f} | {r.cpu_cores_used:.1f} | {r.system_cpu_pct:.0f}% |")
g = runs.groupby("experiment").agg(m=("val_macro_f1", "mean"), s=("val_macro_f1", "std"), acc=("val_accuracy", "mean"), loss=("val_loss", "mean"), tm=("train_minutes", "mean"))
a("\n| Experiment | Mean val macro-F1 (sd) | Mean val accuracy | Mean val loss | Mean train minutes |\n|---|---|---|---|---|")
for e, r in g.iterrows(): a(f"| {e} | {r.m:.4f} ({r.s:.4f}) | {pc(r.acc)} | {r.loss:.3f} | {r.tm:.1f} |")
a(f"\nPre-declared rule: the experiment with the higher mean validation macro-F1 wins unless the gap is under 0.01. Gap = {g.m['B_partial_ft'] - g.m['A_frozen_head']:.4f}, so **B_partial_ft** is selected; best seed **{sel['selected_run']}** (best epoch {sel['selected_best_epoch']}). Seeds differ by at most 0.01 within an experiment, and B is above A for every seed. Reproducibility check: re-running A seed 42 gave identical per-epoch loss and F1 (to 5 decimals) on the same machine.\n")
a("### Validation per class (mean over three seeds)\n")
a("| Class | A recall | A precision | A F1 | B recall | B precision | B F1 |\n|---|---|---|---|---|---|---|")
for c in CLASSES:
    row = []
    for e in ("A_frozen_head", "B_partial_ft"):
        d = runs[runs.experiment == e]; row += [d[f"recall_{c}"].mean(), d[f"precision_{c}"].mean(), d[f"f1_{c}"].mean()]
    a(f"| {c} {CLASS_NAMES[c]} | " + " | ".join(f3(x) for x in row) + " |")
a("\nValidation is not independent of the training sources and devices (its devices also appear in training), so it measures the same thing as the known-device tier.\n")
a(f"### Selected model validation confusion matrix ({sel['selected_run']}, rows = true class)\n")
cm = pd.read_csv(EXP + rf"\runs\{R}\val_confusion_matrix.csv", index_col=0); a(cm.to_markdown() + "\n")
vm = json.load(open(EXP + rf"\runs\{R}\val_metrics.json")); a(f"Validation: accuracy {pc(vm['accuracy'])}, macro-F1 {vm['macro_f1']:.4f}, 95% interval (leaf groups) accuracy {pc(vm['bootstrap']['accuracy_95ci'][0])} to {pc(vm['bootstrap']['accuracy_95ci'][1])}.\n")

a("## 3. Test tiers for the selected model (run once, reported separately)\n")
a("The two official tiers (known-device and held-out-device) are not pooled. Each answers a different question (see `docs/EVALUATION_TIERS.md` in the dataset). Cross-source figures are exploratory and kept separate.\n")
tiers = {"test_known_device": "Tier 1: known-device evaluation (leaf, burst and augmented-family disjoint; devices seen in training)", "test_heldout_device": "Tier 2: held-out-device evaluation (five devices never seen in training; Anthracnose and Gall Midge only)"}
for t, title in tiers.items():
    m = json.load(open(EXP + rf"\test_results\{t}_metrics.json")); a(f"### {title}\n")
    a(f"Images scored: {m['n']}. Accuracy **{pc(m['accuracy'])}** (95% interval {pc(m['bootstrap']['accuracy_95ci'][0])} to {pc(m['bootstrap']['accuracy_95ci'][1])}), macro-F1 **{m['macro_f1']:.3f}** ({m['bootstrap']['macro_f1_95ci'][0]:.3f} to {m['bootstrap']['macro_f1_95ci'][1]:.3f}); intervals resample leaf groups. Classes scored: {', '.join(m['classes_with_support'])}.\n")
    if t == "test_heldout_device": a(f"Not evaluable and excluded from the scores (fewer than 100 images or 50 leaf groups): {m['tier_info']['not_evaluable_classes_raw_counts_only']}.\n")
    a("| Class | Support | Precision | Recall | F1 | Mean confidence when correct | Mean confidence when wrong | Abstain at conf 0.40 or margin 0.12 |\n|---|---|---|---|---|---|---|---|")
    for c in CLASSES:
        p = m["per_class"][c]
        if p["support"] == 0: continue
        cf = m["confidence"][c]; a(f"| {c} {CLASS_NAMES[c]} | {p['support']} | {f3(p['precision'])} | {f3(p['recall'])} | {f3(p['f1'])} | {f3(cf['confidence_when_correct']['mean'])} | {f3(cf['confidence_when_wrong']['mean'])} | {pc(cf['abstain_at_conf0.40_or_margin0.12'])} |")
    cmx = pd.read_csv(EXP + rf"\test_results\{t}_confusion_matrix.csv", index_col=0); a("\nConfusion matrix (rows = true class):\n"); a(cmx.to_markdown() + "\n")
    a("By device (accuracy): " + "; ".join(f"{k} {pc(v['accuracy'])} (n={v['n']})" for k, v in m["by_device"].items()) + "\n")
dp = EXP + r"\test_results"
diag = [f for f in sorted(os.listdir(dp)) if f.startswith("diagnostic_crosssource") and f.endswith("_metrics.json")]
a("### Exploratory cross-source diagnostics (NOT official evaluation results of the selected candidate)\n")
a("These come from two separate throw-away models, each trained on one source with the selected recipe and tested on the other. They were trained on diagnostic manifests, which the instruction of 2026-11-17 on training data excluded; see `CROSS_SOURCE_DIAGNOSTICS_DISCLOSURE.md`. They were run after the selection and the two official test tiers were complete, were not used for selection, and describe different models, not the candidate. Treat them as exploratory only.\n")
if diag:
    for f in diag:
        m = json.load(open(os.path.join(dp, f))); nm = f.replace("diagnostic_crosssource_", "").replace("_metrics.json", "")
        a(f"**{nm.replace('_to_', ' to ')}**: images {m['n']}, accuracy {pc(m['accuracy'])} ({pc(m['bootstrap']['accuracy_95ci'][0])} to {pc(m['bootstrap']['accuracy_95ci'][1])}), macro-F1 {m['macro_f1']:.3f}. Per-class recall: " + "; ".join(f"{c} {f3(p['recall'])}" for c, p in m["per_class"].items() if p["support"]) + ".\n")
else: a("Not yet run.\n")
a("Bacterial Canker cannot be assessed here (no SAR images, and ABCGMP overlaps MangoLeafBD).\n")
a("### C270 field validation\n\nNo field data yet. No field-accuracy claim is made.\n")

a("## 4. Training time and hardware\n")
a("CPU only (20 logical CPUs, torch 10 threads, 8 data-loading workers, no GPU). Peak process memory about 0.8 to 0.9 GB. System CPU use averaged 85 to 90%, and the training process used about 6 to 7.7 cores. A run took 4 to 9 minutes; a first epoch takes about 80 s because of worker start-up. See the table in section 2.\n")
if HAVE:
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    for r in sorted(os.listdir(EXP + r"\runs")):
        if "_s4" in r and "repro" not in r and not r.startswith("DIAG"):
            e = pd.read_csv(EXP + rf"\runs\{r}\epochs.csv"); ls = "-" if r.startswith("B") else "--"; col = "tab:red" if r.startswith("B") else "tab:blue"
            ax[0].plot(e.epoch, e.train_loss, ls, color=col, alpha=.6); ax[1].plot(e.epoch, e.val_loss, ls, color=col, alpha=.6)
    ax[0].set_title("training loss (A dashed blue, B solid red)"); ax[1].set_title("validation loss"); [x.set_xlabel("epoch") for x in ax]; fig.tight_layout(); fig.savefig(EXP + r"\figures\loss_curves.png", dpi=110); plt.close(fig)
    for t in tiers:
        cmx = pd.read_csv(EXP + rf"\test_results\{t}_confusion_matrix.csv", index_col=0).values; fig, ax = plt.subplots(figsize=(4.8, 4.2)); ax.imshow(cmx, cmap="Blues")
        for i in range(5):
            for j in range(5): ax.text(j, i, cmx[i, j], ha="center", va="center", fontsize=8)
        ax.set_xticks(range(5)); ax.set_xticklabels([c[3:] for c in CLASSES]); ax.set_yticks(range(5)); ax.set_yticklabels([c[3:] for c in CLASSES]); ax.set_title(t); ax.set_xlabel("predicted"); ax.set_ylabel("true")
        fig.tight_layout(); fig.savefig(EXP + rf"\figures\{t}_confusion.png", dpi=110); plt.close(fig)
    a("Figures: `figures/loss_curves.png`, `figures/test_known_device_confusion.png`, `figures/test_heldout_device_confusion.png`.\n")
open(EXP + r"\EVALUATION_REPORT.md", "w", encoding="utf-8").write("\n".join(L)); print("report written, matplotlib:", HAVE)
