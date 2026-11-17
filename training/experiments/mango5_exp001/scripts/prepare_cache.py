#!/usr/bin/env python3
"""Decode every accepted image of the frozen dataset ONCE into a resized uint8 array (shorter side 256, BILINEAR, EXIF-transposed, RGB).
This is the fixed resize policy (same as the kiosk-style preprocessing: shorter side 256 then centre crop 224 at evaluation).
Each file is SHA-256 checked against the frozen manifest before use. The dataset is only read."""
import hashlib, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd
from PIL import Image, ImageOps
sys.path.insert(0, os.path.dirname(__file__))
from common import RC, CACHE, verify_frozen_files, sha256


def work(a):
    mid, rel, sh = a
    p = os.path.join(RC, rel.replace("/", os.sep))
    h = hashlib.sha256(open(p, "rb").read()).hexdigest()
    if h != sh: return mid, "SHA_MISMATCH"
    with Image.open(p) as im:
        im.draft("RGB", (600, 600))
        im = ImageOps.exif_transpose(im).convert("RGB")
    w, hh = im.size; s = 256.0 / min(w, hh)
    im = im.resize((max(256, round(w * s)), max(256, round(hh * s))), Image.BILINEAR)
    np.save(os.path.join(CACHE, mid + ".npy"), np.asarray(im, dtype=np.uint8))
    return mid, "ok"


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    print("frozen manifests verified:", list(verify_frozen_files()))
    m = pd.read_csv(os.path.join(RC, "manifests", "master_image_manifest.csv"), low_memory=False)
    a = m[m.inclusion_status == "accepted"]
    jobs = [(r.master_image_id, r.master_relpath, r.sha256) for r in a.itertuples() if not os.path.exists(os.path.join(CACHE, r.master_image_id + ".npy"))]
    print("to cache", len(jobs), "of", len(a), flush=True)
    bad = 0
    with ProcessPoolExecutor(14) as ex:
        for i, (mid, st) in enumerate(ex.map(work, jobs, chunksize=8), 1):
            if st != "ok": bad += 1; print("PROBLEM", mid, st)
            if i % 1000 == 0: print("cached", i, flush=True)
    json.dump({"policy": "shorter side 256 BILINEAR, EXIF transpose, RGB, uint8", "images": int(len(a)), "sha_mismatches": bad, "dataset": "AGL-MANGO-MD v1.1.0-rc1"}, open(os.path.join(CACHE, "_cache_info.json"), "w"))
    print("done, sha mismatches", bad)
