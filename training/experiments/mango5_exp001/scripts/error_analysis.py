#!/usr/bin/env python3
"""Error analysis of the SELECTED candidate (B_partial_ft_s43) on the already-run test tiers. Reads predictions only; no model is trained,
no test tier is re-scored, no label is changed. Writes experiments/mango5_exp001/error_analysis/."""
import json, os, sys
import numpy as np, pandas as pd
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(__file__))
from common import *
from sklearn.metrics import roc_auc_score

OUT = EXP + r"\error_analysis"; FIG = OUT + r"\figures"; os.makedirs(FIG, exist_ok=True)
V0 = r"D:\OneDrive - Faiyaz Personal\OneDrive\3. Shreyance related Documents\AGRILENS_5.0.0\Model_Trainer_Program\AGL-MANGO-MD\AGL-MANGO-MD-v1.0.0"
man = pd.read_csv(RC + r"\manifests\master_image_manifest.csv", low_memory=False)
cand = pd.read_csv(V0 + r"\work\candidates.csv", low_memory=False); F = np.load(V0 + r"\work\features_1280.npy"); F = F / np.maximum(np.linalg.norm(F, axis=1, keepdims=True), 1e-9)
cand["row"] = np.arange(len(cand)); key = cand.set_index(["source", "src_rel"]).row
man["crow"] = [key.get((s, p), -1) for s, p in zip(man.source_id, man.original_source_path)]
acc = man[(man.inclusion_status == "accepted")].copy()
q = lambda a: {k: float(np.percentile(a, k)) for k in (10, 25, 50, 75, 90)} if len(a) else {}


def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d; h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d; return c - h, c + h


def load(tier):
    d = pd.read_csv(EXP + rf"\test_results\{tier}_predictions.csv"); P = d[[f"p_{c}" for c in CLASSES]].to_numpy(); d["true"] = d.class_id; d["pred"] = [CLASSES[i] for i in P.argmax(1)]
    s = np.sort(P, 1)[:, ::-1]; d["conf"] = s[:, 0]; d["margin"] = s[:, 0] - s[:, 1]; d["p_true"] = [P[i, CIDX[t]] for i, t in enumerate(d.true)]; d["correct"] = d.true == d.pred
    d["abstain"] = (d.conf < CONF_T) | (d.margin < MARGIN_T)
    m = d.merge(man[["master_image_id", "crow", "width", "height", "capture_date", "original_source_path", "master_relpath"]], on="master_image_id", how="left")
    c = cand.iloc[m.crow.to_numpy()].reset_index(drop=True)
    for k in ("sharp", "lum_mean", "fg_frac", "clip_hi", "clip_lo", "border_fg"): m[k] = c[k].to_numpy()
    # colour statistics from the cached 256-px copy (centre 224 crop)
    rgb, sat = [], []
    for i in m.master_image_id:
        a = load_cached(i); h, w = a.shape[:2]; t, l = (h - 224) // 2, (w - 224) // 2; x = a[t:t + 224, l:l + 224].astype(np.float32) / 255
        rgb.append(x.reshape(-1, 3).mean(0)); mx, mn = x.max(2), x.min(2); sat.append(float(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0).mean()))
    rgb = np.array(rgb); m["mean_r"], m["mean_g"], m["mean_b"], m["mean_sat"] = rgb[:, 0], rgb[:, 1], rgb[:, 2], sat
    # label ambiguity: ten nearest same-source neighbours from other leaf groups (production feature extractor, same measure as the quarantine screen)
    pool = acc[acc.crow >= 0]; own, top = [], []
    for r in m.itertuples():
        pp = pool[(pool.source_id == r.source_id) & (pool.leaf_group_id != r.leaf_group_id)]; s = F[pp.crow.to_numpy()] @ F[r.crow]; nn = pp.class_id.to_numpy()[np.argsort(-s)[:10]]
        own.append(int((nn == r.true).sum())); top.append(pd.Series(nn).value_counts().index[0])
    m["nn_own_of_10"] = own; m["nn_top_class"] = top
    return m


H = load("test_heldout_device"); K = load("test_known_device"); H = H[H.true.isin(["MNG001", "MNG005"])].reset_index(drop=True)   # evaluable classes only
H.to_csv(OUT + r"\error_table_heldout_device.csv", index=False); K.to_csv(OUT + r"\error_table_known_device.csv", index=False)
res = {}
# ---------- per-device accuracy
def dev_tab(d):
    rows = []
    for (dev, c), g in d.groupby(["capture_device", "true"]):
        k = int(g.correct.sum()); lo, hi = wilson(k, len(g)); rows.append({"device": dev, "class": c, "n": len(g), "correct": k, "recall": k / len(g), "ci_lo": lo, "ci_hi": hi, "leaf_groups": g.leaf_group_id.nunique()})
    for dev, g in d.groupby("capture_device"):
        k = int(g.correct.sum()); lo, hi = wilson(k, len(g)); rows.append({"device": dev, "class": "ALL", "n": len(g), "correct": k, "recall": k / len(g), "ci_lo": lo, "ci_hi": hi, "leaf_groups": g.leaf_group_id.nunique()})
    return pd.DataFrame(rows)
dt_h = dev_tab(H); dt_k = dev_tab(K); dt_h.to_csv(OUT + r"\device_accuracy_heldout.csv", index=False); dt_k.to_csv(OUT + r"\device_accuracy_known.csv", index=False)
# colour of devices: train vs held-out
tr = pd.read_csv(RC + r"\splits\train.csv"); tr = tr.merge(man[["master_image_id", "width", "height"]], on="master_image_id")
def colour_stats(df):
    r = []
    for i in df.master_image_id:
        a = load_cached(i); h, w = a.shape[:2]; t, l = (h - 224) // 2, (w - 224) // 2; x = a[t:t + 224, l:l + 224].astype(np.float32) / 255; mx, mn = x.max(2), x.min(2)
        r.append((*x.reshape(-1, 3).mean(0), float(np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0).mean())))
    return pd.DataFrame(r, columns=["r", "g", "b", "sat"], index=df.index)
trs = tr.sample(1200, random_state=0); trc = colour_stats(trs); trs = pd.concat([trs, trc], axis=1)
col = pd.concat([trs.groupby(["capture_device"])[["r", "g", "b", "sat"]].mean().assign(set="train", n=trs.groupby("capture_device").size()),
                 pd.concat([H, K]).rename(columns={"mean_r": "r", "mean_g": "g", "mean_b": "b", "mean_sat": "sat"}).groupby("capture_device")[["r", "g", "b", "sat"]].mean().assign(set="test", n=pd.concat([H, K]).groupby("capture_device").size())]).reset_index()
col.to_csv(OUT + r"\device_colour_stats.csv", index=False)
# ---------- confusion cells in held-out tier
cells = {}
for a, b in (("MNG001", "MNG005"), ("MNG005", "MNG001")):
    e = H[(H.true == a) & (H.pred == b)]; allc = H[H.true == a]
    lg = H[(H.true == a)].groupby("leaf_group_id").correct.agg(["size", "sum"]); mixed = int(((lg["sum"] > 0) & (lg["sum"] < lg["size"])).sum()); allwrong = int((lg["sum"] == 0).sum())
    cells[f"{a}->{b}"] = {"errors": len(e), "of_class_images": len(allc), "distinct_leaf_groups_in_errors": int(e.leaf_group_id.nunique()), "leaf_groups_of_class": int(lg.shape[0]), "leaf_groups_all_images_wrong": allwrong, "leaf_groups_mixed_right_and_wrong": mixed,
                          "by_device": e.capture_device.value_counts().to_dict(), "by_date": e.capture_date.value_counts().to_dict(), "conf": q(e.conf), "margin": q(e.margin), "p_true": q(e.p_true),
                          "share_conf_ge_0.8": float((e.conf >= 0.8).mean()), "share_abstained_at_production_thresholds": float(e.abstain.mean()),
                          "nn_own_of_10_mean_errors": float(e.nn_own_of_10.mean()), "nn_own_of_10_mean_correct": float(allc[allc.correct].nn_own_of_10.mean()),
                          "share_errors_with_neighbour_majority_other_class(nn_own<=4)": float((e.nn_own_of_10 <= 4).mean()), "share_correct_with_neighbour_majority_other_class": float((allc[allc.correct].nn_own_of_10 <= 4).mean())}
res["heldout_cells"] = cells
# ---------- known-device: Healthy -> Gall Midge
e13 = K[(K.true == "MNG006") & (K.pred == "MNG005")]
res["healthy_to_gallmidge"] = {"errors": len(e13), "by_device": e13.capture_device.value_counts().to_dict(), "by_source": e13.source_id.value_counts().to_dict(), "by_date": e13.capture_date.value_counts().to_dict(),
    "distinct_leaf_groups": int(e13.leaf_group_id.nunique()), "conf": q(e13.conf), "margin": q(e13.margin), "p_true": q(e13.p_true), "nn_own_of_10_mean": float(e13.nn_own_of_10.mean()),
    "nn_top_class": e13.nn_top_class.value_counts().to_dict(), "sharp_median_errors": float(e13.sharp.median()), "sharp_median_all_healthy_known": float(K[K.true == "MNG006"].sharp.median()),
    "healthy_known_total": int((K.true == "MNG006").sum()), "healthy_known_by_device_total": K[K.true == "MNG006"].capture_device.value_counts().to_dict(), "abstained": float(e13.abstain.mean())}
e13.to_csv(OUT + r"\healthy_to_gallmidge_13.csv", index=False)
# ---------- confidence and margin of correct vs incorrect, per tier and class
conf = {}
for nm, d in (("known_device", K), ("heldout_device", H)):
    r = {"correct": {"n": int(d.correct.sum()), "conf": q(d[d.correct].conf), "margin": q(d[d.correct].margin)}, "incorrect": {"n": int((~d.correct).sum()), "conf": q(d[~d.correct].conf), "margin": q(d[~d.correct].margin)}}
    r["errors_with_conf_ge_0.8"] = float((d[~d.correct].conf >= 0.8).mean()); r["errors_caught_by_abstention"] = float(d[~d.correct].abstain.mean()); r["correct_wrongly_abstained"] = float(d[d.correct].abstain.mean())
    r["error_rate_all"] = float((~d.correct).mean()); r["error_rate_among_non_abstained"] = float((~d[~d.abstain].correct).mean()); r["coverage"] = float((~d.abstain).mean())
    r["auroc_conf_separates_correct_from_wrong"] = float(roc_auc_score(d.correct, d.conf)); r["auroc_margin"] = float(roc_auc_score(d.correct, d.margin))
    r["by_class"] = {c: {"errors": int((~g.correct).sum()), "conf_wrong_median": float(g[~g.correct].conf.median()) if (~g.correct).any() else None, "conf_right_median": float(g[g.correct].conf.median())} for c, g in d.groupby("true")}
    conf[nm] = r
res["confidence"] = conf
# ---------- association of errors with image quality / colour (AUROC: 0.5 = no relation)
qual = {}
for nm, d in (("known_device", K), ("heldout_device", H)):
    t = {}
    for k in ("sharp", "lum_mean", "fg_frac", "border_fg", "clip_hi", "clip_lo", "width", "mean_r", "mean_g", "mean_b", "mean_sat", "nn_own_of_10"):
        x = d[k].astype(float); ok = x.notna()
        t[k] = {"auroc_error_vs_value": float(roc_auc_score(~d.correct[ok], x[ok])) if (~d.correct[ok]).nunique() == 2 else None, "median_errors": float(x[~d.correct].median()), "median_correct": float(x[d.correct].median())}
    qual[nm] = t
res["quality_association"] = qual
# ---------- heuristic cause tags for every error (not mutually exclusive; primary = first match)
src_p10 = cand[cand.ok].groupby("source").sharp.quantile(0.10).to_dict()
def tag(r):
    t = []
    if r.sharp < src_p10[r.source_id] or r.fg_frac < 0.05 or r.clip_hi > 0.25 or r.lum_mean < 60: t.append("image_quality")
    if r.nn_own_of_10 <= 4: t.append("label_ambiguity_suspected")
    if r.conf >= 0.8 and r.nn_own_of_10 >= 7 and "image_quality" not in t: t.append("model_limitation_confident_error")
    if not t: t.append("unexplained_or_low_margin")
    return t
causes = {}
for nm, d in (("known_device", K), ("heldout_device", H)):
    e = d[~d.correct].copy(); e["tags"] = e.apply(tag, axis=1); e["primary"] = e.tags.map(lambda x: x[0]); e["tags_str"] = e.tags.map("|".join)
    e.drop(columns=["tags"]).to_csv(OUT + rf"\errors_tagged_{nm}.csv", index=False)
    causes[nm] = {"errors": len(e), "primary": e.primary.value_counts().to_dict(), "any_tag": {k: int(e.tags_str.str.contains(k).sum()) for k in ("image_quality", "label_ambiguity_suspected", "model_limitation_confident_error", "unexplained_or_low_margin")}}
    if nm == "heldout_device":
        for dv, g in e.groupby("capture_device"): causes[nm].setdefault("by_device_primary", {})[dv] = g.primary.value_counts().to_dict()
res["cause_tags"] = causes
json.dump(res, open(OUT + r"\error_analysis_stats.json", "w"), indent=1, default=str)
# ---------- representative image sheets
def sheet(d, name, title, n=12, how="conf_desc"):
    if len(d) == 0: return
    if how == "conf_desc": s = d.sort_values("conf", ascending=False).head(n)
    elif how == "margin_asc": s = d.sort_values("margin").head(n)
    elif how == "median": s = d.sort_values("conf").iloc[max(0, len(d) // 2 - n // 2):][:n]
    else: s = d.sample(min(n, len(d)), random_state=1)
    T, C = 220, 4; rows = (len(s) + C - 1) // C; S = Image.new("RGB", (C * T, rows * (T + 42) + 22), "white"); dr = ImageDraw.Draw(S); dr.text((4, 4), title, fill="black")
    for k, r in enumerate(s.itertuples()):
        a = Image.fromarray(load_cached(r.master_image_id)); a.thumbnail((T - 4, T - 4)); x, y = (k % C) * T, (k // C) * (T + 42) + 22; S.paste(a, (x + 2, y + 2))
        dr.text((x + 3, y + T), f"{r.master_image_id[7:].replace('SAR25_IMG','S')} {r.capture_device.split()[-1][:10]}", fill="black"); dr.text((x + 3, y + T + 12), f"true {r.true[3:]} pred {r.pred[3:]} conf {r.conf:.2f}", fill="darkred" if not r.correct else "darkgreen")
        dr.text((x + 3, y + T + 24), f"margin {r.margin:.2f} sharp {r.sharp:.0f} nn{r.nn_own_of_10}", fill="gray")
    S.save(FIG + rf"\{name}.jpg", quality=88)
sheet(H[(H.true == "MNG001") & (H.pred == "MNG005")], "heldout_anth_as_gm_confident", "Held-out devices: Anthracnose predicted Gall Midge (highest confidence)", 12, "conf_desc")
sheet(H[(H.true == "MNG001") & (H.pred == "MNG005")], "heldout_anth_as_gm_lowmargin", "Held-out devices: Anthracnose predicted Gall Midge (lowest margin)", 12, "margin_asc")
sheet(H[(H.true == "MNG005") & (H.pred == "MNG001")], "heldout_gm_as_anth_confident", "Held-out devices: Gall Midge predicted Anthracnose (highest confidence)", 12, "conf_desc")
sheet(H[(H.true == "MNG005") & (H.pred == "MNG001")], "heldout_gm_as_anth_lowmargin", "Held-out devices: Gall Midge predicted Anthracnose (lowest margin)", 12, "margin_asc")
sheet(H[(H.true == "MNG001") & H.correct], "heldout_anth_correct", "Held-out devices: Anthracnose correct (random)", 12, "random")
sheet(H[(H.true == "MNG005") & H.correct], "heldout_gm_correct", "Held-out devices: Gall Midge correct (random)", 12, "random")
sheet(e13, "known_healthy_as_gm", "Known devices: Healthy predicted Gall Midge (all 13, by confidence)", 13, "conf_desc")
sheet(K[(K.true == "MNG006") & K.correct], "known_healthy_correct", "Known devices: Healthy correct (random)", 12, "random")
print(json.dumps({"cells": res["heldout_cells"], "h2g": res["healthy_to_gallmidge"], "causes": res["cause_tags"]}, indent=1, default=str)); print(dt_h.round(3).to_string()); print(col.round(3).to_string())
