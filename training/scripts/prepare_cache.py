#!/usr/bin/env python3
"""Build the resized training cache for AGL-MULTICROP-MD (outside the dataset). Each image is SHA-256-checked against the manifest first.
Usage: python prepare_cache.py --dataset <dataset root> --cache <cache dir>"""
import argparse, hashlib, json, os, sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd
from PIL import Image, ImageOps


def work(a):
    iid, path, sh, cache = a
    out = os.path.join(cache, iid + ".npy")
    if os.path.exists(out): return iid, "cached"
    data = open(path, "rb").read()
    if hashlib.sha256(data).hexdigest() != sh: return iid, "SHA_MISMATCH"
    import io
    with Image.open(io.BytesIO(data)) as im:
        im.draft("RGB", (600, 600)); im = ImageOps.exif_transpose(im).convert("RGB")
    w, h = im.size; s = 256.0 / min(w, h); im = im.resize((max(256, round(w * s)), max(256, round(h * s))), Image.BILINEAR)
    np.save(out, np.asarray(im, dtype=np.uint8)); return iid, "ok"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--dataset", required=True); ap.add_argument("--cache", required=True); a = ap.parse_args(); os.makedirs(a.cache, exist_ok=True)
    sp = pd.read_csv(os.path.join(a.dataset, "splits", "split_assignment.csv"))
    jobs = [(r.image_id, os.path.join(a.dataset, r.master_relpath.replace("/", os.sep)), r.sha256, a.cache) for r in sp.itertuples()]
    bad = 0; n = 0
    with ProcessPoolExecutor(14) as ex:
        for iid, st in ex.map(work, jobs, chunksize=16):
            n += 1; bad += st == "SHA_MISMATCH"
            if n % 2000 == 0: print("cache", n, flush=True)
    json.dump({"dataset": a.dataset, "images": n, "sha_mismatches": bad, "policy": "shorter side 256 bilinear, EXIF transpose, RGB uint8"}, open(os.path.join(a.cache, "_cache_info.json"), "w"), indent=1)
    print("done", n, "sha mismatches", bad); assert bad == 0
