#!/usr/bin/env python3
"""Order the blinded review in two tranches (priority first) without revealing which items are errors, add the tranche column to the response form,
and build the distributable zip (the answer key is NOT included)."""
import hashlib, os, random, zipfile
import pandas as pd
ROOT = r"D:\AGRILENS_Training\AGL-MANGO-MD"; PK = ROOT + r"\expert_review_package"; KEY = ROOT + r"\expert_review_package_KEY"
k = pd.read_csv(KEY + r"\answer_key.csv"); f = pd.read_csv(PK + r"\expert_response_form.csv")
assert f.iloc[:, 1:].fillna("").astype(str).apply(lambda c: c.str.len()).sum().sum() == 0 or "tranche" in f.columns, "form already contains answers; refusing to rebuild"
if "tranche" in f.columns: f = f.drop(columns=["tranche"])
pri_sets = ("S1", "S2", "S3", "S6", "S7"); pri_classes = ("Anthracnose", "Gall Midge", "Healthy")
def tr(r):
    s = r.review_set
    if s.startswith(pri_sets): return 1
    if s.startswith("S5") and any(c in s for c in pri_classes): return 1
    return 2
k["tranche"] = k.apply(tr, axis=1); k.to_csv(KEY + r"\answer_key.csv", index=False)
f = f.merge(k[["item_id", "tranche"]], on="item_id"); f.insert(1, "tranche", f.pop("tranche")); f.to_csv(PK + r"\expert_response_form.csv", index=False)
css = "<style>body{font-family:Arial;margin:16px}.g{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px}.c{border:1px solid #bbb;padding:6px}img{width:100%}h4{margin:4px 0}</style>"
rng = random.Random(21); per = 25; idx = []
for t in (1, 2):
    ids = k[k.tranche == t].item_id.tolist(); rng.shuffle(ids); pages = (len(ids) + per - 1) // per
    for p in range(pages):
        sub = ids[p * per:(p + 1) * per]; nav = " ".join(f'<a href="tranche{t}_page{q + 1}.html">{q + 1}</a>' for q in range(pages))
        body = "".join(f'<div class="c"><h4>{i}</h4><a href="images/{i}.jpg"><img loading="lazy" src="images/{i}.jpg"></a></div>' for i in sub)
        open(PK + rf"\tranche{t}_page{p + 1}.html", "w", encoding="utf-8").write(f"<html><head><meta charset='utf-8'>{css}</head><body><h3>Tranche {t}, page {p + 1} of {pages}</h3><p>Pages: {nav}. Record each answer in expert_response_form.csv (column expert_label). Click an image to enlarge.</p><div class='g'>{body}</div></body></html>")
    idx.append((t, len(ids), pages))
open(PK + r"\index.html", "w", encoding="utf-8").write(f"<html><head><meta charset='utf-8'>{css}</head><body><h2>AGRILENS mango leaf review package</h2><p>Please do Tranche 1 first, then Tranche 2. Read README_FOR_EXPERT.md.</p>" + "".join(f"<p><b>Tranche {t}</b>: {n} images, " + " ".join(f'<a href="tranche{t}_page{q + 1}.html">page {q + 1}</a>' for q in range(p)) + "</p>" for t, n, p in idx) + "</body></html>")
for old in [x for x in os.listdir(PK) if x.startswith("page") and x.endswith(".html")]: os.remove(os.path.join(PK, old))
z = ROOT + r"\expert_review_package_v1.zip"
if os.path.exists(z): os.remove(z)
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    for dp, _, fs in os.walk(PK):
        for x in fs: zf.write(os.path.join(dp, x), os.path.join("expert_review_package", os.path.relpath(os.path.join(dp, x), PK)).replace(os.sep, "/"))
open(ROOT + r"\expert_review_package_v1.zip.sha256", "w").write(hashlib.sha256(open(z, "rb").read()).hexdigest() + "  expert_review_package_v1.zip\n")
print(idx, round(os.path.getsize(z) / 2**20, 1), "MB")
