#!/usr/bin/env python3
"""Extract the Apple, Potato and Tomato source images from Datasets.zip (read only) into a source-extract folder, verifying every file
against the SHA-256 recorded in the earlier inventory (reports/orig/all_images_inventory.csv). Refuses to continue on any mismatch.
The archive itself is never modified. Usage: python extract_source_archive.py --zip <Datasets.zip> --out <extract root>"""
import argparse, csv, hashlib, json, os, zipfile
ap = argparse.ArgumentParser(); ap.add_argument("--zip", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--inventory", default=r"D:\AGRILENS_Training\mango_sar_mld1\reports\orig\all_images_inventory.csv"); a = ap.parse_args()
EXPECT_ZIP = "87a22c4647b515865c6eb12aafd71e77d93f4d83ea108b8bb18c0434d718e977"
h = hashlib.sha256()
with open(a.zip, "rb") as f:
    for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
assert h.hexdigest() == EXPECT_ZIP, f"archive hash differs: {h.hexdigest()}"
folder = {"Apple": "apple dataset", "Potato": "Potato Dataset", "Tomato": "Tomato dataset"}
inv = {}
for r in csv.DictReader(open(a.inventory, encoding="utf-8")):
    if r["crop"] in folder: inv[f"datasets/{folder[r['crop']]}/{r['rel'].replace(chr(92), '/')}"] = r["sha256"]
ok = bad = 0; missing = set(inv)
with zipfile.ZipFile(a.zip) as z:
    for e in z.infolist():
        if e.filename in inv:
            data = z.read(e); dst = os.path.join(a.out, *e.filename.split("/")); os.makedirs(os.path.dirname(dst), exist_ok=True)
            if hashlib.sha256(data).hexdigest() != inv[e.filename]: bad += 1; continue
            if not os.path.exists(dst): open(dst, "wb").write(data)
            ok += 1; missing.discard(e.filename)
rec = {"archive": a.zip, "archive_sha256": EXPECT_ZIP, "extracted_verified": ok, "sha_mismatches": bad, "inventory_entries_not_in_archive": len(missing)}
json.dump(rec, open(os.path.join(a.out, "EXTRACT_RECORD.json"), "w"), indent=1); print(json.dumps(rec))
assert bad == 0 and not missing
