#!/usr/bin/env python3
"""AGL-MANGO-MD v1.0.0 step 2: duplicate/near-duplicate detection, leaf grouping, label-conflict detection and per-image decisions.
Input : work/candidates.csv, work/features_1280.npy, work/augmented_links.csv
Output: work/decisions.csv, work/duplicate_pairs.csv, work/group_summary.json
Rules (all conservative; nothing is auto-resolved when labels conflict -> quarantine):
  edges used to GROUP leaves (same MNG class only):
    E1 identical SHA-256          E2 feature cosine >= 0.97
    E3 same source, dHash hamming <= 4 AND cosine >= 0.90
    E4 same source+class, capture time within 30 s AND cosine >= 0.80 (same leaf / burst; photos stay distinct images)
    E5 MangoLeafBD same class and same file-name stem after removing '(Custom)' repeats / ' (n)' (zoom/rotate derivatives)
    E6 legacy 'process data' image with the same file-name stem as a MangoLeafBD image (derivative with background removed)
  COPY edges (E1,E2,E3,E5,E6) additionally define copy groups: first is likely_original, others likely_derivative.
  cross-class evidence: identical SHA, cosine>=0.97, or (hamming<=4 and cosine>=0.90), or E6 stem match with differing class.
"""
import csv, datetime as dt, json, os, re
from collections import Counter, defaultdict
import numpy as np

BASE = r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.0.0"
W = os.path.join(BASE, "work")
CLS = {"Anthracnose": "MNG001", "Bacterial Canker": "MNG002", "Cutting Weevil": "MNG003", "Die Back": "MNG004",
       "Gall Midge": "MNG005", "Golmichi": "MNG005", "Healthy": "MNG006", "Powdery Mildew": "MNG007",
       "Sooty Mould": "MNG008", "Turning brown": "MNG009"}
POP = np.array([bin(i).count("1") for i in range(256)], dtype=np.uint8)


class UF:
    def __init__(s, n): s.p = list(range(n))
    def f(s, x):
        while s.p[x] != x:
            s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def u(s, a, b):
        a, b = s.f(a), s.f(b)
        if a != b: s.p[max(a, b)] = min(a, b)


def stem(name):
    s = os.path.splitext(name)[0]
    s = re.sub(r"(\s*\(Custom\))+$", "", s)
    s = re.sub(r"\s*\(\d+\)$", "", s)
    return s.strip().lower()


def ptime(r):
    for v in (r["exif_datetime"], ):
        v = (v or "").strip()
        for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try: return dt.datetime.strptime(v, fmt).timestamp()
            except ValueError: pass
    if r["name_time"]:
        try: return dt.datetime.fromisoformat(r["name_time"]).timestamp()
        except ValueError: pass
    return np.nan


def main():
    R = list(csv.DictReader(open(os.path.join(W, "candidates.csv"), newline="", encoding="utf-8")))
    F = np.load(os.path.join(W, "features_1280.npy")); F /= np.maximum(np.linalg.norm(F, axis=1, keepdims=True), 1e-9)
    n = len(R); assert len(F) == n
    for i, r in enumerate(R):
        r["i"] = i; r["mng"] = CLS[r["src_class"]]; r["ok_b"] = r["ok"] == "True"
        r["t"] = ptime(r) if r["ok_b"] else np.nan
        r["stem"] = stem(r["orig_name"])
    src = np.array([r["source"] for r in R]); mng = np.array([r["mng"] for r in R])
    leg = (src == "LEGACY"); t = np.array([r["t"] for r in R])
    ok = np.array([r["ok_b"] for r in R])
    dh = np.array([int(r["dhash"], 16) if r["dhash"] else 0 for r in R], dtype=np.uint64)
    key = np.array([f"{r['source']}|{r['src_class']}" for r in R])
    leaf, copy = UF(n), UF(n)
    pairs = []  # (i, j, kind, cos, ham)
    cross = defaultdict(list)  # i -> list of (j, kind)

    def add(i, j, kind, c, h, same_class, is_copy):
        pairs.append((i, j, kind, round(float(c), 4), int(h) if h is not None else ""))
        if same_class:
            leaf.u(i, j)
            if is_copy: copy.u(i, j)
        else:
            cross[i].append((j, kind)); cross[j].append((i, kind))

    # E1 identical SHA
    bysha = defaultdict(list)
    for r in R:
        if r["sha256"]: bysha[r["sha256"]].append(r["i"])
    for s, ids in bysha.items():
        for a in ids[1:]:
            add(ids[0], a, "E1_exact_sha", 1.0, 0, mng[ids[0]] == mng[a], True)
    # E5 / E6 name based
    ml = defaultdict(list)
    for r in R:
        if r["source"] == "MANGOLEAFBD": ml[(r["src_class"], r["stem"])].append(r["i"])
    for k, ids in ml.items():
        for a in ids[1:]:
            add(ids[0], a, "E5_name_stem", float(F[ids[0]] @ F[a]), None, True, True)
    mlstem = defaultdict(list)
    for r in R:
        if r["source"] == "MANGOLEAFBD": mlstem[r["stem"]].append(r["i"])
    legacy_parent = {}
    for r in R:
        if r["source"] == "LEGACY" and r["stem"] in mlstem:
            p = mlstem[r["stem"]]
            same = [x for x in p if mng[x] == r["mng"]]
            tgt = same[0] if same else p[0]
            legacy_parent[r["i"]] = tgt
            add(tgt, r["i"], "E6_legacy_stem", 0.0, None, mng[tgt] == r["mng"], True)
    # E2-E4 by features (chunked)
    CH = 600
    for a in range(0, n, CH):
        b = min(n, a + CH)
        S = F[a:b] @ F.T
        x = dh[a:b, None] ^ dh[None, :]
        ham = POP[x.view(np.uint8).reshape(b - a, n, 8)].sum(2)
        dtm = np.abs(t[a:b, None] - t[None, :])
        dom = leg[a:b, None] == leg[None, :]
        valid = ok[a:b, None] & ok[None, :] & dom
        idx = np.arange(a, b)[:, None]; jdx = np.arange(n)[None, :]
        valid &= jdx > idx
        bothsar = (src[a:b, None] == "SAR25") & (src[None, :] == "SAR25")
        # production features collapse within MangoLeafBD/ABCGMP/legacy (cos>=0.97 for tens of thousands of pairs), so for any
        # non-SAR pair the feature evidence must be backed by a perceptual-hash match (ham<=10 / <=16 for time links).
        e2 = valid & (S >= 0.97) & (bothsar | (ham <= 6))
        e3 = valid & (src[a:b, None] == src[None, :]) & (ham <= 4) & (S >= 0.90)
        e4 = valid & (key[a:b, None] == key[None, :]) & (dtm <= 30) & np.where(bothsar, S >= 0.80, (S >= 0.95) & (ham <= 8))
        xc = valid & (mng[a:b, None] != mng[None, :]) & (((S >= 0.97) & (bothsar | (ham <= 6))) | ((ham <= 4) & (S >= 0.90)))
        for kind, M, cp in (("E2_cos>=0.97", e2, True), ("E3_hash+cos", e3, True), ("E4_time+cos", e4, False)):
            M = M & (mng[a:b, None] == mng[None, :])
            for ii, jj in zip(*np.nonzero(M)):
                add(a + ii, jj, kind, S[ii, jj], ham[ii, jj], True, cp)
        for ii, jj in zip(*np.nonzero(xc)):
            add(a + ii, jj, "X_cross_class", S[ii, jj], ham[ii, jj], False, False)
        print("pairs", b, len(pairs), flush=True)
    # cross-class from E1 / E6 already added through add(); label conflicts = images with any cross edge
    lg = [leaf.f(i) for i in range(n)]; cg = [copy.f(i) for i in range(n)]
    gsize = Counter(lg); csize = Counter(cg)
    # master group ids (stable ordering by first member)
    gid = {}; cid = {}
    for i in range(n):
        gid.setdefault(lg[i], f"G{len(gid) + 1:05d}")
        cid.setdefault(cg[i], f"D{len(cid) + 1:05d}")
    # likely original within copy group: prefers non-'(Custom) (Custom)' name, then larger pixels, then name
    def rank(r):
        dbl = 1 if re.search(r"\(Custom\)\s*\(Custom\)", r["orig_name"]) else 0
        return (dbl, -int(r["w"] or 0) * int(r["h"] or 0), r["orig_name"])
    members = defaultdict(list)
    for r in R: members[cg[r["i"]]].append(r)
    for g, ms in members.items():
        ms.sort(key=rank)
        for k, r in enumerate(ms):
            r["orig_flag"] = "likely_original" if k == 0 else "likely_derivative"
    # quality thresholds per source
    sharp_p1 = {}
    for s in set(src):
        v = np.array([float(r["sharp"]) for r in R if r["source"] == s and r["ok_b"] and r["sharp"]])
        sharp_p1[s] = float(np.percentile(v, 1)) if len(v) else 0.0
    # kNN label disagreement within source (excluding same leaf group)
    knn_flag = {}
    for s in set(src):
        ids = np.nonzero((src == s) & ok & ~leg | ((src == s) & ok & leg))[0]
        if len(ids) < 50: continue
        Fs = F[ids]; ms = mng[ids]; gs = np.array([lg[i] for i in ids])
        for a in range(0, len(ids), 800):
            S = Fs[a:a + 800] @ Fs.T
            S[gs[a:a + 800, None] == gs[None, :]] = -2
            top = np.argpartition(-S, 10, axis=1)[:, :10]
            for k in range(top.shape[0]):
                lab = Counter(ms[top[k]])
                c, m = lab.most_common(1)[0]
                if c != ms[a + k] and m >= 8:
                    knn_flag[ids[a + k]] = f"{ms[a + k]}->{c}({m}/10)"
    # decisions
    out = []
    exact_keep = {}
    for s, ids in bysha.items():
        same = [i for i in ids if True]
        by_m = defaultdict(list)
        for i in same: by_m[mng[i]].append(i)
        for m, l in by_m.items():
            l.sort(key=lambda i: (R[i]["source"] != "SAR25", R[i]["src_rel"]))
            exact_keep[s, m] = l[0]
    for r in R:
        i = r["i"]; reasons, flags = [], []
        dec = "accepted"
        if not r["ok_b"]:
            dec = "rejected"; reasons.append("undecodable:" + r["error"])
        else:
            fg, lum = float(r["fg_frac"]), float(r["fg_lum"])
            if r["source"] == "LEGACY" and i in legacy_parent:
                dec = "rejected"; reasons.append("derivative_of_MANGOLEAFBD_original(background removed)")
            if fg < 0.02: dec = "rejected"; reasons.append("no_visible_leaf_fg<0.02")
            elif lum < 20 or lum > 245: dec = "rejected"; reasons.append("leaf_luminance_out_of_range")
            if dec != "rejected" and len(bysha[r["sha256"]]) > 1 and exact_keep[r["sha256"], r["mng"]] != i \
                    and not any(m != r["mng"] for m in [mng[j] for j in bysha[r["sha256"]]]):
                dec = "rejected"; reasons.append("within_class_exact_duplicate_of:" + R[exact_keep[r["sha256"], r["mng"]]]["src_rel"])
            if dec != "rejected":
                if i in cross:
                    dec = "quarantined"; reasons.append("cross_class_duplicate_or_label_conflict:" + ";".join(sorted({f"{R[j]['mng']}/{k}" for j, k in cross[i]}))[:150])
                if 0.02 <= fg < 0.05: dec = "quarantined"; reasons.append("tiny_leaf_fg<0.05")
                if r["source"] != "LEGACY" and float(r["sharp"]) < sharp_p1[r["source"]]:
                    dec = "quarantined"; reasons.append("borderline_blur_below_source_p1")
                if i in knn_flag and r["source"] != "LEGACY":
                    dec = "quarantined"; reasons.append("kNN_label_disagreement:" + knn_flag[i])
                if float(r["border_fg"]) > 0.35: flags.append("cropped_framing")
                if min(int(r["w"]), int(r["h"])) < 200: flags.append("low_res")
                if float(r["clip_hi"]) > 0.25: flags.append("overexposed")
                if r["source"] != "LEGACY" and float(r["clip_lo"]) > 0.35: flags.append("underexposed")
        if r["source"] == "LEGACY" and dec == "accepted": dec = "accepted_supplementary"; flags.append("background_removed")
        if r["mng"] in ("MNG005", "MNG009"): flags.append("provisional_class_mapping")
        sizeg, sizec = gsize[lg[i]], csize[cg[i]]
        if r["source"] == "SAR25": ostat = "original_photo"
        else: ostat = r["orig_flag"] if sizec > 1 else "original_photo"
        if r["source"] == "LEGACY": ostat = "background_removed_original" if i not in legacy_parent else "derivative"
        out.append(dict(idx=i, source=r["source"], mng=r["mng"], src_rel=r["src_rel"], orig_name=r["orig_name"],
                        leaf_group_id=gid[lg[i]], leaf_group_size=sizeg, copy_group_id=cid[cg[i]], copy_group_size=sizec,
                        orig_status=ostat, decision=dec, reasons="|".join(reasons), flags="|".join(flags),
                        legacy_parent=R[legacy_parent[i]]["src_rel"] if i in legacy_parent else "",
                        legacy_parent_leaf_group=gid[lg[legacy_parent[i]]] if i in legacy_parent else ""))
    with open(os.path.join(W, "decisions.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, list(out[0].keys())); wr.writeheader(); wr.writerows(out)
    with open(os.path.join(W, "duplicate_pairs.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["a_src_rel", "a_class", "b_src_rel", "b_class", "evidence", "cosine", "dhash_hamming", "same_class"])
        for i, j, k, c, h in pairs:
            wr.writerow([R[i]["src_rel"], R[i]["mng"], R[j]["src_rel"], R[j]["mng"], k, c, h, R[i]["mng"] == R[j]["mng"]])
    summ = {"candidates": n, "decisions": Counter(o["decision"] for o in out),
            "by_source_decision": {f"{s}|{d}": c for (s, d), c in Counter((o["source"], o["decision"]) for o in out).items()},
            "leaf_groups_by_source": {s: len({lg[i] for i in range(n) if src[i] == s}) for s in set(src)},
            "largest_leaf_groups": gsize.most_common(8), "edge_counts": Counter(p[2] for p in pairs),
            "sharp_p1": sharp_p1, "knn_flags": len(knn_flag)}
    json.dump(summ, open(os.path.join(W, "group_summary.json"), "w"), indent=1, default=dict)
    print(json.dumps(summ, indent=1, default=dict))


if __name__ == "__main__":
    main()
