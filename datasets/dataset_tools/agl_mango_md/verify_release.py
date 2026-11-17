#!/usr/bin/env python3
"""Verify a frozen AGL-MANGO-MD release: (1) every file listed in FREEZE_CHECKSUMS.sha256 matches; (2) no file exists that is not listed
(except the three freeze records); (3) every image in manifests/master_image_manifest.csv matches its SHA-256 and sits where the manifest says;
(4) split files only reference accepted images and no leaf group, copy group or unit spans two splits.
Usage: python verify_release.py <release_dir>   Exit code 0 = pass."""
import csv, hashlib, os, sys
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

root = sys.argv[1]; EXEMPT = {"FREEZE_CHECKSUMS.sha256", "RELEASE_MANIFEST.json", "FROZEN.txt"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()


listed = {}
for ln in open(os.path.join(root, "FREEZE_CHECKSUMS.sha256"), encoding="utf-8"):
    if ln.strip(): h, p = ln.rstrip("\n").split("  ", 1); listed[p] = h
present = {}
for dp, _, fs in os.walk(root):
    for f in fs:
        p = os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/")
        if p not in EXEMPT: present[p] = os.path.join(dp, f)
missing = sorted(set(listed) - set(present)); extra = sorted(set(present) - set(listed))
with ThreadPoolExecutor(8) as ex: got = dict(zip(present, ex.map(sha, present.values())))
bad = sorted(p for p in listed if p in got and got[p] != listed[p])
print(f"files listed {len(listed)} present {len(present)} missing {len(missing)} unexpected {len(extra)} hash mismatches {len(bad)}")
m = pd.read_csv(os.path.join(root, "manifests", "master_image_manifest.csv"), low_memory=False)
onf = m[m.master_relpath.notna() & (m.master_relpath != "")]
img_bad = [r.master_image_id for r in onf.itertuples() if got.get(r.master_relpath) != r.sha256]
print(f"images in manifest on disk {len(onf)} sha mismatches/missing {len(img_bad)}")
acc = set(m[m.inclusion_status == "accepted"].master_image_id)
sa = pd.read_csv(os.path.join(root, "splits", "split_assignment.csv"))
used = sa[sa.split.isin(["train", "val", "test_known_device", "test_heldout_device"])]
print("split images", len(used), "not accepted:", int((~used.master_image_id.isin(acc)).sum()))
cross = {k: int((used.groupby(k).split.nunique() > 1).sum()) for k in ("leaf_group_id", "duplicate_group_id", "unit")}
print("groups spanning more than one split:", cross)
ok = not (missing or extra or bad or img_bad) and not (~used.master_image_id.isin(acc)).any() and not any(cross.values())
print("VERIFICATION", "PASS" if ok else "FAIL")
if missing: print("missing", missing[:5])
if extra: print("unexpected", extra[:5])
if bad: print("bad", bad[:5])
sys.exit(0 if ok else 1)
