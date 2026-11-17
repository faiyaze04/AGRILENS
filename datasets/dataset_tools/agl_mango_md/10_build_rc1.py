#!/usr/bin/env python3
"""AGL-MANGO-MD v1.1.0-rc1 builder (five-class experimental baseline). Reads v1.0.0 (read-only) and writes the rc1 directory.
Classes: MNG001, MNG002, MNG005 (provisional), MNG006, MNG007. Not in rc1: MNG003, MNG004, MNG008, MNG009, background-removed supplementary images.
Quarantine decisions (user, 2026-11-17): keep 39 cross-class conflicts, 122 label-doubt and 45 small-leaf images quarantined; reject the 2
defocused images; the 61 proposed releases were reviewed one by one: 52 released, 9 held (see release_review_61.csv).
Split rules: unit = leaf group + copy group + capture burst (same source/class/device/day, gaps <= 60 s); five held-out devices; seed 42.
Names: train, val, test_known_device, test_heldout_device, diagnostic cross-source manifests, c270 field validation (empty placeholder).
Usage: python 10_build_rc1.py   (hashing and copying take several minutes)"""
import csv, datetime as dt, hashlib, json, os, random, shutil, sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

ROOT = r"D:\AGRILENS_Training\AGL-MANGO-MD"
V0 = ROOT + r"\AGL-MANGO-MD-v1.0.0"; RC = ROOT + r"\AGL-MANGO-MD-v1.1.0-rc1"
DEV = RC + r"\provenance\dev_artifacts"
FIVE = ["MNG001", "MNG002", "MNG005", "MNG006", "MNG007"]
FOLDER = {"MNG001": "MNG001_ANTHRACNOSE", "MNG002": "MNG002_BACTERIAL_CANKER", "MNG005": "MNG005_GALL_MIDGE", "MNG006": "MNG006_HEALTHY", "MNG007": "MNG007_POWDERY_MILDEW"}
H = {"samsung SM-A525F", "vivo V2204", "realme realme C35", "Xiaomi 23021RAAEG", "vivo V2111"}
GAP, SEED = 60, 42
FR = {"train": 0.72, "val": 0.14, "test_known_device": 0.14}
HOLD_N = {5, 6, 7, 11, 24, 36, 37, 38, 39}   # individually reviewed releases that failed (see release_review_61.csv)
HOLD_WHY = {5: "label disputed: 6/10 same-source neighbours are Gall Midge", 6: "small folded leaf, no symptom visible", 7: "small folded leaf, no symptom visible",
            11: "blurred and 4/10 neighbours are Gall Midge", 24: "label disputed: 6/10 neighbours are Turning Brown", 36: "motion blur hides the surface texture",
            37: "motion blur (sharpness 20.8)", 38: "motion blur hides the surface texture", 39: "motion blur hides the surface texture"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()


class UF:
    def __init__(s): s.p = {}
    def f(s, x):
        s.p.setdefault(x, x)
        while s.p[x] != x:
            s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def u(s, a, b):
        a, b = s.f(a), s.f(b)
        if a != b: s.p[b] = a


def ptime(r):
    v = str(r.get("exif_datetime", "") or "").strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try: return dt.datetime.strptime(v, fmt).timestamp()
        except ValueError: pass
    nt = str(r.get("name_time", "") or "")
    if nt and nt != "nan":
        try: return dt.datetime.fromisoformat(nt).timestamp()
        except ValueError: pass
    return np.nan


def main():
    for d in ("images", "quarantine", "rejected_by_review", "manifests", "splits", "reports", "docs"):
        os.makedirs(os.path.join(RC, d), exist_ok=True)
    m = pd.read_csv(V0 + r"\manifests\master_image_manifest.csv", low_memory=False)
    f5 = m[m.class_id.isin(FIVE)].copy()
    f5["v1_0_0_status"] = f5.inclusion_status; f5["v1_0_0_relpath"] = f5.master_relpath
    prep = pd.read_csv(DEV + r"\review_worksheets\release_review_61_prep.csv")
    prep["decision"] = np.where(prep.n.isin(HOLD_N), "HOLD", "RELEASE")
    prep["decision_note"] = prep.n.map(lambda n: HOLD_WHY.get(n, "image quality adequate, label not disputed (neighbours agree, no cross-class evidence)"))
    prep[["n", "master_image_id", "class_id", "source_id", "reasons", "sharpness", "fg_fraction", "nn_dist", "nn_disputed", "decision", "decision_note"]].to_csv(RC + r"\reports\release_review_61.csv", index=False)
    release = set(prep[prep.decision == "RELEASE"].master_image_id); hold9 = set(prep[prep.decision == "HOLD"].master_image_id)
    disp = pd.read_csv(DEV + r"\baseline_5class_candidate_pre_review\reports\quarantine_disposition.csv").set_index("master_image_id")
    status, hold, note = [], [], []
    for r in f5.itertuples():
        s, h, n = r.inclusion_status, "", ""
        if s == "quarantined":
            if r.source_id == "LEGACY": s, h = "outside_baseline_legacy_background_removed", "HOLD_out_of_scope"
            else:
                pd_ = disp.loc[r.master_image_id, "proposed_disposition"]
                if r.master_image_id in release: s, n = "accepted", "released from quarantine after individual review (rc1)"
                elif pd_ == "PROPOSE_REJECT_defocused": s, h, n = "rejected", "", "rejected: defocused (user decision)"
                elif r.master_image_id in hold9: h, n = "HOLD_individual_review_failed", "release candidate that failed individual review"
                else: h = pd_.replace("HOLD_unreviewed_small_leaf", "HOLD_small_leaf")
        elif s == "accepted_supplementary": s = "outside_baseline_supplementary_background_removed"
        status.append(s); hold.append(h); note.append(n)
    f5["inclusion_status"] = status; f5["quarantine_hold"] = hold; f5["rc1_note"] = note
    # ---- copy files
    jobs = []
    newrel = {}
    for r in f5.itertuples():
        if r.inclusion_status == "accepted": sub = "images"
        elif r.inclusion_status == "quarantined": sub = "quarantine"
        elif r.inclusion_status == "rejected" and r.rc1_note.startswith("rejected: defocused"): sub = "rejected_by_review"
        else: continue
        src = os.path.join(V0, r.v1_0_0_relpath.replace("/", os.sep)); name = os.path.basename(r.v1_0_0_relpath)
        rel = f"{sub}/{FOLDER[r.class_id]}/{name}" if sub != "rejected_by_review" else f"{sub}/{name}"
        newrel[r.master_image_id] = rel; jobs.append((src, os.path.join(RC, rel.replace("/", os.sep)), r.sha256))
    f5["master_relpath"] = f5.master_image_id.map(newrel).fillna("")

    def cp(j):
        s, d, h = j; os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.exists(d): os.chmod(d, 0o666)
        shutil.copyfile(s, d); return sha(d) == h
    with ThreadPoolExecutor(8) as ex: ok = list(ex.map(cp, jobs))
    print("copied", len(jobs), "mismatches", ok.count(False), flush=True); assert all(ok)
    # ---- splits
    c = pd.read_csv(V0 + r"\work\candidates.csv", low_memory=False); c["t"] = c.apply(ptime, axis=1)
    f5 = f5.merge(c[["source", "src_rel", "t"]].rename(columns={"source": "source_id", "src_rel": "original_source_path"}), on=["source_id", "original_source_path"], how="left")
    a = f5[f5.inclusion_status == "accepted"].copy().reset_index(drop=True)
    a["burst"] = ""
    for k, g in a.groupby(["source_id", "class_id", "capture_device", "capture_date"]):
        g = g[g.t.notna()].sort_values("t")
        if g.empty: continue
        b = (g.t.diff() > GAP).cumsum()
        for i, bb in zip(g.index, b): a.at[i, "burst"] = "B|" + "|".join(map(str, k)) + f"|{bb}"
    uf = UF()
    for r in a.itertuples():
        uf.u("L" + r.leaf_group_id, "C" + r.duplicate_group_id)
        if r.burst: uf.u("L" + r.leaf_group_id, r.burst)
    a["unit"] = [uf.f("L" + r.leaf_group_id) for r in a.itertuples()]
    a["is_H"] = a.capture_device.isin(H)
    ug = a.groupby("unit").agg(n=("is_H", "size"), nH=("is_H", "sum"), c=("class_id", "first"), ncls=("class_id", "nunique"), src=("source_id", lambda x: Counter(x).most_common(1)[0][0]))
    assert (ug.ncls == 1).all()
    dev_units = set(ug.index[ug.nH == ug.n])
    rng = random.Random(SEED); assign = {u: "test_heldout_device" for u in dev_units}
    for (cl, sr), g in ug[~ug.index.isin(dev_units)].groupby(["c", "src"]):
        keys = list(g.index); rng.shuffle(keys); keys.sort(key=lambda k: -g.n[k]); tot = int(g.n.sum()); cur = Counter()
        for k in keys:
            s = max(FR, key=lambda s: FR[s] * tot - cur[s]); cur[s] += int(g.n[k]); assign[k] = s
    a["split"] = a.unit.map(assign)
    excl = a.is_H & ~a.unit.isin(dev_units)
    a.loc[excl, "split"] = "excluded_cross_device_leaf"
    cols = ["master_image_id", "class_id", "split", "source_id", "capture_device", "capture_date", "leaf_group_id", "duplicate_group_id", "unit", "master_relpath"]
    a[cols].to_csv(RC + r"\splits\split_assignment.csv", index=False)
    use = a[a.split != "excluded_cross_device_leaf"]
    for s in list(FR) + ["test_heldout_device"]: use[use.split == s][cols].to_csv(RC + rf"\splits\{s}.csv", index=False)
    a[a.split == "excluded_cross_device_leaf"][cols].to_csv(RC + r"\splits\excluded_cross_device_leaf.csv", index=False)
    pd.DataFrame(columns=["image_id", "class_id", "leaf_id", "tree_id", "session_id", "capture_device", "capture_date", "capture_conditions", "path", "expert_label", "expert_id", "verification_status"]).to_csv(RC + r"\splits\c270_field_validation_manifest.csv", index=False)
    # augmented / derivative family inheritance
    leaf_split = use.groupby("leaf_group_id").split.agg(set); copy_split = use.groupby("duplicate_group_id").split.agg(set)
    fam = f5[f5.original_or_augmented.isin(["augmented", "derivative"]) | (f5.inclusion_status.str.startswith("outside") & (f5.source_id == "LEGACY"))].copy()
    fam["family_split"] = fam.leaf_group_id.map(lambda g: next(iter(leaf_split[g])) if g in leaf_split.index and len(leaf_split[g]) == 1 else "none (no member in any split)")
    fam[["master_image_id", "class_id", "inclusion_status", "original_or_augmented", "legacy_parent", "leaf_group_id", "family_split"]].to_csv(RC + r"\splits\derivative_and_augmented_family_inheritance.csv", index=False)
    pid = f5.set_index("master_image_id").leaf_group_id
    aug = f5[f5.original_or_augmented == "augmented"]
    aug_parent_ok = int(sum(1 for r in aug.itertuples() if (not r.legacy_parent) or (r.legacy_parent in pid.index and pid[r.legacy_parent] == r.leaf_group_id)))
    leak = {"leaf_groups_in_more_than_one_split": int((leaf_split.map(len) > 1).sum()), "copy_groups_in_more_than_one_split": int((copy_split.map(len) > 1).sum()),
            "units_in_more_than_one_split": int((use.groupby("unit").split.nunique() > 1).sum()),
            "bursts_in_more_than_one_split": int((use[use.burst != ""].groupby("burst").split.nunique() > 1).sum()),
            "heldout_devices_in_train_val_test_known": sorted(set(use[use.split.isin(["train", "val", "test_known_device"])].capture_device) & H),
            "augmented_records": int(len(aug)), "augmented_records_unlinked_no_parent_found": int(aug.legacy_parent.isna().sum()),
            "augmented_records_linked_to_parent": int(aug.legacy_parent.notna().sum()), "augmented_linked_whose_leaf_group_equals_parent_leaf_group": aug_parent_ok,
            "augmented_linked_family_in_a_split": int(fam[(fam.original_or_augmented == "augmented") & fam.legacy_parent.notna() & ~fam.family_split.str.startswith("none")].shape[0]),
            "heldout_device_images_excluded_from_mixed_units": int(excl.sum())}
    # diagnostics
    hold_ = {}
    for A, Bs, cl in (("SAR25", "MANGOLEAFBD", ["MNG001", "MNG005", "MNG006", "MNG007"]), ("MANGOLEAFBD", "SAR25", ["MNG001", "MNG005", "MNG006", "MNG007"]),
                      ("MANGOLEAFBD", "ABCGMP", ["MNG002", "MNG006"]), ("ABCGMP", "MANGOLEAFBD", ["MNG002", "MNG006"])):
        x = a[a.class_id.isin(cl) & a.source_id.isin([A, Bs])]
        shared = set(x[x.source_id == A].unit) & set(x[x.source_id == Bs].unit)
        x = x[~((x.source_id == Bs) & x.unit.isin(shared))].copy(); x["role"] = x.source_id.map(lambda s: "train" if s == A else "test")
        x[["master_image_id", "class_id", "role", "source_id", "capture_device", "leaf_group_id", "master_relpath"]].to_csv(RC + rf"\splits\diagnostic_crosssource_train_{A}_test_{Bs}.csv", index=False)
        hold_[f"{A}->{Bs}"] = {"train_images": int((x.role == "train").sum()), "test_images": int((x.role == "test").sum()), "per_class_test": x[x.role == "test"].class_id.value_counts().to_dict(),
                               "test_images_removed_for_shared_groups": int(a[a.class_id.isin(cl) & (a.source_id == Bs) & a.unit.isin(shared)].shape[0])}
    # evaluability of held-out-device claims
    ev = {}
    for cl in FIVE:
        t = use[(use.class_id == cl) & (use.split == "test_heldout_device")]
        ev[cl] = {"heldout_device_images": int(len(t)), "heldout_device_leaf_groups": int(t.leaf_group_id.nunique()), "devices": sorted(t.capture_device.unique()),
                  "adequate_for_device_independence_claim": bool(len(t) >= 100 and t.leaf_group_id.nunique() >= 50)}
    # tables
    a2 = use.copy(); a2["size"] = a2.width.astype(int).astype(str) + "x" + a2.height.astype(int).astype(str); a2["month"] = a2.capture_date.str[:7]
    tab = a.groupby(["class_id", "split"]).agg(images=("master_image_id", "size"), leaf_groups=("leaf_group_id", "nunique"), units=("unit", "nunique"), devices=("capture_device", "nunique"),
                                              sources=("source_id", lambda x: ",".join(f"{k}:{v}" for k, v in sorted(Counter(x).items())))).reset_index()
    tab.to_csv(RC + r"\reports\split_composition_by_class.csv", index=False)
    a.groupby(["class_id", "split", "capture_device"]).size().reset_index(name="images").to_csv(RC + r"\reports\split_composition_by_device.csv", index=False)
    a.groupby(["class_id", "source_id", "capture_device", a.capture_date.str[:7].rename("month")]).agg(images=("master_image_id", "size"), leaf_groups=("leaf_group_id", "nunique"), capture_days=("capture_date", "nunique"),
        bursts=("burst", lambda x: x[x != ""].nunique()), heldout_device=("is_H", "first")).reset_index().to_csv(RC + r"\reports\distribution_class_source_device_month.csv", index=False)
    pcs = a.groupby(["class_id", "source_id"]).agg(images=("master_image_id", "size"), leaf_groups=("leaf_group_id", "nunique"), devices=("capture_device", "nunique"), capture_days=("capture_date", "nunique"), bursts=("burst", lambda x: x[x != ""].nunique())).reset_index()
    pcs.to_csv(RC + r"\reports\per_class_source_summary.csv", index=False)

    def acc(df, keys):
        g = df.groupby(keys).class_id.agg(lambda s: s.value_counts().iloc[0]); return [round(float(g.sum() / len(df)), 4), int(len(g))]
    sar = a2[a2.source_id == "SAR25"]; ml = a2[a2.source_id == "MANGOLEAFBD"]
    short = {"population": "images in splits", "n": int(len(a2)), "majority_baseline": round(float(a2.class_id.value_counts().iloc[0] / len(a2)), 4),
             "class_from_source": acc(a2, ["source_id"]), "class_from_device": acc(a2, ["capture_device"]), "class_from_source_device": acc(a2, ["source_id", "capture_device"]),
             "class_from_device_size": acc(a2, ["capture_device", "size"]), "class_from_device_size_month": acc(a2, ["capture_device", "size", "month"]),
             "SAR_only_class_from_device": acc(sar, ["capture_device"]), "SAR_only_baseline": round(float(sar.class_id.value_counts().iloc[0] / len(sar)), 4),
             "MLBD_only_class_from_device": acc(ml, ["capture_device"]), "MLBD_only_baseline": round(float(ml.class_id.value_counts().iloc[0] / len(ml)), 4)}
    # manifests
    f5["rc1_split"] = f5.master_image_id.map(a.set_index("master_image_id").split).fillna("")
    spg = f5[f5.inclusion_status == "accepted"].groupby("leaf_group_id").source_id.nunique()
    f5["cross_source_shared_leaf_group"] = f5.leaf_group_id.isin(set(spg[spg > 1].index)) & (f5.inclusion_status == "accepted")
    f5["dataset_version"] = "v1.1.0-rc1"
    mcols = [x for x in f5.columns if x not in ("t",)]
    f5[mcols].to_csv(RC + r"\manifests\master_image_manifest.csv", index=False)
    q = f5[f5.inclusion_status.isin(["quarantined"]) | (f5.rc1_note.str.startswith("rejected: defocused")) | f5.master_image_id.isin(release)]
    qd = q.copy(); qd["final_decision"] = np.where(qd.master_image_id.isin(release), "RELEASED_to_accepted (individual review)", np.where(qd.inclusion_status == "rejected", "REJECTED (defocused)", "HELD in quarantine"))
    qd["hold_category"] = qd.quarantine_hold
    qd["decision_basis"] = qd.master_image_id.map(lambda i: prep.set_index("master_image_id").decision_note.get(i, "user decision 2026-11-17 on category"))
    qd[["master_image_id", "class_id", "source_id", "v1_0_0_status", "reasons", "final_decision", "hold_category", "decision_basis", "master_relpath"]].to_csv(RC + r"\manifests\quarantine_decisions.csv", index=False)
    f5[f5.inclusion_status == "quarantined"][mcols].to_csv(RC + r"\manifests\quarantine_manifest.csv", index=False)
    dup = pd.read_csv(V0 + r"\manifests\duplicate_report.csv"); ids = set(f5.master_image_id)
    dup[dup.image_a.isin(ids) & dup.image_b.isin(ids)].to_csv(RC + r"\manifests\duplicate_report.csv", index=False)
    cm = pd.read_csv(V0 + r"\manifests\class_mapping.csv")
    cm[cm.class_id.isin(FIVE) | cm.source_id.eq("C270")].to_csv(RC + r"\manifests\class_mapping.csv", index=False)
    stat = {"dataset_id": "AGL-MANGO-MD", "version": "v1.1.0-rc1", "per_class": {}}
    for cl in FIVE:
        R = f5[f5.class_id == cl]; A_ = R[R.inclusion_status == "accepted"]
        stat["per_class"][cl] = {"records": int(len(R)), "by_status": R.inclusion_status.value_counts().to_dict(), "accepted": int(len(A_)), "accepted_leaf_groups": int(A_.leaf_group_id.nunique()),
                                 "accepted_by_source": A_.source_id.value_counts().to_dict(), "accepted_by_device": A_.capture_device.value_counts().to_dict(),
                                 "in_splits": use[use.class_id == cl].split.value_counts().to_dict(), "excluded_cross_device_leaf": int((a[a.class_id == cl].split == "excluded_cross_device_leaf").sum()),
                                 "quarantine_holds": R[R.inclusion_status == "quarantined"].quarantine_hold.value_counts().to_dict()}
    stat["totals"] = {"records": int(len(f5)), "by_status": f5.inclusion_status.value_counts().to_dict(), "accepted_images_on_disk": int((f5.inclusion_status == "accepted").sum()),
                      "images_in_splits": int(len(use)), "by_split": use.split.value_counts().to_dict(), "excluded_cross_device_leaf": int(excl.sum())}
    ov = f5[f5.cross_source_shared_leaf_group]
    stat["cross_source_overlap"] = {"note": "ABCGMP images share leaf groups with MangoLeafBD images (same leaves/photographs, resized). The two are not independent sources for these classes.",
                                    "leaf_groups": int(ov.leaf_group_id.nunique()), "images_by_class_source": {f"{k[0]}|{k[1]}": int(v) for k, v in ov.groupby(["class_id", "source_id"]).size().items()}}
    stat["metadata_shortcut_risk"] = short; stat["leakage_checks"] = leak; stat["heldout_device_evaluability"] = ev; stat["cross_source_diagnostics"] = hold_
    json.dump(stat, open(RC + r"\manifests\dataset_statistics.json", "w"), indent=1, default=str)
    json.dump({"seed": SEED, "burst_gap_s": GAP, "heldout_devices": sorted(H), "leakage_checks": leak, "heldout_device_evaluability": ev}, open(RC + r"\reports\split_checks.json", "w"), indent=1, default=str)
    print(json.dumps({"totals": stat["totals"], "leak": leak, "ev": ev, "short": short}, indent=1, default=str))
    pd.set_option("display.width", 250); print(tab.to_string()); print(pcs.to_string())
    print(f5.groupby(["class_id", "inclusion_status"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
