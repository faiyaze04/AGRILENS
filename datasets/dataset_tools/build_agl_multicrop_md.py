#!/usr/bin/env python3
"""Build AGL-MULTICROP-MD 1.0.0, the authoritative four-crop master dataset for AGRILENS.

Sources (all READ ONLY; never modified):
  * Mango : AGL-MANGO-MD v1.0.0 (nine-class master) and AGL-MANGO-MD v1.1.0-rc1 (five-class baseline: quarantine decisions and splits)
  * Apple : Plant Pathology 2020 images from Datasets.zip (verified extract; see extract_source_archive.py)
  * Potato, Tomato : PlantVillage images from the same verified extract of Datasets.zip
  * earlier read-only analysis: reports/orig/all_images_inventory.csv (SHA-256, dHash, size), <crop>_clusters.csv (near-duplicate groups),
    reference/plantvillage_leaf_map.json (public PlantVillage leaf identities)

Rules
  * Every source image gets one manifest record and one inclusion status:
      accepted                       training-eligible, has a split
      accepted_excluded_from_splits  accepted, kept out of every split (protects the held-out-device test; inherited from AGL-MANGO-MD rc1)
      quarantined                    copied to quarantine/, never in a split (uncertain label, provisional class or mapping, cross-class duplicate, quality)
      supplementary                  copied to supplementary/, never in a split by default (background-removed legacy Mango images)
      rejected                       not copied (exact within-class duplicate, defocused, legacy derivative, no visible leaf); the original stays in its source
      excluded_augmented             record only; augmented copy of another image, never an independent leaf, never copied
  * Group identifiers keep copies of one leaf together: Mango leaf groups and copy groups from AGL-MANGO-MD; PlantVillage leaf identity from the
    public leaf map united with hash near-duplicate clusters; Apple hash near-duplicate clusters. A split unit never crosses splits.
  * Mango splits are inherited unchanged from AGL-MANGO-MD rc1 for MNG001, MNG002, MNG005 (MangoLeafBD part), MNG006, MNG007, so the frozen
    test tiers keep their meaning. MNG003, MNG004, MNG008 are split with the same rule (leaf group + copy group + 60 s capture burst, seed 42).
  * Apple, Potato, Tomato: split units = groups, stratified per class about 70/15/15, seed 42.
  * Images are COPIED (not hard-linked: hard links share attributes and ACLs with the frozen AGL-MANGO-MD releases) and SHA-256-verified.
Usage: python build_agl_multicrop_md.py --out <dataset root> [--no-copy]
"""
import argparse, csv, datetime as dt, hashlib, json, os, random, re, shutil, sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

VERSION = "1.0.0"; DATASET_ID = "AGL-MULTICROP-MD"; SEED = 42
AGRI = r"d:\OneDrive - Faiyaz Personal\OneDrive\3. Shreyance related Documents\AgriLens"
DS = r"D:\AGRILENS_Training\datasets\source_extracts\Datasets.zip_87a22c46\datasets"  # verified extract of Datasets.zip (sha256 87a22c46...e977); the extracted AgriLens\datasets folder no longer exists
ORIG = r"D:\AGRILENS_Training\mango_sar_mld1\reports\orig"; REF = r"D:\AGRILENS_Training\mango_sar_mld1\reference"
V0 = r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.0.0"; RC = r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.1.0-rc1"
CROP_FOLDER = {"Apple": "apple dataset", "Potato": "Potato Dataset", "Tomato": "Tomato dataset"}
H_DEVICES = {"samsung SM-A525F", "vivo V2204", "realme realme C35", "Xiaomi 23021RAAEG", "vivo V2111"}

# class taxonomy: model_index follows the production labels.txt order exactly (labels.txt stays byte-identical)
TAX = [  # class_id, crop, model_label, display_name, source labels
    ("APL001", "Apple", "Apple_Rust", "Apple Rust", ["Apple_Rust"]), ("APL002", "Apple", "Apple_Scab", "Apple Scab", ["Apple_Scab"]), ("APL003", "Apple", "Apple_healthy", "Apple Healthy", ["Apple_healthy"]),
    ("MNG001", "Mango", "Mango_Anthracnose", "Mango Anthracnose", ["MNG001"]), ("MNG002", "Mango", "Mango_Bacterial_Canker", "Mango Bacterial Canker", ["MNG002"]),
    ("MNG003", "Mango", "Mango_Cutting_Weevil", "Mango Cutting Weevil", ["MNG003"]), ("MNG004", "Mango", "Mango_Die_Back", "Mango Die Back", ["MNG004"]),
    ("MNG005", "Mango", "Mango_Gall_Midge", "Mango Gall Midge", ["MNG005"]), ("MNG006", "Mango", "Mango_Healthy", "Mango Healthy", ["MNG006"]),
    ("MNG007", "Mango", "Mango_Powdery_Mildew", "Mango Powdery Mildew", ["MNG007"]), ("MNG008", "Mango", "Mango_Sooty_Mould", "Mango Sooty Mould", ["MNG008"]),
    ("POT001", "Potato", "Potato_Early_blight", "Potato Early Blight", ["Potato_Early_blight"]), ("POT002", "Potato", "Potato_Late_blight", "Potato Late Blight", ["Potato_Late_blight"]),
    ("POT003", "Potato", "Potato_healthy", "Potato Healthy", ["Potato_healthy"]),
    ("TOM001", "Tomato", "Tomato_Bacterial_spot", "Tomato Bacterial Spot", ["Tomato_Bacterial_spot"]), ("TOM002", "Tomato", "Tomato_Early_blight", "Tomato Early Blight", ["Tomato_Early_blight"]),
    ("TOM003", "Tomato", "Tomato_Late_blight", "Tomato Late Blight", ["Tomato_Late_blight"]), ("TOM004", "Tomato", "Tomato_Leaf_Mold", "Tomato Leaf Mould", ["Tomato_Leaf_Mold"]),
    ("TOM005", "Tomato", "Tomato_Septoria_leaf_spot", "Tomato Septoria Leaf Spot", ["Tomato_Septoria_leaf_spot"]),
    ("TOM006", "Tomato", "Tomato_Spider_mites_Two_spotted_spider_mite", "Tomato Spider Mites (Two-spotted)", ["Tomato_Spider_mites_Two_spotted_spider_mite"]),
    ("TOM007", "Tomato", "Tomato_Target_Spot", "Tomato Target Spot", ["Tomato_Target_Spot"]), ("TOM008", "Tomato", "Tomato_Tomato_YellowLeaf_Curl_Virus", "Tomato Yellow Leaf Curl Virus", ["Tomato_Tomato_YellowLeaf_Curl_Virus"]),
    ("TOM009", "Tomato", "Tomato_Tomato_mosaic_virus", "Tomato Mosaic Virus", ["Tomato_Tomato_mosaic_virus"]), ("TOM010", "Tomato", "Tomato_healthy", "Tomato Healthy", ["Tomato_healthy"]),
]
NOT_IN_MODEL = [("MNG009", "Mango", "", "Mango Turning Brown (provisional)", ["MNG009"])]
FOLDER = {c[0]: f"{c[0]}_{re.sub(r'[^A-Za-z0-9]+', '_', c[3].replace('(provisional)', '').strip()).strip('_').upper()}" for c in TAX + NOT_IN_MODEL}
LABEL_OF = {c[4][0]: c[0] for c in TAX if c[1] != "Mango"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


class UF:
    def __init__(s): s.p = {}
    def f(s, x):
        s.p.setdefault(x, x)
        while s.p[x] != x: s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def u(s, a, b):
        a, b = s.f(a), s.f(b)
        if a != b: s.p[b] = a


def ptime(exif, name_time):
    v = str(exif or "").strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try: return dt.datetime.strptime(v, fmt).timestamp()
        except ValueError: pass
    nt = str(name_time or "")
    if nt and nt != "nan":
        try: return dt.datetime.fromisoformat(nt).timestamp()
        except ValueError: pass
    return np.nan


def split_units(df, unit_col, strat_cols, frac, seed, names):
    """Assign whole units to splits, stratified per stratum, largest units first, filling towards the target fractions."""
    rng = random.Random(seed); assign = {}
    ug = df.groupby(unit_col).agg(n=(unit_col, "size"), **{c: (c, "first") for c in strat_cols})
    for _, g in ug.groupby(strat_cols):
        keys = list(g.index); rng.shuffle(keys); keys.sort(key=lambda k: -g.n[k]); tot = int(g.n.sum()); cur = Counter()
        for k in keys:
            s = max(names, key=lambda s: frac[s] * tot - cur[s]); cur[s] += int(g.n[k]); assign[k] = s
    return df[unit_col].map(assign)


# ----------------------------------------------------------------------------------------------------------------- Mango
def mango_records():
    v0 = pd.read_csv(V0 + r"\manifests\master_image_manifest.csv", low_memory=False)
    rc = pd.read_csv(RC + r"\manifests\master_image_manifest.csv", low_memory=False)
    sa = pd.read_csv(RC + r"\splits\split_assignment.csv")
    rc_split = dict(zip(sa.master_image_id, sa.split)); rc_unit = dict(zip(sa.master_image_id, sa.unit))
    rcs = rc.set_index("master_image_id"); recs = []
    cand = pd.read_csv(V0 + r"\work\candidates.csv", low_memory=False); tmap = {(r.source, r.src_rel): ptime(r.exif_datetime, r.name_time) for r in cand.itertuples()}
    for r in v0.itertuples():
        cid = r.class_id; rec = {"image_id": r.master_image_id, "crop": "Mango", "class_id": cid, "source_class_label": r.source_class_label, "source_dataset": r.original_source_dataset,
               "source_id": r.source_id, "original_filename": r.original_filename, "original_source_path": r.original_source_path, "sha256": r.sha256, "width": r.width, "height": r.height,
               "capture_device": r.capture_device, "capture_date": r.capture_date, "original_or_augmented": r.original_or_augmented, "copy_group_id": f"MNG:{r.duplicate_group_id}" if isinstance(r.duplicate_group_id, str) else "",
               "leaf_group_id": f"MNG:{r.leaf_group_id}" if isinstance(r.leaf_group_id, str) else "", "licence": r.licence_flag, "flags": r.flags if isinstance(r.flags, str) else "",
               "label_verification_status": r.label_verification_status, "provenance_release": "AGL-MANGO-MD v1.0.0", "file_source_path": "", "status": "", "reason": "", "split": "", "split_unit": "",
               "capture_time_epoch": tmap.get((r.source_id, r.original_source_path), np.nan)}
        if cid in ("MNG001", "MNG002", "MNG005", "MNG006", "MNG007"):
            q = rcs.loc[r.master_image_id]; st = q.inclusion_status; rec["provenance_release"] = "AGL-MANGO-MD v1.1.0-rc1"
            if st == "accepted":
                rec["file_source_path"] = os.path.join(RC, q.master_relpath.replace("/", os.sep)); sp = rc_split.get(r.master_image_id, "")
                rec["split_unit"] = f"MNGRC:{rc_unit.get(r.master_image_id, '')}"
                if cid == "MNG005" and r.source_id == "SAR25":
                    rec["status"], rec["reason"] = "quarantined", "provisional source-label mapping SAR 'Golmichi' -> Gall Midge; pending expert review (MangoLeafBD Gall Midge used for training)"
                elif sp == "excluded_cross_device_leaf":
                    rec["status"], rec["reason"] = "accepted_excluded_from_splits", "leaf photographed by a held-out device and a training device (inherited from AGL-MANGO-MD rc1)"
                else: rec["status"], rec["split"] = "accepted", sp
                if q.rc1_note and isinstance(q.rc1_note, str) and "released" in q.rc1_note: rec["flags"] = (rec["flags"] + "|released_from_quarantine_after_review").strip("|")
            elif st == "quarantined":
                rec["status"], rec["reason"] = "quarantined", f"{q.quarantine_hold}: {q.reasons}"; rec["file_source_path"] = os.path.join(RC, q.master_relpath.replace("/", os.sep))
            elif st == "rejected":
                rec["status"], rec["reason"] = "rejected", (q.rc1_note if isinstance(q.rc1_note, str) and q.rc1_note else q.reasons)
            elif st == "outside_baseline_supplementary_background_removed":
                rec["status"], rec["reason"] = "supplementary", "background-removed legacy image (not training-eligible by default)"; rec["file_source_path"] = os.path.join(V0, r.master_relpath.replace("/", os.sep))
            elif st == "outside_baseline_legacy_background_removed":
                rec["status"], rec["reason"] = "quarantined", f"background-removed legacy image held in quarantine in AGL-MANGO-MD v1.0.0: {r.reasons}"; rec["file_source_path"] = os.path.join(V0, r.master_relpath.replace("/", os.sep))
            elif st == "excluded_augmented": rec["status"], rec["reason"] = "excluded_augmented", r.reasons
            else: raise SystemExit(f"unknown rc1 status {st}")
        elif cid == "MNG009":
            if r.inclusion_status in ("rejected", "excluded_augmented"): rec["status"], rec["reason"] = r.inclusion_status, r.reasons
            else:
                rec["status"], rec["reason"] = "quarantined", "provisional class Turning Brown (symptom, not a diagnosis); not in taxonomy 1.0.0; pending expert definition"
                rec["file_source_path"] = os.path.join(V0, r.master_relpath.replace("/", os.sep))
        else:  # MNG003, MNG004, MNG008 from v1.0.0
            st = r.inclusion_status; rel = r.master_relpath if isinstance(r.master_relpath, str) else ""
            if st == "accepted": rec["status"] = "accepted"; rec["file_source_path"] = os.path.join(V0, rel.replace("/", os.sep))
            elif st == "accepted_supplementary": rec["status"], rec["reason"] = "supplementary", "background-removed legacy image (not training-eligible by default)"; rec["file_source_path"] = os.path.join(V0, rel.replace("/", os.sep))
            elif st == "quarantined": rec["status"], rec["reason"] = "quarantined", r.reasons; rec["file_source_path"] = os.path.join(V0, rel.replace("/", os.sep))
            else: rec["status"], rec["reason"] = st, r.reasons
        rec["capture_session_id"] = f"{r.source_id}|{r.capture_device}|{r.capture_date}"
        recs.append(rec)
    m = pd.DataFrame(recs)
    # splits for MNG003/004/008 with the rc1 rule (leaf group + copy group + 60 s capture burst)
    sub = m[(m.class_id.isin(["MNG003", "MNG004", "MNG008"])) & (m.status == "accepted")].copy(); sub["burst"] = ""
    for k, g in sub.groupby(["source_id", "class_id", "capture_device", "capture_date"]):
        g = g[g.capture_time_epoch.notna()].sort_values("capture_time_epoch")
        if g.empty: continue
        b = (g.capture_time_epoch.diff() > 60).cumsum()
        for i, bb in zip(g.index, b): sub.at[i, "burst"] = "B|" + "|".join(map(str, k)) + f"|{bb}"
    uf = UF()
    for r in sub.itertuples():
        uf.u("L" + r.leaf_group_id, "C" + r.copy_group_id)
        if r.burst: uf.u("L" + r.leaf_group_id, r.burst)
    sub["unit"] = ["MNGNEW:" + uf.f("L" + r.leaf_group_id) for r in sub.itertuples()]
    assert not (set(sub.capture_device) & H_DEVICES)
    sub["split"] = split_units(sub, "unit", ["class_id", "source_id"], {"train": 0.72, "val": 0.14, "test_known_device": 0.14}, SEED, ["train", "val", "test_known_device"])
    m.loc[sub.index, "split"] = sub.split; m.loc[sub.index, "split_unit"] = sub.unit
    return m


# ----------------------------------------------------------------------------------------------------- Apple, Potato, Tomato
def other_records():
    inv = pd.read_csv(ORIG + r"\all_images_inventory.csv"); inv = inv[inv.crop.isin(["Apple", "Potato", "Tomato"])].copy()
    cl = pd.concat([pd.read_csv(ORIG + rf"\{c.lower()}_clusters.csv") for c in ("Apple", "Potato", "Tomato")])
    inv = inv.merge(cl[["crop", "rel", "cluster_id"]], on=["crop", "rel"], how="left"); assert inv.cluster_id.notna().all()
    leaf = json.load(open(REF + r"\plantvillage_leaf_map.json")); recs = []; counter = Counter()
    pv_hit = Counter()
    for r in inv.sort_values(["crop", "label", "rel"]).itertuples():
        cid = LABEL_OF[r.label]; counter[cid] += 1; src = "PP2020" if r.crop == "Apple" else "PLANTVILLAGE"
        iid = f"{cid}_{src}_IMG{counter[cid]:06d}"; key = ""; leaf_id = ""
        if r.crop != "Apple":
            m = re.search(r"___(.+)\.[A-Za-z]+$", r.name)
            if m:
                key = m.group(1).strip().lower(); v = leaf.get(key)
                if v:
                    cands = [x for x in v if x.split(":::")[0].replace("___", "_").replace(" ", "_").lower().startswith(r.crop.lower())]
                    if cands: leaf_id = "PVLEAF:" + cands[0]; pv_hit[r.crop] += 1
        sess = ""
        if r.crop != "Apple":
            m2 = re.search(r"___(.+?)\s*\d+(\.[A-Za-z]+)?$", r.name); sess = f"PV|{m2.group(1).strip()}" if m2 else "PV|unknown"
        recs.append({"image_id": iid, "crop": r.crop, "class_id": cid, "source_class_label": r.class_folder, "source_id": src,
                     "source_dataset": "Plant Pathology 2020 (FGVC7, Kaggle) as held in AgriLens/datasets/apple dataset" if src == "PP2020" else "PlantVillage (color) as held in AgriLens/datasets",
                     "original_filename": r.name, "original_source_path": f"{CROP_FOLDER[r.crop]}/{r.rel.replace(os.sep, '/')}", "sha256": r.sha256, "width": r.w, "height": r.h,
                     "capture_device": "unknown (no EXIF; Plant Pathology 2020 field photographs)" if src == "PP2020" else "unknown (no EXIF; PlantVillage laboratory capture)",
                     "capture_date": "unknown", "capture_session_id": sess or "unknown", "original_or_augmented": "original_photo",
                     "copy_group_id": f"{r.crop[:3].upper()}:{r.cluster_id}", "leaf_group_id": leaf_id, "pv_key": key, "brightness": r.brightness, "focus_lapvar": r.focus_lapvar,
                     "licence": "CC BY-SA 3.0 (PlantVillage)" if src == "PLANTVILLAGE" else "Plant Pathology 2020 Kaggle competition data (terms not verified)",
                     "flags": "", "label_verification_status": "source_label_unverified", "provenance_release": "Datasets.zip sha256 87a22c4647b515865c6eb12aafd71e77d93f4d83ea108b8bb18c0434d718e977 (member datasets/" + CROP_FOLDER[r.crop] + "/...), verified per file against the inventory",
                     "file_source_path": os.path.join(DS, CROP_FOLDER[r.crop], r.rel), "status": "accepted", "reason": "", "split": "", "split_unit": ""})
    o = pd.DataFrame(recs)
    # leaf groups: PlantVillage leaf identity united with hash clusters; Apple: hash clusters
    uf = UF()
    for r in o.itertuples():
        uf.u("C" + r.copy_group_id, "C" + r.copy_group_id)
        if r.leaf_group_id: uf.u("C" + r.copy_group_id, r.leaf_group_id)
    o["leaf_group_id"] = [("GRP:" + uf.f("C" + r.copy_group_id)) for r in o.itertuples()]
    return o, dict(pv_hit)


# ------------------------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--no-copy", action="store_true"); a = ap.parse_args(); OUT = a.out
    if os.path.exists(os.path.join(OUT, "FREEZE_CHECKSUMS.sha256")): raise SystemExit("Refusing: this dataset version is frozen. A change needs a new version.")
    for d in ("images", "quarantine", "supplementary", "manifests", "metadata", "splits", "documentation"): os.makedirs(os.path.join(OUT, d), exist_ok=True)
    m = mango_records(); o, pv_hit = other_records(); df = pd.concat([m, o], ignore_index=True, sort=False).fillna({"flags": "", "reason": "", "split": "", "split_unit": ""})
    # exact duplicates across the whole dataset (Mango duplicates were already resolved in AGL-MANGO-MD; recheck here for the new crops)
    act = df[df.status.isin(["accepted"])]
    for h, g in act.groupby("sha256"):
        if len(g) < 2: continue
        if g.class_id.nunique() > 1:
            for i in g.index: df.at[i, "status"] = "quarantined"; df.at[i, "reason"] = "cross-class exact duplicate (identical file under " + ",".join(sorted(g.class_id.unique())) + "); not auto-resolved"; df.at[i, "split"] = ""
        else:
            keep = g.sort_values("image_id").index[0]
            for i in g.index:
                if i != keep: df.at[i, "status"] = "rejected"; df.at[i, "reason"] = f"within-class exact duplicate of {df.at[keep, 'image_id']}"; df.at[i, "split"] = ""
    # cross-class near-duplicate groups among new crops -> quarantine
    oo = df[(df.crop != "Mango") & (df.status == "accepted")]
    for g, x in oo.groupby("leaf_group_id"):
        if x.class_id.nunique() > 1:
            for i in x.index: df.at[i, "status"] = "quarantined"; df.at[i, "reason"] = "leaf group spans classes (same leaf or near-duplicate under " + ",".join(sorted(x.class_id.unique())) + "); not auto-resolved"
    # splits for Apple, Potato, Tomato
    sel = df[(df.crop != "Mango") & (df.status == "accepted")].copy(); sel["unit"] = sel.leaf_group_id
    sel["split"] = split_units(sel, "unit", ["class_id"], {"train": 0.70, "val": 0.15, "test_known_device": 0.15}, SEED, ["train", "val", "test_known_device"])
    df.loc[sel.index, "split"] = sel.split; df.loc[sel.index, "split_unit"] = "GRP:" + sel.unit
    # quality flags (not exclusions) for the new crops
    for crop in ("Apple", "Potato", "Tomato"):
        x = df[(df.crop == crop) & df.focus_lapvar.notna()]; p1 = x.focus_lapvar.quantile(0.01)
        for i in x.index[x.focus_lapvar < p1]: df.at[i, "flags"] = (df.at[i, "flags"] + "|low_sharpness_p1_of_crop").strip("|")
    # model index and folders
    mi = {c[0]: i for i, c in enumerate(TAX)}; df["model_index"] = df.class_id.map(mi).astype("Int64"); df["model_label"] = df.class_id.map({c[0]: c[2] for c in TAX}).fillna("")
    df["in_model_taxonomy"] = df.class_id.isin(mi)
    def rel(r):
        if r.status in ("accepted", "accepted_excluded_from_splits"): base = "images"
        elif r.status == "quarantined": base = "quarantine"
        elif r.status == "supplementary": base = "supplementary"
        else: return ""
        ext = os.path.splitext(str(r.file_source_path))[1].lower().replace(".jpeg", ".jpg")
        return f"{base}/{r.crop}/{FOLDER[r.class_id]}/{r.image_id}{ext}"
    df["master_relpath"] = df.apply(rel, axis=1)
    # ---- checks
    sp = df[df.split.isin(["train", "val", "test_known_device", "test_heldout_device"])]
    leak = {k: int((sp.groupby(k).split.nunique() > 1).sum()) for k in ("leaf_group_id", "copy_group_id", "split_unit")}
    assert all(v == 0 for v in leak.values()), f"leakage: {leak}"
    assert sp.status.eq("accepted").all() and sp.in_model_taxonomy.all()
    assert df.image_id.is_unique
    # ---- copy
    jobs = [(r.file_source_path, os.path.join(OUT, r.master_relpath.replace("/", os.sep)), r.sha256) for r in df.itertuples() if r.master_relpath]
    print("records", len(df), "files to copy", len(jobs), flush=True)
    if not a.no_copy:
        def cp(j):
            s, d, h = j; os.makedirs(os.path.dirname(d), exist_ok=True)
            if not (os.path.exists(d) and sha(d) == h): shutil.copyfile(s, d)
            return sha(d) == h
        with ThreadPoolExecutor(8) as ex: ok = list(ex.map(cp, jobs))
        print("copied", len(jobs), "sha mismatches", ok.count(False), flush=True); assert all(ok)
    # ---- manifests
    cols = ["image_id", "crop", "class_id", "model_index", "model_label", "source_class_label", "source_id", "source_dataset", "original_filename", "original_source_path", "sha256",
            "leaf_group_id", "copy_group_id", "split_unit", "capture_session_id", "capture_device", "capture_date", "width", "height", "original_or_augmented", "status", "reason", "split",
            "flags", "label_verification_status", "licence", "provenance_release", "master_relpath"]
    df[cols].to_csv(os.path.join(OUT, "manifests", "image_manifest.csv"), index=False)
    df[df.status == "quarantined"][cols].to_csv(os.path.join(OUT, "manifests", "quarantine_manifest.csv"), index=False)
    df[df.status == "rejected"][cols].to_csv(os.path.join(OUT, "manifests", "rejected_manifest.csv"), index=False)
    scols = ["image_id", "crop", "class_id", "model_index", "model_label", "split", "source_id", "capture_device", "capture_session_id", "leaf_group_id", "copy_group_id", "split_unit", "master_relpath", "sha256"]
    sp[scols].to_csv(os.path.join(OUT, "splits", "split_assignment.csv"), index=False)
    for s in ("train", "val", "test_known_device", "test_heldout_device"): sp[sp.split == s][scols].to_csv(os.path.join(OUT, "splits", f"{s}.csv"), index=False)
    # taxonomy
    acc = df[df.status == "accepted"]; trows = []
    conf = {"MNG005": "medium: MangoLeafBD labels only; SAR 'Golmichi' mapping provisional and quarantined", "MNG003": "source label, single source and essentially one phone", "MNG004": "source label, single source, leaf-only diagnosis doubtful",
            "MNG008": "source label, single source and one phone", "MNG002": "source label; ABCGMP overlaps MangoLeafBD (effectively one session)", "MNG009": "provisional; symptom, not a diagnosis; unreviewed"}
    lim = {"MNG005": "provisional until expert review; held-out-device evidence only from SAR images, which are quarantined in this release", "MNG003": "no device-independent or source-independent test",
           "MNG004": "no device-independent or source-independent test", "MNG008": "no device-independent or source-independent test", "MNG002": "no device-independent test",
           "MNG006": "no device-independent test", "MNG007": "no device-independent test (4 held-out images)", "MNG001": "held-out-device test available (SAR)",
           "MNG009": "excluded from the model", "APL": "single source, one capture campaign; no device information", "POT": "PlantVillage laboratory images; Potato healthy has 152 images from few leaves", "TOM": "PlantVillage laboratory images; same-session capture"}
    for c in TAX + NOT_IN_MODEL:
        x = acc[acc.class_id == c[0]]; allc = df[df.class_id == c[0]]
        trows.append({"class_id": c[0], "model_index": mi.get(c[0], ""), "model_label": c[2], "crop": c[1], "display_name": c[3], "source_datasets": ";".join(sorted(x.source_id.unique())) or ";".join(sorted(allc.source_id.unique())),
                      "accepted_images": len(x), "accepted_leaf_groups": x.leaf_group_id.nunique(), "quarantined": int((allc.status == "quarantined").sum()), "in_splits": int(x.split.ne("").sum()),
                      "label_confidence": conf.get(c[0], "source label, unverified by an expert"), "training_eligible": c[0] in mi, "provisional": c[0] in ("MNG005", "MNG009"),
                      "known_limitations": lim.get(c[0], lim.get(c[0][:3], ""))})
    tx = pd.DataFrame(trows); tx.to_csv(os.path.join(OUT, "manifests", "class_taxonomy.csv"), index=False)
    json.dump({"dataset": f"{DATASET_ID} {VERSION}", "classes": trows, "model_index_order": "identical to the production labels.txt (24 classes)"}, open(os.path.join(OUT, "manifests", "class_taxonomy.json"), "w"), indent=1, default=str)
    stats = {"dataset_id": DATASET_ID, "version": VERSION, "records": len(df), "by_status": df.status.value_counts().to_dict(), "by_crop_status": {f"{k[0]}|{k[1]}": int(v) for k, v in df.groupby(["crop", "status"]).size().items()},
             "accepted_by_class": acc.class_id.value_counts().sort_index().to_dict(), "by_split": sp.split.value_counts().to_dict(), "split_by_crop": {f"{k[0]}|{k[1]}": int(v) for k, v in sp.groupby(["crop", "split"]).size().items()},
             "original_vs_augmented": df.original_or_augmented.value_counts().to_dict(), "accepted_by_source": acc.source_id.value_counts().to_dict(), "leakage_checks": leak, "plantvillage_leaf_map_matches": pv_hit,
             "accepted_leaf_groups_by_crop": acc.groupby("crop").leaf_group_id.nunique().to_dict()}
    json.dump(stats, open(os.path.join(OUT, "metadata", "statistics.json"), "w"), indent=1, default=str)
    acc.groupby(["crop", "class_id", "source_id", "capture_device"]).agg(images=("image_id", "size"), leaf_groups=("leaf_group_id", "nunique"), sessions=("capture_session_id", "nunique")).reset_index().to_csv(os.path.join(OUT, "metadata", "bias_class_source_device.csv"), index=False)
    print(json.dumps(stats, indent=1, default=str)); print(tx[["class_id", "accepted_images", "accepted_leaf_groups", "quarantined", "in_splits"]].to_string())


if __name__ == "__main__":
    main()
