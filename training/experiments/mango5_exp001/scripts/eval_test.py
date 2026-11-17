#!/usr/bin/env python3
"""Run the frozen TEST tiers ONCE for the selected checkpoint. Refuses to run twice (lock file). Tiers are reported separately, never pooled.
  python eval_test.py <run_id>"""
import json, os, sys, time
import numpy as np, pandas as pd, timm, torch
sys.path.insert(0, os.path.dirname(__file__))
from common import *

run = sys.argv[1]; sel = json.load(open(EXP + r"\SELECTION.json")); assert sel["selected_run"] == run, "run is not the selected run"
lock = EXP + r"\TEST_TIERS_RUN_ONCE.json"
assert not os.path.exists(lock), "test tiers were already run once; refusing to run again"
verify_frozen_files()
ck = torch.load(EXP + rf"\runs\{run}\best.pt", weights_only=False)
model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=5); model.load_state_dict(ck["state_dict"]); model.eval()
json.dump({"run": run, "checkpoint_sha256": sha256(EXP + rf"\runs\{run}\best.pt"), "run_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, open(lock, "w"), indent=1)
out_dir = EXP + r"\test_results"; os.makedirs(out_dir, exist_ok=True)
res = {}
for tier in ("test_known_device", "test_heldout_device"):
    df = pd.read_csv(os.path.join(RC, "splits", tier + ".csv")); ids = df.master_image_id.tolist(); y = df.class_id.map(CIDX).to_numpy(); P = predict(model, ids)
    pd.concat([df[["master_image_id", "class_id", "source_id", "capture_device", "leaf_group_id"]].reset_index(drop=True), pd.DataFrame(P, columns=[f"p_{c}" for c in CLASSES])], axis=1).to_csv(out_dir + rf"\{tier}_predictions.csv", index=False)
    info = {"images": len(df), "images_by_class": df.class_id.value_counts().to_dict(), "leaf_groups_by_class": df.groupby("class_id").leaf_group_id.nunique().to_dict()}
    if tier == "test_heldout_device":
        ev = [c for c in CLASSES if (df.class_id == c).sum() >= 100 and df[df.class_id == c].leaf_group_id.nunique() >= 50]
        info["evaluable_classes (>=100 images and >=50 leaf groups)"] = ev
        info["not_evaluable_classes_raw_counts_only"] = {c: int((df.class_id == c).sum()) for c in CLASSES if c not in ev and (df.class_id == c).sum() > 0}
        keep = df.class_id.isin(ev).to_numpy(); y, P, d2 = y[keep], P[keep], df[keep]
        present = [CIDX[c] for c in ev]
    else: d2, present = df, None
    m = metrics_from_probs(y, P, present); m["confidence"] = confidence_report(y, P); m["bootstrap"] = bootstrap_ci(y, P, d2.leaf_group_id.to_numpy(), 1000, 0, present)
    m["by_source"] = {s: {"n": int((d2.source_id == s).sum()), "accuracy": metrics_from_probs(y[(d2.source_id == s).to_numpy()], P[(d2.source_id == s).to_numpy()])["accuracy"]} for s in d2.source_id.unique()}
    m["by_device"] = {s: {"n": int((d2.capture_device == s).sum()), "accuracy": metrics_from_probs(y[(d2.capture_device == s).to_numpy()], P[(d2.capture_device == s).to_numpy()])["accuracy"]} for s in d2.capture_device.unique()}
    m["tier_info"] = info; res[tier] = m
    pd.DataFrame(m["confusion_matrix"], index=CLASSES, columns=CLASSES).to_csv(out_dir + rf"\{tier}_confusion_matrix.csv")
    json.dump(m, open(out_dir + rf"\{tier}_metrics.json", "w"), indent=1)
    print(tier, "n", m["n"], "acc", round(m["accuracy"], 4), "macroF1", round(m["macro_f1"], 4), {c: round(v["recall"], 3) for c, v in m["per_class"].items() if v["support"]})
