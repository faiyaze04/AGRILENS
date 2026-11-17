#!/usr/bin/env python3
"""Cross-source DIAGNOSTIC tier. For each direction train a separate throw-away model with the SELECTED recipe (same mode, hyperparameters and
epoch count as the selected run, no validation, no tuning), then evaluate once on the other source. These models are never candidates and
never used for selection. Source and device are fully separated between training and test in this tier.
  python run_diagnostics.py"""
import copy, json, os, subprocess, sys
import numpy as np, pandas as pd, timm, torch, yaml
sys.path.insert(0, os.path.dirname(__file__))
from common import *

sel = json.load(open(EXP + r"\SELECTION.json")); base = yaml.safe_load(open(EXP + rf"\configs\{sel['selected_run']}.yaml"))
out_dir = EXP + r"\test_results"; os.makedirs(out_dir, exist_ok=True); py = sys.executable
for A, B in (("SAR25", "MANGOLEAFBD"), ("MANGOLEAFBD", "SAR25")):
    name = f"DIAG_{A}_to_{B}"; res = out_dir + rf"\diagnostic_crosssource_{A}_to_{B}_metrics.json"
    assert not os.path.exists(res), "already run once"
    c = copy.deepcopy(base); c["run_id"] = name; c["seed"] = 42
    c["data"] = {"train_manifest": f"splits/diagnostic_crosssource_train_{A}_test_{B}.csv", "train_role": "train", "val_manifest": None, "allow_test_overlap": True}
    c["optim"]["fixed_epochs"] = sel["selected_best_epoch"]; c["selection"] = {"monitor": "none (fixed epochs of the selected run)", "test_tiers_used": False}
    cp = EXP + rf"\configs\{name}.yaml"; yaml.safe_dump(c, open(cp, "w"), sort_keys=False)
    subprocess.run([py, EXP + r"\scripts\train.py", cp], stdout=open(EXP + rf"\logs\{name}.log", "w"), stderr=open(EXP + rf"\logs\{name}.err", "w"), check=True)
    ck = torch.load(EXP + rf"\runs\{name}\last.pt", weights_only=False); model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=5); model.load_state_dict(ck["state_dict"]); model.eval()
    d = pd.read_csv(os.path.join(RC, "splits", f"diagnostic_crosssource_train_{A}_test_{B}.csv")); d = d[d.role == "test"].reset_index(drop=True)
    y = d.class_id.map(CIDX).to_numpy(); P = predict(model, d.master_image_id.tolist())
    m = metrics_from_probs(y, P); m["confidence"] = confidence_report(y, P); m["bootstrap"] = bootstrap_ci(y, P, d.leaf_group_id.to_numpy(), 1000, 0)
    m["by_device"] = {s: {"n": int((d.capture_device == s).sum()), "accuracy": metrics_from_probs(y[(d.capture_device == s).to_numpy()], P[(d.capture_device == s).to_numpy()])["accuracy"]} for s in d.capture_device.unique()}
    m["tier_info"] = {"train_source": A, "test_source": B, "train_images": int(sum(1 for _ in open(EXP + rf"\runs\{name}\epochs.csv")) - 1) and None, "test_images": len(d), "classes_in_test": d.class_id.value_counts().to_dict(),
                      "note": "diagnostic model, 4 classes present (no Bacterial Canker in SAR); not a candidate"}
    json.dump(m, open(res, "w"), indent=1)
    pd.DataFrame(m["confusion_matrix"], index=CLASSES, columns=CLASSES).to_csv(out_dir + rf"\diagnostic_crosssource_{A}_to_{B}_confusion_matrix.csv")
    print(name, "n", m["n"], "acc", round(m["accuracy"], 4), "macroF1", round(m["macro_f1"], 4), {c: round(v["recall"], 3) for c, v in m["per_class"].items() if v["support"]}, flush=True)
