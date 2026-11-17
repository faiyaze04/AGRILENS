#!/usr/bin/env python3
"""AGL-MANGO-MD v1.0.0 step 5: dataset_statistics.json, docs/CLASS_STATISTICS.md, dataset_manifest.json (identity + file hashes)."""
import csv, datetime as dt, hashlib, json, os
from collections import Counter, defaultdict

BASE = r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.0.0"
MIN_LEAVES = 300  # heuristic: fewer distinct accepted leaf groups than this = "insufficient genuine images" for a specialist class


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()


def main():
    rows = list(csv.DictReader(open(os.path.join(BASE, "manifests", "master_image_manifest.csv"), newline="", encoding="utf-8")))
    spl = {r["master_image_id"]: r["split"] for r in csv.DictReader(open(os.path.join(BASE, "splits", "split_assignment.csv"), newline="", encoding="utf-8"))}
    classes = sorted({r["class_id"] for r in rows})
    names = {r["class_id"]: r["class_name"] for r in rows}
    st = {"dataset_id": "AGL-MANGO-MD", "version": "v1.0.0", "per_class": {}, "totals": {}}
    for c in classes:
        R = [r for r in rows if r["class_id"] == c]
        A = [r for r in R if r["inclusion_status"] == "accepted"]
        d = {"class_name": names[c], "records_total": len(R),
             "by_status": dict(Counter(r["inclusion_status"] for r in R)),
             "accepted_images": len(A), "accepted_distinct_leaf_groups": len({r["leaf_group_id"] for r in A}),
             "accepted_distinct_copy_groups": len({r["duplicate_group_id"] for r in A}),
             "accepted_original_vs_derivative": dict(Counter(r["original_or_augmented"] for r in A)),
             "accepted_by_source": dict(Counter(r["source_id"] for r in A)),
             "accepted_by_camera": dict(Counter(r["capture_device"] for r in A)),
             "accepted_by_month": dict(sorted(Counter(r["capture_date"][:7] for r in A).items())),
             "accepted_by_capture_day_count": len({r["capture_date"] for r in A}),
             "accepted_by_split": dict(Counter(spl.get(r["master_image_id"], "-") for r in A)),
             "quarantine_reasons": dict(Counter(x.split(":")[0] for r in R if r["inclusion_status"] == "quarantined" for x in r["reasons"].split("|") if x)),
             "reject_reasons": dict(Counter(x.split(":")[0] for r in R if r["inclusion_status"] == "rejected" for x in r["reasons"].split("|") if x)),
             "flags": dict(Counter(x for r in A for x in r["flags"].split("|") if x))}
        d["single_source"] = len(d["accepted_by_source"]) == 1
        d["single_camera"] = len([k for k in d["accepted_by_camera"] if not k.startswith("unknown")]) <= 1
        d["insufficient_genuine_leaves"] = d["accepted_distinct_leaf_groups"] < MIN_LEAVES
        st["per_class"][c] = d
    A = [r for r in rows if r["inclusion_status"] == "accepted"]
    st["totals"] = {"records_total": len(rows), "by_status": dict(Counter(r["inclusion_status"] for r in rows)),
                    "accepted_images": len(A), "accepted_distinct_leaf_groups": len({r["leaf_group_id"] for r in A}),
                    "by_source_status": {f"{s}|{k}": v for (s, k), v in sorted(Counter((r["source_id"], r["inclusion_status"]) for r in rows).items())}}
    # metadata-only predictability of class (in-sample majority rule; upper bound of what a shortcut could give without looking at the leaf)
    def pred(keyf):
        g = defaultdict(Counter)
        for r in A: g[keyf(r)][r["class_id"]] += 1
        ok = sum(max(v.values()) for v in g.values()); return round(ok / len(A), 4), len(g)
    base = max(Counter(r["class_id"] for r in A).values()) / len(A)
    st["metadata_shortcut_risk"] = {"majority_class_baseline": round(base, 4),
        "class_from_source": pred(lambda r: r["source_id"]), "class_from_camera": pred(lambda r: r["capture_device"]),
        "class_from_source_camera": pred(lambda r: (r["source_id"], r["capture_device"])),
        "class_from_source_camera_size": pred(lambda r: (r["source_id"], r["capture_device"], r["width"], r["height"])),
        "class_from_source_camera_size_month": pred(lambda r: (r["source_id"], r["capture_device"], r["width"], r["height"], r["capture_date"][:7])),
        "note": "(accuracy, number of metadata cells). Values far above the majority baseline mean acquisition metadata alone separates classes."}
    st["exact_and_near_duplicates"] = {
        "rejected_within_class_exact_duplicates": sum(1 for r in rows if "within_class_exact_duplicate" in r["reasons"]),
        "quarantined_cross_class": sum(1 for r in rows if "cross_class" in r["reasons"]),
        "copy_groups_with_more_than_one_accepted_member": sum(1 for g, n in Counter(r["duplicate_group_id"] for r in A).items() if n > 1),
        "accepted_likely_derivative": sum(1 for r in A if r["original_or_augmented"] == "likely_derivative"),
        "legacy_derivatives_of_MangoLeafBD_excluded": sum(1 for r in rows if "derivative_of_MANGOLEAFBD" in r["reasons"]),
        "legacy_augmented_recorded_not_copied": sum(1 for r in rows if r["inclusion_status"] == "excluded_augmented")}
    json.dump(st, open(os.path.join(BASE, "manifests", "dataset_statistics.json"), "w"), indent=1)
    L = ["# AGL-MANGO-MD v1.0.0 class statistics (generated)\n",
         "| Class | Records | Accepted | Leaf groups | Supplementary | Quarantined | Rejected | Excl. augmented | Sources | Cameras | Single src | Insufficient (<%d leaves) |" % MIN_LEAVES,
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in classes:
        d = st["per_class"][c]; b = d["by_status"]
        L.append(f"| {c} {d['class_name']} | {d['records_total']} | {d['accepted_images']} | {d['accepted_distinct_leaf_groups']} | {b.get('accepted_supplementary', 0)} | "
                 f"{b.get('quarantined', 0)} | {b.get('rejected', 0)} | {b.get('excluded_augmented', 0)} | {', '.join(f'{k}:{v}' for k, v in d['accepted_by_source'].items())} | "
                 f"{len(d['accepted_by_camera'])} | {d['single_source']} | {d['insufficient_genuine_leaves']} |")
    L += ["", "## Cameras per class (accepted)"]
    for c in classes: L.append(f"- {c}: " + "; ".join(f"{k} = {v}" for k, v in st["per_class"][c]["accepted_by_camera"].items()))
    L += ["", "## Capture months per class (accepted)"]
    for c in classes: L.append(f"- {c}: " + "; ".join(f"{k} = {v}" for k, v in st["per_class"][c]["accepted_by_month"].items()))
    L += ["", "## Split mix per class (accepted)"]
    for c in classes: L.append(f"- {c}: {st['per_class'][c]['accepted_by_split']}")
    L += ["", "## Metadata shortcut risk", "```", json.dumps(st["metadata_shortcut_risk"], indent=1), "```"]
    os.makedirs(os.path.join(BASE, "docs"), exist_ok=True)
    open(os.path.join(BASE, "docs", "CLASS_STATISTICS.md"), "w", encoding="utf-8").write("\n".join(L))
    files = {}
    for d in ("manifests", "splits"):
        for f in sorted(os.listdir(os.path.join(BASE, d))):
            files[f"{d}/{f}"] = sha(os.path.join(BASE, d, f))
    man = {"dataset_id": "AGL-MANGO-MD", "name": "AGRILENS Mango Master Dataset", "version": "v1.0.0",
           "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "status": "DRAFT FOR USER REVIEW - not approved for training",
           "classes": {c: {"folder": f"{c}_{names[c].upper().replace(' ', '_').replace('MOULD', 'MOULD')}", "name": names[c],
                           "provisional": c in ("MNG005", "MNG009")} for c in classes},
           "sources": {"SAR25": "SAR-MLD1-2025 (Mendeley sd8hzpg69b, j3bn63t4sp; v4 downloaded; CC BY 4.0)",
                       "MANGOLEAFBD": "MangoLeafBD (Mendeley hxsnvwty3r v1; CC BY-NC 3.0 non-commercial)",
                       "LEGACY": "Legacy compilation (Mendeley 7ghdbftp54 v1; background removed; CC BY 4.0 per record, derivation concern)",
                       "ABCGMP": "ABCGMP six-crop dataset, mango leaf folders only (Mendeley fhbvmpcyy2; CC BY 4.0 per v2 record)",
                       "C270": "reserved: real field images, evaluation only, none collected yet"},
           "totals": st["totals"], "layout": {"images": "accepted, default training-eligible", "images_supplementary": "accepted but background-removed (not default)",
                                              "quarantine": "review copies, excluded from all splits"},
           "naming": "<CLASS>_<SRCID>_IMG<6 digits>.<ext> (counter per class and source); extension kept real (.jpg/.png)",
           "file_sha256": files}
    json.dump(man, open(os.path.join(BASE, "manifests", "dataset_manifest.json"), "w"), indent=1)
    print(json.dumps({"totals": st["totals"], "risk": st["metadata_shortcut_risk"], "dups": st["exact_and_near_duplicates"]}, indent=1))
    print("\n".join(L[:14]))


if __name__ == "__main__":
    main()
