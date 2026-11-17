#!/usr/bin/env python3
"""AGL-MANGO-MD v1.0.0 step 4: PROPOSED leaf/session-grouped splits (nothing is trained).
Rules: only inclusion_status == accepted rows; split unit = leaf group, merged with capture-day sessions for MangoLeafBD
(leaf identity is unreliable there: production features collapse, only ~1,800 leaves are claimed for 4,000 images);
copy groups never cross splits; augmented / derivative records inherit the split of their leaf group; ~70/15/15 per class
by image count, seed 42. Also writes cross-source holdout manifests and an empty C270 evaluation manifest.
"""
import csv, json, os, random
from collections import Counter, defaultdict

BASE = r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.0.0"
SEED = 42; TARGET = {"train": 0.70, "val": 0.15, "test": 0.15}


class UF:
    def __init__(s): s.p = {}
    def f(s, x):
        s.p.setdefault(x, x)
        while s.p[x] != x:
            s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def u(s, a, b):
        a, b = s.f(a), s.f(b)
        if a != b: s.p[b] = a


def main():
    rows = list(csv.DictReader(open(os.path.join(BASE, "manifests", "master_image_manifest.csv"), newline="", encoding="utf-8")))
    acc = [r for r in rows if r["inclusion_status"] == "accepted"]
    ufA, ufB = UF(), UF()   # A: leaf+copy groups only; B: A plus capture-day sessions (MangoLeafBD)
    for r in acc:
        for u in (ufA, ufB): u.u("L" + r["leaf_group_id"], "C" + r["duplicate_group_id"])
        if r["source_id"] == "MANGOLEAFBD" and r["capture_date"] != "unknown":
            ufB.u("L" + r["leaf_group_id"], f"S|{r['class_id']}|{r['capture_date']}|{r['capture_device']}")
    # per class: use session-merged units when they are usable (>=10 units and largest <=40% of class); otherwise leaf units + flag
    basis = {}
    for c in sorted({r["class_id"] for r in acc}):
        sub = [r for r in acc if r["class_id"] == c]
        cnt = Counter(ufB.f("L" + r["leaf_group_id"]) for r in sub)
        basis[c] = "session+leaf" if (len(cnt) >= 10 and max(cnt.values()) <= 0.40 * len(sub)) else "leaf_only_SESSION_LEAKAGE_RISK"
    unit = {r["master_image_id"]: (ufB if basis[r["class_id"]] == "session+leaf" else ufA).f("L" + r["leaf_group_id"]) for r in acc}
    ucls = defaultdict(set)
    for r in acc: ucls[unit[r["master_image_id"]]].add(r["class_id"])
    assert all(len(v) == 1 for v in ucls.values()), "unit spans classes"
    rng = random.Random(SEED)
    assign = {}
    report = {}
    for c in sorted({r["class_id"] for r in acc}):
        us = defaultdict(list)
        for r in acc:
            if r["class_id"] == c: us[unit[r["master_image_id"]]].append(r)
        keys = sorted(us); rng.shuffle(keys); keys.sort(key=lambda k: -len(us[k]))
        tot = sum(len(v) for v in us.values()); cur = Counter()
        for k in keys:
            s = max(TARGET, key=lambda s: TARGET[s] * tot - cur[s]); cur[s] += len(us[k])
            for r in us[k]: assign[r["master_image_id"]] = s
        report[c] = {"split_basis": basis[c], "images": tot, "units": len(us), "largest_unit": max(len(v) for v in us.values()), **{s: cur[s] for s in TARGET}}
    sp = os.path.join(BASE, "splits"); os.makedirs(sp, exist_ok=True)
    cols = ["master_image_id", "class_id", "split", "source_id", "capture_device", "capture_date", "leaf_group_id", "split_unit", "master_relpath"]
    with open(os.path.join(sp, "split_assignment.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, cols); w.writeheader()
        for r in acc: w.writerow({**{k: r[k] for k in cols if k in r}, "split": assign[r["master_image_id"]], "split_unit": unit[r["master_image_id"]]})
    for s in TARGET:
        with open(os.path.join(sp, f"{s}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, cols); w.writeheader()
            for r in acc:
                if assign[r["master_image_id"]] == s: w.writerow({**{k: r[k] for k in cols if k in r}, "split": s, "split_unit": unit[r["master_image_id"]]})
    # leakage checks
    leak = {}
    for name, key in (("leaf_group", "leaf_group_id"), ("copy_group", "duplicate_group_id"), ("split_unit", None)):
        m = defaultdict(set)
        for r in acc: m[unit[r["master_image_id"]] if key is None else r[key]].add(assign[r["master_image_id"]])
        leak[name] = sum(1 for v in m.values() if len(v) > 1)
    # derivatives/augmented inherit
    u_by_leaf = {r["leaf_group_id"]: assign[r["master_image_id"]] for r in acc}
    inh = Counter()
    with open(os.path.join(sp, "derivative_split_inheritance.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["master_image_id", "inclusion_status", "inherited_split"])
        for r in rows:
            if r["inclusion_status"] in ("excluded_augmented", "rejected") and r["original_or_augmented"] in ("augmented", "derivative"):
                s = u_by_leaf.get(r["leaf_group_id"], "none(parent not in any split)"); inh[s] += 1
                w.writerow([r["master_image_id"], r["inclusion_status"], s])
    # per split mix
    mix = {}
    for s in TARGET:
        sub = [r for r in acc if assign[r["master_image_id"]] == s]
        mix[s] = {"images": len(sub), "by_source": dict(Counter(r["source_id"] for r in sub)),
                  "by_device": dict(Counter(r["capture_device"] for r in sub)), "by_class": dict(Counter(r["class_id"] for r in sub))}
    # source-holdout manifests
    pairs = [("SAR25", "MANGOLEAFBD", ["MNG001", "MNG005", "MNG006", "MNG007"]), ("MANGOLEAFBD", "SAR25", ["MNG001", "MNG005", "MNG006", "MNG007"]),
             ("MANGOLEAFBD", "ABCGMP", ["MNG002", "MNG006"]), ("ABCGMP", "MANGOLEAFBD", ["MNG002", "MNG006"])]
    hold = {}
    for a, b, cl in pairs:
        n = 0
        with open(os.path.join(sp, f"holdout_train_{a}_test_{b}.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["master_image_id", "class_id", "role", "source_id", "master_relpath"])
            for r in acc:
                if r["class_id"] in cl and r["source_id"] in (a, b):
                    w.writerow([r["master_image_id"], r["class_id"], "train" if r["source_id"] == a else "test", r["source_id"], r["master_relpath"]]); n += 1
        hold[f"{a}->{b}"] = {"classes": cl, "images": n}
    with open(os.path.join(sp, "c270_field_evaluation_manifest.csv"), "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["image_id", "class_id", "leaf_id", "session_id", "capture_device", "capture_date", "path", "expert_label", "expert_id"])
    out = {"seed": SEED, "target": TARGET, "per_class": report, "leakage_violations": leak, "per_split_mix": mix, "holdouts": hold,
           "derivative_inheritance": dict(inh)}
    json.dump(out, open(os.path.join(sp, "split_report.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("per_class", "leakage_violations", "holdouts", "derivative_inheritance")}, indent=1))


if __name__ == "__main__":
    main()
