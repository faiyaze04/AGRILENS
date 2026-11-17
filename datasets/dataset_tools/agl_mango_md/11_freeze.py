#!/usr/bin/env python3
"""Freeze step for AGL-MANGO-MD v1.1.0-rc1: record v1.0.0 checksums, write dataset_manifest.json, FREEZE_CHECKSUMS.sha256,
RELEASE_MANIFEST.json and FROZEN.txt. Read-only attributes and ACLs are applied afterwards by the operator (PowerShell)."""
import datetime as dt, hashlib, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor

ROOT = r"D:\AGRILENS_Training\AGL-MANGO-MD"; V0 = ROOT + r"\AGL-MANGO-MD-v1.0.0"; RC = ROOT + r"\AGL-MANGO-MD-v1.1.0-rc1"
REPO = r"d:\OneDrive - Faiyaz Personal\OneDrive\3. Shreyance related Documents\AgriLens\AGRILENS"
EXEMPT = {"FREEZE_CHECKSUMS.sha256", "RELEASE_MANIFEST.json", "FROZEN.txt"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()


def tree(root, skip=()):
    out = {}
    for dp, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(dp, f); rel = os.path.relpath(p, root).replace(os.sep, "/")
            if rel in skip or "__pycache__" in rel: continue
            out[rel] = p
    return out


def hash_tree(t):
    with ThreadPoolExecutor(8) as ex: return dict(zip(t, ex.map(sha, t.values())))


# 1. v1.0.0 record
t0 = tree(V0); h0 = hash_tree(t0)
open(RC + r"\provenance\v1.0.0_FILE_CHECKSUMS.sha256", "w", encoding="utf-8").write("".join(f"{h0[p]}  {p}\n" for p in sorted(h0)))
print("v1.0.0 files", len(h0), flush=True)
# 2. dataset_manifest.json
stat = json.load(open(RC + r"\manifests\dataset_statistics.json"))
chk = json.load(open(RC + r"\reports\split_checks.json"))
classes = {"MNG001": "Anthracnose", "MNG002": "Bacterial Canker", "MNG005": "Gall Midge (provisional)", "MNG006": "Healthy", "MNG007": "Powdery Mildew"}
dm = {"dataset_id": "AGL-MANGO-MD", "name": "AGRILENS Mango Master Dataset, five-class experimental baseline", "version": "v1.1.0-rc1", "directory": "AGL-MANGO-MD-v1.1.0-rc1",
      "derived_from": "AGL-MANGO-MD-v1.0.0 (preserved unchanged)", "classes": classes,
      "sources": {"SAR25": "SAR-MLD1-2025 (Mendeley sd8hzpg69b, j3bn63t4sp, v4), CC BY 4.0", "MANGOLEAFBD": "MangoLeafBD (Mendeley hxsnvwty3r v1), CC BY-NC 3.0 non-commercial",
                  "ABCGMP": "ABCGMP six-crop dataset, mango leaf folders only (Mendeley fhbvmpcyy2), CC BY 4.0 per v2 record; overlaps MangoLeafBD for Bacterial Canker and Healthy",
                  "C270": "reserved, none collected"},
      "totals": stat["totals"], "per_class": {k: {kk: v[kk] for kk in ("accepted", "accepted_leaf_groups", "in_splits", "excluded_cross_device_leaf", "quarantine_holds")} for k, v in stat["per_class"].items()}}
json.dump(dm, open(RC + r"\manifests\dataset_manifest.json", "w"), indent=1)
# 3. checksums of rc1
t1 = tree(RC, skip=EXEMPT); h1 = hash_tree(t1)
open(RC + r"\FREEZE_CHECKSUMS.sha256", "w", encoding="utf-8").write("".join(f"{h1[p]}  {p}\n" for p in sorted(h1)))
size = sum(os.path.getsize(p) for p in t1.values())
imgs = [p for p in h1 if p.startswith(("images/", "quarantine/", "rejected_by_review/"))]
prod = {"main.py": sha(REPO + r"\AGRILENS_RaspberryPi\main.py"), "agrilens.onnx": sha(REPO + r"\AGRILENS_RaspberryPi\agrilens.onnx")}
git = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout.strip().splitlines()
rm = {"dataset_id": "AGL-MANGO-MD", "version": "v1.1.0-rc1", "release_candidate": True, "status": "FROZEN (immutable experimental baseline)",
      "frozen_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "authorised_by": "user, 2026-11-17",
      "training_authorised": False, "derived_from": "AGL-MANGO-MD-v1.0.0", "v1_0_0_checksum_record": "provenance/v1.0.0_FILE_CHECKSUMS.sha256",
      "classes": classes, "excluded_from_this_release": ["MNG003 Cutting Weevil", "MNG004 Die Back", "MNG008 Sooty Mould", "MNG009 Turning Brown (provisional)", "background-removed supplementary images", "legacy augmented images (records only)"],
      "counts": stat["totals"], "per_class": stat["per_class"],
      "splits": {"files": ["train", "val", "test_known_device", "test_heldout_device"], "seed": chk["seed"], "burst_gap_s": chk["burst_gap_s"], "heldout_devices": chk["heldout_devices"]},
      "evaluation_tiers": "docs/EVALUATION_TIERS.md", "heldout_device_evaluability": chk["heldout_device_evaluability"], "leakage_checks": chk["leakage_checks"],
      "quarantine": "docs/DATASET_READINESS_REPORT.md section B; manifests/quarantine_decisions.csv", "known_limitations": "docs/KNOWN_LIMITATIONS.md",
      "files": {"count": len(h1), "image_files": len(imgs), "bytes": size, "checksum_file": "FREEZE_CHECKSUMS.sha256", "checksum_file_sha256": sha(RC + r"\FREEZE_CHECKSUMS.sha256"),
                "exempt_from_checksum_file": sorted(EXEMPT)},
      "production_unchanged": {"sha256": prod, "git_status_entries": len(git), "note": "AGRILENS_RaspberryPi files, 24-class ONNX model, labels and deployment were not modified"}}
json.dump(rm, open(RC + r"\RELEASE_MANIFEST.json", "w"), indent=1)
open(RC + r"\FROZEN.txt", "w").write(f"AGL-MANGO-MD v1.1.0-rc1 frozen {rm['frozen_utc']}\nDo not modify. Verify with: python scripts/verify_release.py <this directory>\nChecksum file SHA-256: {rm['files']['checksum_file_sha256']}\nTraining is not authorised by this freeze.\n")
print(json.dumps({"files": len(h1), "images": len(imgs), "bytes": size, "prod": prod, "git_entries": len(git)}, indent=1))
