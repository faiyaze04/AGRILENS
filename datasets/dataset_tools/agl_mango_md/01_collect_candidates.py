#!/usr/bin/env python3
"""AGL-MANGO-MD v1.0.0 step 1: enumerate every candidate Mango image from all sources (read-only) and measure it.
Output: work/candidates.csv, work/features_1280.npy (row order = candidates.csv), work/augmented_links.csv.
Originals are only read. ABCGMP leaf folders are extracted into work/abcgmp_extract (copy of zip content).
Usage: python 01_collect_candidates.py
"""
import csv, datetime as dt, hashlib, os, re, sys, zipfile
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from PIL import Image, ImageOps

BASE = r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.0.0"
WORK = os.path.join(BASE, "work")
WS = r"D:\AGRILENS_Training\mango_sar_mld1"
MLBD = r"d:\OneDrive - Faiyaz Personal\OneDrive\3. Shreyance related Documents\AgriLens\datasets\mango dataset"
SAR = os.path.join(WS, "data", "raw")
LEG = os.path.join(WS, "data", "old_mango", "process_data")
LEGAUG = os.path.join(WS, "data", "old_mango", "augmented")
ABC_ZIP = r"D:\Downloads\6  indian Fruit crops Fruit and Leaf Disease Dataset (version 1).zip"
ABC_X = os.path.join(WORK, "abcgmp_extract")
ONNX = os.path.join(WS, "data", "feature_extractor_copy.onnx")

CLS = {"Anthracnose": "MNG001", "Bacterial Canker": "MNG002", "Cutting Weevil": "MNG003", "Die Back": "MNG004",
       "Gall Midge": "MNG005", "Golmichi": "MNG005", "Healthy": "MNG006", "Powdery Mildew": "MNG007",
       "Sooty Mould": "MNG008", "Turning brown": "MNG009"}
ABC_MAP = {"Mango Bacterial Canker": "Bacterial Canker", "Mang Healthy Leaf": "Healthy"}
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
IMG = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def walk(root):
    for d, _, fs in os.walk(root):
        for f in sorted(fs):
            if f.lower().endswith(IMG):
                yield os.path.join(d, f)


def extract_abc():
    out = []
    with zipfile.ZipFile(ABC_ZIP) as z:
        for e in z.infolist():
            if e.is_dir():
                continue
            parts = e.filename.split("/")
            if len(parts) >= 2 and parts[-2] in ABC_MAP and e.filename.lower().endswith(IMG):
                dest = os.path.join(ABC_X, parts[-2], parts[-1])
                if not os.path.exists(dest):
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with z.open(e) as s, open(dest, "wb") as o:
                        o.write(s.read())
                out.append((dest, parts[-2], e.filename))
    return out


def candidates():
    rows = []
    for d in sorted(os.listdir(MLBD)):
        for p in walk(os.path.join(MLBD, d)):
            rows.append(dict(source="MANGOLEAFBD", path=p, src_class=d, src_rel=f"mango dataset/{d}/{os.path.basename(p)}",
                             origin="MangoLeafBD Mendeley hxsnvwty3r v1", licence="CC BY-NC 3.0 (non-commercial)", status="original_photo"))
    for p in walk(SAR):
        rel = os.path.relpath(p, SAR)
        parts = rel.split(os.sep)
        rows.append(dict(source="SAR25", path=p, src_class=parts[-2], src_rel=rel.replace(os.sep, "/"),
                         origin=f"SAR-MLD1-2025 Mendeley {'sd8hzpg69b' if 'part-1' in rel else 'j3bn63t4sp'} v4 ({parts[1]})",
                         licence="CC BY 4.0", status="original_photo"))
    for p in walk(LEG):
        rel = os.path.relpath(p, LEG)
        rows.append(dict(source="LEGACY", path=p, src_class=rel.split(os.sep)[0], src_rel="process data/" + rel.replace(os.sep, "/"),
                         origin="Legacy compilation Mendeley 7ghdbftp54 v1 (process data; background removed)",
                         licence="CC BY 4.0 per record; derivation from MangoLeafBD suspected (re-licence concern)",
                         status="background_removed_derivative"))
    for p, f, member in extract_abc():
        rows.append(dict(source="ABCGMP", path=p, src_class=ABC_MAP[f], src_rel="zip:" + member,
                         origin="ABCGMP Mendeley fhbvmpcyy2 (local zip 'version 1'; leaf folders only)",
                         licence="CC BY 4.0 per v2 record (v1 unverified)", status="original_photo"))
    return rows


def name_time(name):
    m = re.match(r"(\d{8})_(\d{6})", name)
    if m:
        try:
            return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").isoformat()
        except ValueError:
            return ""
    m = re.match(r"^(\d{13})", name)
    if m:
        try:
            return dt.datetime.fromtimestamp(int(m.group(1)) / 1000, dt.timezone.utc).replace(tzinfo=None).isoformat()
        except Exception:
            return ""
    return ""


def dhash(g, n=8):
    a = np.asarray(Image.fromarray(g).resize((n + 1, n), Image.BILINEAR), dtype=np.float32)
    bits = (a[:, 1:] > a[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def measure(rec):
    p = rec["path"]
    out = {"sha256": "", "bytes": os.path.getsize(p), "ok": False, "error": ""}
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    out["sha256"] = h.hexdigest()
    try:
        with Image.open(p) as im:
            fmt = im.format
            im.load()
            raw_w, raw_h = im.size
            ex = im.getexif()
            make, model = str(ex.get(271, "") or "").strip(), str(ex.get(272, "") or "").strip()
            exif_dt = str(ex.get(306, "") or "").replace("\x00", "").strip()
            try:
                sub = ex.get_ifd(0x8769)
                exif_dt = str(sub.get(36867, exif_dt) or exif_dt).replace("\x00", "").strip()
            except Exception:
                pass
            im2 = ImageOps.exif_transpose(im).convert("RGB")
        w, h_ = im2.size
        out.update(ok=True, format=fmt, raw_w=raw_w, raw_h=raw_h, w=w, h=h_, make=make, model=model, exif_datetime=exif_dt)
        s = 240.0 / min(w, h_)
        sm = im2.resize((max(1, round(w * s)), max(1, round(h_ * s))), Image.BILINEAR) if s < 1 else im2
        a = np.asarray(sm, dtype=np.float32) / 255.0
        mx, mn = a.max(2), a.min(2)
        sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
        fg = (sat > 0.15) & (mx > 0.08)
        gray = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]) * 255
        out["fg_frac"] = float(fg.mean())
        out["fg_lum"] = float(gray[fg].mean()) if fg.any() else 0.0
        lap = gray[1:-1, 1:-1] * 4 - gray[:-2, 1:-1] - gray[2:, 1:-1] - gray[1:-1, :-2] - gray[1:-1, 2:]
        out["sharp"] = float(lap.var())
        out["lum_mean"] = float(gray.mean())
        out["clip_hi"] = float((gray > 250).mean())
        out["clip_lo"] = float((gray < 5).mean())
        e = np.concatenate([fg[0], fg[-1], fg[:, 0], fg[:, -1]])
        out["border_fg"] = float(e.mean())
        g8 = np.asarray(sm.convert("L"))
        out["dhash"] = format(dhash(g8), "016x")
        # 224 centre crop for the production feature extractor (same as the kiosk-style centre crop)
        im3 = im2.copy()
        im3.draft("RGB", (640, 640))
        s2 = 256.0 / min(w, h_)
        r = im2.resize((max(256, round(w * s2)), max(256, round(h_ * s2))), Image.BILINEAR)
        rw, rh = r.size
        x0, y0 = (rw - 224) // 2, (rh - 224) // 2
        out["_crop"] = np.asarray(r.crop((x0, y0, x0 + 224, y0 + 224)), dtype=np.uint8)
    except Exception as ex_:
        out["error"] = f"{type(ex_).__name__}: {ex_}"[:200]
    return out


def main():
    os.makedirs(WORK, exist_ok=True)
    rows = candidates()
    print("candidates", len(rows), flush=True)
    for r in rows:
        r["orig_name"] = os.path.basename(r["path"])
        r["name_time"] = name_time(r["orig_name"])
    import onnxruntime as ort
    so = ort.SessionOptions(); so.intra_op_num_threads = 8
    sess = ort.InferenceSession(ONNX, so, providers=["CPUExecutionProvider"])
    feats, batch, idx = [], [], []
    zero = np.zeros((224, 224, 3), np.uint8)
    with ProcessPoolExecutor(max_workers=12) as ex:
        for i, m in enumerate(ex.map(measure, rows, chunksize=8), 1):
            crop = m.pop("_crop", None)
            rows[i - 1].update(m)
            batch.append(crop if crop is not None else zero)
            if len(batch) == 32 or i == len(rows):
                x = ((np.stack(batch).astype(np.float32) / 255.0 - MEAN) / STD).transpose(0, 3, 1, 2)
                feats.append(sess.run(None, {"input": np.ascontiguousarray(x)})[0])
                batch = []
            if i % 1000 == 0:
                print("done", i, flush=True)
    np.save(os.path.join(WORK, "features_1280.npy"), np.concatenate(feats).astype(np.float32))
    cols = ["source", "src_class", "orig_name", "src_rel", "path", "origin", "licence", "status", "sha256", "bytes", "ok", "error",
            "format", "raw_w", "raw_h", "w", "h", "make", "model", "exif_datetime", "name_time", "fg_frac", "fg_lum", "sharp",
            "lum_mean", "clip_hi", "clip_lo", "border_fg", "dhash"]
    with open(os.path.join(WORK, "candidates.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, cols, extrasaction="ignore"); wr.writeheader(); wr.writerows(rows)
    # legacy augmented set: names only (recorded, never copied)
    with open(os.path.join(WORK, "augmented_links.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f); wr.writerow(["aug_class", "aug_name", "aug_path", "sha256"])
        for p in walk(LEGAUG):
            hh = hashlib.sha256(open(p, "rb").read()).hexdigest()
            wr.writerow([os.path.basename(os.path.dirname(p)), os.path.basename(p), p, hh])
    print("finished", len(rows), flush=True)


if __name__ == "__main__":
    main()
