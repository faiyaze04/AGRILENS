#!/usr/bin/env python3
"""Write documentation, source-archive provenance and the version manifest for AGL-MULTICROP-MD, verify every file against the image manifest,
then write FREEZE_CHECKSUMS.sha256 (every file). Read-only protection is applied afterwards by the operator. Usage: python freeze_agl_multicrop_md.py --root <dataset root>"""
import argparse, datetime as dt, hashlib, json, os
from concurrent.futures import ThreadPoolExecutor
import pandas as pd

ap = argparse.ArgumentParser(); ap.add_argument("--root", required=True); a = ap.parse_args(); R = a.root
if os.path.exists(os.path.join(R, "FREEZE_CHECKSUMS.sha256")): raise SystemExit("already frozen")
AGRI = r"d:\OneDrive - Faiyaz Personal\OneDrive\3. Shreyance related Documents\AgriLens"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()


m = pd.read_csv(os.path.join(R, "manifests", "image_manifest.csv"), low_memory=False); tax = pd.read_csv(os.path.join(R, "manifests", "class_taxonomy.csv"))
st = json.load(open(os.path.join(R, "metadata", "statistics.json")))
on = m[m.master_relpath.notna() & (m.master_relpath != "")]
with ThreadPoolExecutor(8) as ex: got = list(ex.map(lambda p: sha(os.path.join(R, p.replace("/", os.sep))), on.master_relpath))
bad = int(sum(g != h for g, h in zip(got, on.sha256))); print("image files verified", len(on), "mismatches", bad); assert bad == 0
srcs = [("Datasets.zip (Apple, Potato, Tomato, original MangoLeafBD copy)", AGRI + r"\Datasets.zip"), ("Mango Leaf Disease Dataset.zip (legacy compilation, Mendeley 7ghdbftp54 v1)", AGRI + r"\Mango Leaf Disease Dataset.zip"),
        ("SAR-MLD1-2025 Part 01.zip (Mendeley sd8hzpg69b v4)", AGRI + r"\SAR-MLD1-2025 Part 01.zip"), ("SAR-MLD1-2025 Part 02.zip (Mendeley j3bn63t4sp v4)", AGRI + r"\SAR-MLD1-2025 Part 02.zip"),
        ("ABCGMP six-crop dataset zip (Mendeley fhbvmpcyy2, 'version 1')", r"D:\Downloads\6  indian Fruit crops Fruit and Leaf Disease Dataset (version 1).zip")]
arch = [{"description": d, "path": p, "exists": os.path.exists(p), "bytes": os.path.getsize(p) if os.path.exists(p) else None, "sha256": sha(p) if os.path.exists(p) else None} for d, p in srcs]
arch.append({"description": "AGL-MANGO-MD v1.0.0 and v1.1.0-rc1 (frozen Mango releases; Mango image provenance)", "path": r"D:\AGRILENS_Training\AGL-MANGO-MD", "sha256": None, "note": "see their FREEZE_CHECKSUMS.sha256 / provenance records"})
json.dump({"note": "Source archives are kept outside the dataset so it can be reconstructed. The extracted AgriLens\\datasets folder used in earlier work no longer exists; Apple, Potato and Tomato were re-extracted from Datasets.zip and verified per file.", "archives": arch},
          open(os.path.join(R, "metadata", "source_archives.json"), "w"), indent=1)
lic = {"PLANTVILLAGE": "CC BY-SA 3.0 (PlantVillage; attribution and share-alike)", "PP2020": "Plant Pathology 2020 (FGVC7) Kaggle competition data; terms not verified", "MANGOLEAFBD": "CC BY-NC 3.0 (non-commercial)",
       "SAR25": "CC BY 4.0", "ABCGMP": "CC BY 4.0 per v2 record (local v1 unverified); overlaps MangoLeafBD images", "LEGACY": "CC BY 4.0 per record; derivation from MangoLeafBD suspected"}
json.dump({"licences_by_source": lic, "flag": "MangoLeafBD is non-commercial; the PlantVillage licence requires share-alike for derivatives. Not a legal review."}, open(os.path.join(R, "metadata", "licences.json"), "w"), indent=1)
acc = m[m.status == "accepted"]; sp = m[m.split.notna() & (m.split != "")]
rows = []
for r in tax.itertuples():
    x = sp[sp.class_id == r.class_id]; rows.append(f"| {r.class_id} | {'' if pd.isna(r.model_index) else int(r.model_index)} | {r.display_name} | {r.source_datasets} | {r.accepted_images} | {r.accepted_leaf_groups} | {r.quarantined} | "
                                                 f"{(x.split == 'train').sum()} / {(x.split == 'val').sum()} / {(x.split == 'test_known_device').sum()} / {(x.split == 'test_heldout_device').sum()} | {r.label_confidence} |")
card = f"""# AGL-MULTICROP-MD 1.0.0

The authoritative four-crop master dataset for AGRILENS (Apple, Mango, Potato, Tomato). Created {dt.date.today()}. Frozen: every file is listed in `FREEZE_CHECKSUMS.sha256`. Never modify a released version; changes produce a new version through `datasets/dataset_tools/` in the AGRILENS repository.

## Contents
| Folder | Content |
|---|---|
| `images/<Crop>/<CLASS>/` | accepted images ({int((m.status == 'accepted').sum()):,} in splits, {int((m.status == 'accepted_excluded_from_splits').sum())} accepted but kept out of every split) |
| `quarantine/<Crop>/<CLASS>/` | {int((m.status == 'quarantined').sum()):,} images with uncertain labels, provisional classes or mappings, or quality holds; never in a split |
| `supplementary/` | {int((m.status == 'supplementary').sum())} background-removed legacy Mango images; never in a split by default |
| `manifests/` | `image_manifest.csv` (one row per source record, {len(m):,} rows, including {int((m.status == 'rejected').sum()):,} rejected and {int((m.status == 'excluded_augmented').sum()):,} augmented records that are not copied), `class_taxonomy.csv/.json`, `quarantine_manifest.csv`, `rejected_manifest.csv` |
| `splits/` | `split_assignment.csv`, `train.csv`, `val.csv`, `test_known_device.csv`, `test_heldout_device.csv` |
| `metadata/` | `statistics.json`, `bias_class_source_device.csv`, `source_archives.json`, `licences.json` |

## Classes (model_index = order of the production labels.txt; train / val / test_known_device / test_heldout_device)
| Class ID | Model index | Name | Sources | Accepted | Leaf groups | Quarantined | Splits | Label confidence |
|---|---|---|---|---|---|---|---|---|
""" + "\n".join(rows) + f"""

MNG009 Turning Brown is in the taxonomy but not in the model (provisional class). MNG005 Gall Midge uses MangoLeafBD-labelled images only; the SAR 'Golmichi' images are quarantined until the mapping is reviewed by an expert.

## How groups and splits were made
- Mango: leaf groups, copy groups and capture bursts from AGL-MANGO-MD. The five-class splits of AGL-MANGO-MD v1.1.0-rc1 are inherited unchanged (frozen test tiers keep their meaning). Cutting Weevil, Die Back and Sooty Mould are split with the same rule (seed 42).
- Potato and Tomato (PlantVillage): leaf identity from the public PlantVillage leaf map ({st['plantvillage_leaf_map_matches']} images matched) united with perceptual-hash near-duplicate clusters. Potato's 2,152 images come from 535 leaves.
- Apple (Plant Pathology 2020): perceptual-hash near-duplicate clusters.
- Every split unit lies in exactly one split. Leakage checks: {st['leakage_checks']}.
- Exact duplicates: one copy kept per class; cross-class duplicates and cross-class leaf groups are quarantined, never auto-resolved.

## Evaluation tiers
`test_known_device` (all crops) and `test_heldout_device` (Mango only: five SAR phones never seen in training; only Anthracnose now has an adequate sample) are separate tiers and must never be pooled. Apple, Potato and Tomato have no device information, so no device-independence claim is possible for them.

## Known limitations
- Apple, Potato and Tomato come from one source each; PlantVillage images are laboratory photographs on plain backgrounds; there are no field or C270 images in this dataset.
- About 36% of Tomato images have no known leaf identity; undetected same-leaf photographs may remain across splits.
- Mango limitations from AGL-MANGO-MD carry over (device/source bias, single-source classes, unverified labels, ABCGMP overlap with MangoLeafBD).
- Labels are source labels; none has been verified by an expert.
- Licences differ by source (`metadata/licences.json`); MangoLeafBD is non-commercial.

## Use for training
Reference this dataset by version and by the split manifests. Do not copy or edit it. A different sampling strategy is a new experiment manifest, not a new dataset.
"""
open(os.path.join(R, "documentation", "DATASET_CARD.md"), "w", encoding="utf-8").write(card)
open(os.path.join(R, "documentation", "CHANGELOG.md"), "w", encoding="utf-8").write(f"# Changelog\n\n## 1.0.0 ({dt.date.today()})\n\nFirst release. Built by `build_agl_multicrop_md.py` from AGL-MANGO-MD v1.0.0 and v1.1.0-rc1 (Mango) and Datasets.zip (Apple, Potato, Tomato). Supersedes the original MangoLeafBD-only Mango baseline for development. The original datasets and the production model remain available for comparison and rollback.\n")
open(os.path.join(R, "README.md"), "w", encoding="utf-8").write("# AGL-MULTICROP-MD 1.0.0\n\nStart with `documentation/DATASET_CARD.md`. Verify with `FREEZE_CHECKSUMS.sha256`. Frozen; do not modify.\n")
dm = {"dataset_id": "AGL-MULTICROP-MD", "version": "1.0.0", "status": "FROZEN", "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "statistics": st,
      "taxonomy_classes_in_model": int(tax.training_eligible.astype(str).str.lower().eq("true").sum()), "image_manifest_sha256": sha(os.path.join(R, "manifests", "image_manifest.csv")),
      "split_assignment_sha256": sha(os.path.join(R, "splits", "split_assignment.csv")), "builder": "AGRILENS repository datasets/dataset_tools/build_agl_multicrop_md.py"}
json.dump(dm, open(os.path.join(R, "dataset_manifest.json"), "w"), indent=1, default=str)
files = []
for dp, _, fs in os.walk(R):
    for f in fs:
        p = os.path.join(dp, f); rel = os.path.relpath(p, R).replace(os.sep, "/")
        if rel != "FREEZE_CHECKSUMS.sha256": files.append((rel, p))
with ThreadPoolExecutor(8) as ex: hs = list(ex.map(lambda t: sha(t[1]), files))
open(os.path.join(R, "FREEZE_CHECKSUMS.sha256"), "w", encoding="utf-8").write("".join(f"{h}  {r}\n" for (r, _), h in sorted(zip(files, hs))))
print("frozen", len(files), "files; checksum file sha256", sha(os.path.join(R, "FREEZE_CHECKSUMS.sha256")))
