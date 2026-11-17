#!/usr/bin/env python3
"""Build the BLINDED agronomic review package (expert sees images only; labels and model predictions are in a separate key folder).
Sources are read-only: frozen dataset images and the stored predictions of the selected candidate. Nothing is relabelled."""
import json, os, random, shutil, sys
import numpy as np, pandas as pd
from PIL import Image, ImageOps
sys.path.insert(0, os.path.dirname(__file__))
from common import *

ROOT = r"D:\AGRILENS_Training\AGL-MANGO-MD"; PK = ROOT + r"\expert_review_package"; KEY = ROOT + r"\expert_review_package_KEY"
for d in (PK + r"\images", KEY): os.makedirs(d, exist_ok=True)
EA = EXP + r"\error_analysis"; rng = random.Random(7)
H = pd.read_csv(EA + r"\error_table_heldout_device.csv"); K = pd.read_csv(EA + r"\error_table_known_device.csv")
man = pd.read_csv(RC + r"\manifests\master_image_manifest.csv", low_memory=False).set_index("master_image_id")
items = []   # (image_id, set, tier)
def add(df, s, tier, n=None, how="all"):
    if how == "conf": df = df.sort_values("conf", ascending=False)
    if n is not None and how == "mixed": top = df.sort_values("conf", ascending=False).head(n // 2); rest = df.drop(top.index).sample(min(n - len(top), len(df) - len(top)), random_state=3); df = pd.concat([top, rest])
    elif n is not None: df = df.head(n)
    for r in df.itertuples(): items.append((r.master_image_id, s, tier))
add(H[(H.true == "MNG001") & (H.pred == "MNG005")], "S1 Anthracnose predicted Gall Midge (held-out devices)", "heldout", 30, "mixed")
add(H[(H.true == "MNG005") & (H.pred == "MNG001")], "S2 Gall Midge predicted Anthracnose (held-out devices)", "heldout", 30, "mixed")
add(K[(K.true == "MNG006") & (K.pred == "MNG005")], "S3 Healthy predicted Gall Midge (known devices)", "known", None, "all")
oth = pd.concat([K[~K.correct & ~((K.true == "MNG006") & (K.pred == "MNG005"))], H[~H.correct & ~(((H.true == "MNG001") & (H.pred == "MNG005")) | ((H.true == "MNG005") & (H.pred == "MNG001")))]])
add(oth.sample(min(24, len(oth)), random_state=5), "S4 Other errors", "mixed", None, "all")
for c, n in (("MNG001", 25), ("MNG005", 25), ("MNG006", 25), ("MNG007", 25), ("MNG002", 8)):
    pool = pd.concat([K[(K.true == c) & K.correct], H[(H.true == c) & H.correct]]); pool = pool[pool.conf >= 0.8]
    add(pool.sample(min(n, len(pool)), random_state=11), f"S5 Correct, confident ({CLASS_NAMES[c]})", "mixed", None, "all")
q = man[(man.inclusion_status == "quarantined")]
conf = q[(q.quarantine_hold == "HOLD_label_conflict") & (q.class_id == "MNG001")]
for i in conf.index: items.append((i, "S6 SAR file filed under both Anthracnose and Golmichi", "quarantine"))
dbt = q[q.quarantine_hold == "HOLD_label_doubt"]
for c in ("MNG001", "MNG005"):
    s = dbt[dbt.class_id == c]; 
    for i in s.sample(10, random_state=2).index: items.append((i, "S7 Label-doubt (quarantined, neighbours disagree)", "quarantine"))
seen, uniq = set(), []
for i, s, t in items:
    if i not in seen: seen.add(i); uniq.append((i, s, t))
rng.shuffle(uniq)
rows, key = [], []
pred = pd.concat([K, H]).drop_duplicates("master_image_id").set_index("master_image_id")
for n, (i, s, t) in enumerate(uniq, 1):
    iid = f"ITEM-{n:03d}"; r = man.loc[i]; p = os.path.join(RC, r.master_relpath.replace("/", os.sep))
    with Image.open(p) as im:
        im.draft("RGB", (1200, 1200)); im = ImageOps.exif_transpose(im).convert("RGB"); im.thumbnail((900, 900)); im.save(PK + rf"\images\{iid}.jpg", quality=88)
    pr = pred.loc[i] if i in pred.index else None
    key.append({"item_id": iid, "master_image_id": i, "review_set": s, "source_label": r.class_id, "source_label_name": CLASS_NAMES.get(r.class_id, ""), "model_prediction": pr.pred if pr is not None else "",
                "model_confidence": round(float(pr.conf), 3) if pr is not None else "", "model_margin": round(float(pr.margin), 3) if pr is not None else "", "source": r.source_id, "device": r.capture_device, "date": r.capture_date,
                "original_filename": r.original_filename, "quarantine_hold": r.quarantine_hold if isinstance(r.quarantine_hold, str) else "", "tier": t})
    rows.append({"item_id": iid, "expert_label": "", "confidence_certain_probable_unsure": "", "symptoms_seen": "", "image_adequate_yes_no": "", "notes": ""})
pd.DataFrame(key).to_csv(KEY + r"\answer_key.csv", index=False); pd.DataFrame(rows).to_csv(PK + r"\expert_response_form.csv", index=False)
# blinded gallery (25 items per page)
per = 25; pages = (len(rows) + per - 1) // per
css = "<style>body{font-family:Arial;margin:16px}.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}.c{border:1px solid #bbb;padding:6px}img{width:100%}h4{margin:4px 0}</style>"
for pg in range(pages):
    sub = rows[pg * per:(pg + 1) * per]; nav = " ".join(f'<a href="page{k + 1}.html">{k + 1}</a>' for k in range(pages))
    body = "".join(f'<div class="c"><h4>{r["item_id"]}</h4><a href="images/{r["item_id"]}.jpg"><img loading="lazy" src="images/{r["item_id"]}.jpg"></a></div>' for r in sub)
    open(PK + rf"\page{pg + 1}.html", "w", encoding="utf-8").write(f"<html><head><meta charset='utf-8'>{css}</head><body><h3>AGRILENS mango leaf review: page {pg + 1} of {pages}</h3><p>Pages: {nav}. Record your answer for each ITEM in expert_response_form.csv. Click an image to enlarge.</p><div class='g'>{body}</div></body></html>")
open(PK + r"\index.html", "w", encoding="utf-8").write(f"<html><head><meta charset='utf-8'>{css}</head><body><h2>AGRILENS mango leaf review package</h2><p>{len(rows)} images in random order, in {pages} pages. Start with README_FOR_EXPERT.md.</p>" + " ".join(f'<a href="page{k + 1}.html">page {k + 1}</a>' for k in range(pages)) + "</body></html>")
# unblinded discussion sheet (key folder)
k = pd.DataFrame(key); html = "".join(f'<div class="c"><h4>{r.item_id} | source: {r.source_label_name or "?"} | model: {CLASS_NAMES.get(r.model_prediction, r.model_prediction)} {r.model_confidence}</h4><p>{r.review_set}<br>{r.source} {r.device} {r.date}</p><img loading="lazy" src="../expert_review_package/images/{r.item_id}.jpg"></div>' for r in k.itertuples())
open(KEY + r"\discussion_sheet_UNBLINDED.html", "w", encoding="utf-8").write(f"<html><head><meta charset='utf-8'>{css}</head><body><h3>UNBLINDED discussion sheet: open only after the expert has completed the blind form</h3><div class='g'>{html}</div></body></html>")
print(len(rows), "items;", k.review_set.value_counts().to_dict())
