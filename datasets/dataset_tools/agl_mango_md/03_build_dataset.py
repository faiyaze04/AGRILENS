#!/usr/bin/env python3
"""AGL-MANGO-MD v1.0.0 step 3: assign master IDs, copy images byte-identically (SHA verified), write manifests.
Input : work/candidates.csv, work/decisions.csv, work/duplicate_pairs.csv, work/augmented_links.csv
Output: images/, images_supplementary/, quarantine/, manifests/{master_image_manifest,duplicate_report,quarantine_manifest,class_mapping}.csv
Originals are only read. Re-running replaces the copies (idempotent).
"""
import csv, hashlib, os, re, shutil
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

BASE = r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.0.0"
W = os.path.join(BASE, "work"); M = os.path.join(BASE, "manifests")
CLASSES = {"MNG001": "ANTHRACNOSE", "MNG002": "BACTERIAL_CANKER", "MNG003": "CUTTING_WEEVIL", "MNG004": "DIE_BACK",
           "MNG005": "GALL_MIDGE", "MNG006": "HEALTHY", "MNG007": "POWDERY_MILDEW", "MNG008": "SOOTY_MOULD", "MNG009": "TURNING_BROWN"}
CNAME = {"MNG001": "Anthracnose", "MNG002": "Bacterial Canker", "MNG003": "Cutting Weevil", "MNG004": "Die Back",
         "MNG005": "Gall Midge", "MNG006": "Healthy", "MNG007": "Powdery Mildew", "MNG008": "Sooty Mould", "MNG009": "Turning Brown"}
SRC_CLS = {"Anthracnose": "MNG001", "Bacterial Canker": "MNG002", "Cutting Weevil": "MNG003", "Die Back": "MNG004",
           "Gall Midge": "MNG005", "Golmichi": "MNG005", "Healthy": "MNG006", "Powdery Mildew": "MNG007",
           "Sooty Mould": "MNG008", "Turning brown": "MNG009"}
SRCID = {"MANGOLEAFBD": "MANGOLEAFBD", "SAR25": "SAR25", "LEGACY": "LEGACY", "ABCGMP": "ABCGMP"}
DEST = {"accepted": "images", "accepted_supplementary": "images_supplementary", "quarantined": "quarantine"}


def stem(name):
    s = os.path.splitext(name)[0]
    s = re.sub(r"(\s*\(Custom\))+$", "", s); s = re.sub(r"\s*\(\d+\)$", "", s)
    return s.strip().lower()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()


def main():
    C = list(csv.DictReader(open(os.path.join(W, "candidates.csv"), newline="", encoding="utf-8")))
    D = list(csv.DictReader(open(os.path.join(W, "decisions.csv"), newline="", encoding="utf-8")))
    assert len(C) == len(D)
    for d in ("images", "images_supplementary", "quarantine"):
        p = os.path.join(BASE, d)
        if os.path.isdir(p): shutil.rmtree(p)
        for c, n in CLASSES.items(): os.makedirs(os.path.join(p, f"{c}_{n}"), exist_ok=True)
    os.makedirs(M, exist_ok=True)
    # IDs: per (class, source) counter, ordered by source path
    order = sorted(range(len(C)), key=lambda i: (D[i]["mng"], C[i]["source"], C[i]["src_rel"]))
    cnt = defaultdict(int); mid = {}
    for i in order:
        k = (D[i]["mng"], C[i]["source"]); cnt[k] += 1
        mid[i] = f"{k[0]}_{SRCID[k[1]]}_IMG{cnt[k]:06d}"
    rows, jobs = [], []
    for i, (c, d) in enumerate(zip(C, D)):
        ext = os.path.splitext(c["orig_name"])[1].lower().replace(".jpeg", ".jpg")
        dec = d["decision"]; rel = ""
        if dec in DEST:
            rel = f"{DEST[dec]}/{d['mng']}_{CLASSES[d['mng']]}/{mid[i]}{ext}"
            jobs.append((c["path"], os.path.join(BASE, rel), c["sha256"]))
        dev = " ".join((c["make"] + " " + c["model"]).replace("\x00", " ").split()) or ("unknown (background-removed compilation)" if c["source"] == "LEGACY" else "unknown")
        date = (c["exif_datetime"][:10].replace(":", "-") if re.match(r"\d{4}:\d\d:\d\d", c["exif_datetime"] or "") else c["name_time"][:10])
        lab = "source_label_unverified" + ("_provisional_mapping" if d["mng"] in ("MNG005", "MNG009") else "")
        if "cross_class" in d["reasons"] or "kNN_label" in d["reasons"]: lab = "conflict_unresolved"
        rows.append(dict(master_image_id=mid[i], class_id=d["mng"], class_name=CNAME[d["mng"]], original_filename=c["orig_name"],
                         source_id=SRCID[c["source"]], source_class_label=c["src_class"], original_source_dataset=c["origin"],
                         original_source_path=c["src_rel"], sha256=c["sha256"], width=c["w"], height=c["h"], file_bytes=c["bytes"],
                         capture_device=dev, capture_date=date or "unknown", original_or_augmented=d["orig_status"],
                         duplicate_group_id=d["copy_group_id"], leaf_group_id=d["leaf_group_id"],
                         label_verification_status=lab, inclusion_status=dec, reasons=d["reasons"], flags=d["flags"],
                         licence_flag=c["licence"], sharpness=round(float(c["sharp"]), 2) if c["sharp"] else "",
                         fg_fraction=round(float(c["fg_frac"]), 4) if c["fg_frac"] else "",
                         legacy_parent=d["legacy_parent"], master_relpath=rel))
    # legacy augmented (recorded only)
    byleg = defaultdict(list)
    for r in rows:
        if r["source_id"] == "LEGACY": byleg[(r["class_name"], stem(r["original_filename"]))].append(r)
    acnt = defaultdict(int); naug = nlink = 0
    for a in csv.DictReader(open(os.path.join(W, "augmented_links.csv"), newline="", encoding="utf-8")):
        mm = re.match(r"^aug_\d+_(.*)$", a["aug_name"], re.I)
        base = stem(mm.group(1)) if mm else stem(a["aug_name"])
        cls = {k.lower(): v for k, v in SRC_CLS.items()}.get(a["aug_class"].lower())
        if cls is None: continue
        par = byleg.get((CNAME[cls], base), [])
        acnt[cls] += 1; naug += 1; nlink += bool(par)
        rows.append(dict(master_image_id=f"{cls}_LEGACY_AUG{acnt[cls]:06d}", class_id=cls, class_name=CNAME[cls], original_filename=a["aug_name"],
                         source_id="LEGACY", source_class_label=a["aug_class"],
                         original_source_dataset="Legacy compilation Mendeley 7ghdbftp54 v1 (Augmented Image)",
                         original_source_path="Augmented Image/" + a["aug_class"] + "/" + a["aug_name"], sha256=a["sha256"],
                         width="", height="", file_bytes="", capture_device="n/a (augmented)", capture_date="unknown",
                         original_or_augmented="augmented", duplicate_group_id=par[0]["duplicate_group_id"] if par else "",
                         leaf_group_id=par[0]["leaf_group_id"] if par else "", label_verification_status="source_label_unverified",
                         inclusion_status="excluded_augmented", reasons="augmented copy; parent=" + (par[0]["master_image_id"] if par else "not_found"),
                         flags="", licence_flag="CC BY 4.0 per record; derivation concern", sharpness="", fg_fraction="",
                         legacy_parent=par[0]["master_image_id"] if par else "", master_relpath=""))
    print("augmented recorded", naug, "linked to a process-data parent", nlink)

    def cp(j):
        s, d, h = j
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(s, d)
        return sha(d) == h
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(cp, jobs))
    bad = res.count(False)
    print("copied", len(jobs), "sha mismatches", bad)
    assert bad == 0
    cols = list(rows[0].keys())
    with open(os.path.join(M, "master_image_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
    with open(os.path.join(M, "quarantine_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols + ["review_action"]); w.writeheader()
        for r in rows:
            if r["inclusion_status"] == "quarantined":
                w.writerow({**r, "review_action": "pending human label/quality review; not used in any split"})
    # duplicate report
    idx = {C[i]["src_rel"]: mid[i] for i in range(len(C))}
    st = {mid[i]: D[i]["decision"] for i in range(len(C))}
    nd = 0
    with open(os.path.join(M, "duplicate_report.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["image_a", "class_a", "image_b", "class_b", "evidence", "cosine", "dhash_hamming", "same_class", "status_a", "status_b",
                    "interpretation"])
        interp = {"E1": "byte-identical files", "E2": "near-identical (feature cosine>=0.97 [+hash for non-SAR])",
                  "E3": "near-identical (perceptual hash + features, same source)", "E4": "same session/leaf burst (distinct photos, grouped not merged)",
                  "E5": "MangoLeafBD zoom/rotate derivative (same file-name stem)", "E6": "legacy background-removed derivative of MangoLeafBD image",
                  "X_c": "CROSS-CLASS duplicate/near-duplicate (label conflict, quarantined)"}
        for p in csv.DictReader(open(os.path.join(W, "duplicate_pairs.csv"), newline="", encoding="utf-8")):
            a, b = idx[p["a_src_rel"]], idx[p["b_src_rel"]]
            k = p["evidence"][:3] if p["evidence"][:1] != "X" else "X_c"
            k = k if k in interp else p["evidence"][:2]
            w.writerow([a, p["a_class"], b, p["b_class"], p["evidence"], p["cosine"], p["dhash_hamming"], p["same_class"], st[a], st[b], interp.get(k, "")])
            nd += 1
        for r in rows:
            if r["inclusion_status"] == "excluded_augmented" and r["legacy_parent"]:
                w.writerow([r["master_image_id"], r["class_id"], r["legacy_parent"], r["class_id"], "AUG_parent_by_name", "", "", True,
                            "excluded_augmented", st.get(r["legacy_parent"], ""), "augmented copy linked to its process-data original"]); nd += 1
    print("duplicate rows", nd)
    # class mapping
    with open(os.path.join(M, "class_mapping.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_id", "source_class_label", "class_id", "class_folder", "class_name", "mapping_status", "note"])
        notes = {("SAR25", "Golmichi"): ("provisional", "Golmichi = local name for mango gall midge (Cecidomyiidae) galls; mapped by visual agreement with MangoLeafBD Gall Midge; expert confirmation outstanding"),
                 ("SAR25", "Turning brown"): ("provisional", "no counterpart in other sources; expert definition of the symptom outstanding")}
        for sid, labs in (("MANGOLEAFBD", ["Anthracnose", "Bacterial Canker", "Cutting Weevil", "Die Back", "Gall Midge", "Healthy", "Powdery Mildew", "Sooty Mould"]),
                          ("SAR25", ["Anthracnose", "Golmichi", "Healthy", "Powdery Mildew", "Turning brown"]),
                          ("LEGACY", ["Anthracnose", "Bacterial Canker", "Cutting Weevil", "Die Back", "Gall Midge", "Healthy", "Powdery Mildew", "Sooty Mould"]),
                          ("ABCGMP", ["Bacterial Canker", "Healthy"])):
            for l in labs:
                c = SRC_CLS[l]; ms, nt = notes.get((sid, l), ("source_label_unverified", ""))
                if sid == "ABCGMP": nt = {"Bacterial Canker": "zip folder 'Mango Bacterial Canker' (leaf)", "Healthy": "zip folder 'Mang Healthy Leaf' (leaf)"}[l]
                w.writerow([sid, l, c, f"{c}_{CLASSES[c]}", CNAME[c], ms, nt])
        w.writerow(["C270", "(field images, not yet collected)", "", "", "", "evaluation_only", "separate evaluation source; never mixed into training"])
    print("done")


if __name__ == "__main__":
    main()
