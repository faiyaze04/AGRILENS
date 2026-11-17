#!/usr/bin/env python3
"""Read-only verification of the frozen AGL-MULTICROP-MD release. Writes nothing inside the dataset.
  python verify_agl_multicrop_md.py --dataset <AGL-MULTICROP-MD-1.0.0> --out <report.json> [--archive-root <dir with source archives>]
Checks: every FREEZE_CHECKSUMS entry (hash and presence) and no unlisted files; manifest/split consistency; per-image SHA-256 equals the
manifest; counts by crop, class, status, original/augmented; exact-duplicate handling; split sizes; leakage of leaf groups, copy (derivative /
burst) groups and split units across splits; provenance fields present for every image in the splits."""
import argparse, csv, hashlib, json, os
from collections import Counter, defaultdict
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", required=True); ap.add_argument("--out", required=True); a = ap.parse_args(); D = a.dataset
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
R = {"dataset": D}
listed = {}
for ln in open(os.path.join(D, "FREEZE_CHECKSUMS.sha256"), encoding="utf-8"):
    if ln.strip(): h, p = ln.rstrip("\n").split("  ", 1); listed[p] = h
on_disk = set()
for dp, _, fs in os.walk(D):
    for f in fs: on_disk.add(os.path.relpath(os.path.join(dp, f), D).replace(os.sep, "/"))
on_disk.discard("FREEZE_CHECKSUMS.sha256")
bad = [p for p, h in listed.items() if p not in on_disk or sha(os.path.join(D, p)) != h]
R["freeze"] = {"freeze_file_sha256": sha(os.path.join(D, "FREEZE_CHECKSUMS.sha256")), "files_listed": len(listed), "files_on_disk_excluding_freeze_file": len(on_disk),
               "files_on_disk_including_freeze_file": len(on_disk) + 1, "missing_or_changed": len(bad), "examples": bad[:10], "unlisted_files": sorted(on_disk - set(listed))[:10], "unlisted_count": len(on_disk - set(listed))}
M = list(csv.DictReader(open(os.path.join(D, "manifests", "image_manifest.csv"), encoding="utf-8")))
R["records"] = {"total": len(M), "by_status": dict(Counter(r["status"] for r in M)), "by_original_or_augmented": dict(Counter(r["original_or_augmented"] for r in M)),
                "by_status_and_origin": {f"{k[0]} | {k[1]}": v for k, v in sorted(Counter((r["status"], r["original_or_augmented"]) for r in M).items())}}
acc = [r for r in M if r["status"] == "accepted"]
R["accepted_by_crop"] = dict(sorted(Counter(r["crop"] for r in acc).items()))
R["accepted_by_class"] = {f"{k[0]} {k[1]}": v for k, v in sorted(Counter((r["class_id"], r["model_label"]) for r in acc).items())}
R["status_by_crop"] = {c: dict(Counter(r["status"] for r in M if r["crop"] == c)) for c in sorted({r["crop"] for r in M})}
R["status_by_class"] = {c: dict(Counter(r["status"] for r in M if r["class_id"] == c)) for c in sorted({r["class_id"] for r in M})}
# image files in the release referenced by the manifest: hash check
img_bad = img_n = 0
for r in M:
    rel = r.get("master_relpath", "")
    if rel and os.path.exists(os.path.join(D, rel)):
        img_n += 1; img_bad += listed.get(rel) != r["sha256"]
R["manifest_vs_freeze_hash"] = {"images_checked": img_n, "mismatches": img_bad}
# duplicates
by_sha = defaultdict(list)
for r in M:
    if r["status"] in ("accepted", "accepted_excluded_from_splits"): by_sha[r["sha256"]].append(r)
R["exact_duplicates_among_kept_images"] = sum(1 for v in by_sha.values() if len(v) > 1)
R["rejected_reasons"] = dict(Counter(r["reason"] for r in M if r["status"] == "rejected").most_common())
R["quarantine_reasons"] = dict(Counter(r["reason"] for r in M if r["status"] == "quarantined").most_common())
R["excluded_augmented_reasons"] = dict(Counter(r["reason"] for r in M if r["status"] == "excluded_augmented").most_common(5))
# splits
S = {}
for s in ("train", "val", "test_known_device", "test_heldout_device"):
    S[s] = list(csv.DictReader(open(os.path.join(D, "splits", f"{s}.csv"), encoding="utf-8")))
mid = {r["image_id"]: r for r in M}
R["splits"] = {s: {"images": len(v), "by_crop": dict(sorted(Counter(r["crop"] for r in v).items())), "by_class": dict(sorted(Counter(r["class_id"] for r in v).items()))} for s, v in S.items()}
R["split_consistency"] = {"ids_not_in_manifest": sum(r["image_id"] not in mid for v in S.values() for r in v),
                          "split_rows_not_accepted": sum(mid.get(r["image_id"], {}).get("status") != "accepted" for v in S.values() for r in v),
                          "split_column_disagrees": sum(mid.get(r["image_id"], {}).get("split") != s for s, v in S.items() for r in v),
                          "accepted_not_in_any_split": len({r["image_id"] for r in acc} - {r["image_id"] for v in S.values() for r in v}),
                          "image_in_two_splits": sum(c > 1 for c in Counter(r["image_id"] for v in S.values() for r in v).values())}
leak = {}
for key in ("leaf_group_id", "copy_group_id", "split_unit"):
    where = defaultdict(set)
    for s, v in S.items():
        for r in v:
            if r[key]: where[r[key]].add(s)
    leak[key] = {"groups": len(where), "groups_in_more_than_one_split": sum(len(x) > 1 for x in where.values())}
sess = defaultdict(set)
for s, v in S.items():
    for r in v: sess[r["capture_session_id"]].add("train" if s == "train" else ("val" if s == "val" else "test"))
leak["capture_session_id (information only; sessions are not a split unit)"] = {"sessions": len(sess), "sessions_spanning_train_and_test": sum({"train", "test"} <= x for x in sess.values())}
R["leakage"] = leak
dup_split = sum(len({mid[x["image_id"]]["split"] for x in v}) > 1 for v in by_sha.values() if len(v) > 1)
R["leakage"]["identical_sha256_across_splits"] = dup_split
need = ("source_id", "source_dataset", "original_filename", "original_source_path", "sha256", "licence")
R["provenance"] = {"split_images_missing_a_provenance_field": sum(any(not mid[r["image_id"]].get(k) for k in need) for v in S.values() for r in v),
                   "by_source": dict(sorted(Counter(r["source_id"] for r in acc).items())), "licences": dict(Counter(r["licence"] for r in acc))}
json.dump(R, open(a.out, "w", encoding="utf-8"), indent=1)
ok = not bad and not R["freeze"]["unlisted_count"] and not img_bad and all(v == 0 for v in R["split_consistency"].values()) and all(v["groups_in_more_than_one_split"] == 0 for k, v in leak.items() if k in ("leaf_group_id", "copy_group_id", "split_unit")) and dup_split == 0
print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"freeze": R["freeze"]["missing_or_changed"], "records": len(M), "splits": {s: len(v) for s, v in S.items()}, "leakage": leak}))
