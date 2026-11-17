#!/usr/bin/env python3
"""Analyse completed blinded expert forms against the answer key. READ-ONLY with respect to the dataset: nothing here edits a manifest, an image or a label.
Output (default expert_review_results/): EXPERT_REVIEW_ANALYSIS.md, agreement tables, proposed_label_corrections.csv (PROPOSALS ONLY).
  python analyse_expert_review.py --forms <dir with expert_response_form_<ID>.csv files> [--out dir] [--min-experts-for-relabel 2]
Relabelling rule built in: a correction is only PROPOSED when the expert (or the consensus of at least --min-experts-for-relabel experts) gives a definite, non-'unsure'
label different from the source label on an adequate image. A proposal never changes data; it needs adjudication and a new dataset version."""
import argparse, glob, itertools, json, os
import numpy as np, pandas as pd
ROOT = r"D:\AGRILENS_Training\AGL-MANGO-MD"
ap = argparse.ArgumentParser(); ap.add_argument("--forms", required=True); ap.add_argument("--out", default=ROOT + r"\expert_review_results"); ap.add_argument("--key", default=ROOT + r"\expert_review_package_KEY\answer_key.csv")
ap.add_argument("--min-experts-for-relabel", type=int, default=2); ap.add_argument("--simulated", action="store_true", help="mark outputs as a test with simulated answers"); a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
CODE = {"anthracnose": "MNG001", "bacterial canker": "MNG002", "gall midge": "MNG005", "healthy": "MNG006", "powdery mildew": "MNG007"}; NAME = {v: k.title() for k, v in CODE.items()}
def norm(x):
    s = str(x).strip().lower() if isinstance(x, str) else ""
    if not s: return ""
    if s in CODE: return CODE[s]
    if s.startswith("other"): return "OTHER"
    if s.startswith("uncertain") or s.startswith("unsure"): return "UNCERTAIN"
    return "OTHER" if s else ""
key = pd.read_csv(a.key); key["set"] = key.review_set.str.extract(r"^(S\d)")[0]
forms = {}
for p in sorted(glob.glob(os.path.join(a.forms, "expert_response_form_*.csv"))):
    f = pd.read_csv(p).fillna(""); eid = os.path.basename(p)[len("expert_response_form_"):-4]; f["code"] = f.expert_label.map(norm)
    f["conf"] = f.iloc[:, [i for i, c in enumerate(f.columns) if c.startswith("confidence")][0]].astype(str).str.lower().str.strip(); f["adequate"] = f.image_adequate_yes_no.astype(str).str.lower().str.strip(); forms[eid] = f.set_index("item_id")
assert forms, "no completed forms found"
L = [f"# Expert review analysis{' (SIMULATED TEST DATA, NOT A REAL REVIEW)' if a.simulated else ''}\n", f"Experts: {', '.join(forms)}. Items in key: {len(key)}. This analysis is read-only: no label, image or manifest was changed. Original labels and model predictions are kept in the answer key.\n"]
# per expert completeness
rows = []
for e, f in forms.items():
    ans = f[f.code != ""]; rows.append({"expert": e, "answered": len(ans), "of": len(f), "definite_label": int(ans.code.isin(NAME).sum()), "uncertain": int((ans.code == "UNCERTAIN").sum()), "other": int((ans.code == "OTHER").sum()),
                                        "image_not_adequate": int((ans.adequate.str.startswith("n")).sum()), "tranche1_answered": int(ans[ans.tranche == 1].shape[0]) if "tranche" in ans.columns else None})
L += ["## 1. Completion\n", pd.DataFrame(rows).to_markdown(index=False), "\n"]
# long table
long = []
for e, f in forms.items():
    d = f[f.code != ""].copy(); d["expert"] = e; long.append(d.reset_index()[["item_id", "expert", "code", "conf", "adequate", "symptoms_seen", "notes"]])
long = pd.concat(long); m = long.merge(key, on="item_id")
definite = m[m.code.isin(NAME)]
# inter-expert agreement
if len(forms) >= 2:
    from sklearn.metrics import cohen_kappa_score
    ag = []
    for e1, e2 in itertools.combinations(forms, 2):
        j = long[long.expert == e1].merge(long[long.expert == e2], on="item_id"); jj = j[j.code_x.isin(NAME) & j.code_y.isin(NAME)]
        ag.append({"pair": f"{e1} / {e2}", "items_both_definite": len(jj), "percent_agreement": round(float((jj.code_x == jj.code_y).mean()), 3) if len(jj) else None, "cohen_kappa": round(float(cohen_kappa_score(jj.code_x, jj.code_y)), 3) if len(jj) > 1 and jj.code_x.nunique() > 1 else None})
    L += ["## 2. Agreement between experts\n", pd.DataFrame(ag).to_markdown(index=False), "\n"]
    # consensus
    def cons(g):
        c = g[g.code.isin(NAME)].code.value_counts()
        if len(c) and c.iloc[0] >= a.min_experts_for_relabel and (len(c) == 1 or c.iloc[0] > c.iloc[1]): return c.index[0]
        return "NO_CONSENSUS"
    cs = long.groupby("item_id").apply(cons).rename("consensus"); m = m.merge(cs, on="item_id", how="left")
else:
    L += ["## 2. Agreement between experts\n", "Only one expert so far: no inter-expert agreement can be computed, and no relabel proposal can reach the consensus threshold. Proposals below are flagged single-expert.\n"]
    m["consensus"] = "SINGLE_EXPERT"
base = definite.copy()
L += ["## 3. Expert against the dataset (source) label\n"]
base["agrees_source"] = base.code == base.source_label; base["agrees_model"] = base.code == base.model_prediction
t = base.groupby("set").agg(items=("item_id", "nunique"), answers=("code", "size"), expert_agrees_with_source=("agrees_source", "mean"), expert_agrees_with_model=("agrees_model", "mean")).round(3)
t.insert(0, "set meaning", [base[base.set == s].review_set.iloc[0] for s in t.index]); L += [t.to_markdown(), "\n"]
L += ["Reading guide: S5 are confidently correct predictions on easy cases and estimate how often the source label is wrong where the model and label agree. S1 and S2 are the Anthracnose / Gall Midge confusions, S3 the Healthy leaves called Gall Midge, S6 SAR files filed under both Anthracnose and Golmichi, S7 label-doubt images.\n"]
cmx = pd.crosstab(base.code.map(lambda c: NAME.get(c, c)), base.source_label.map(lambda c: NAME.get(c, c))); L += ["### Expert label (rows) against source label (columns), all definite answers\n", cmx.to_markdown(), "\n"]
# error sets: who is right
err = base[base.set.isin(["S1", "S2", "S3", "S4"])].copy()
def outcome(r):
    if r.code == r.source_label: return "expert = source label (model wrong)"
    if r.code == r.model_prediction: return "expert = model prediction (label doubtful)"
    return "expert = a third class"
err["outcome"] = err.apply(outcome, axis=1); o = pd.crosstab(err.review_set.str[:2], err.outcome); L += ["## 4. Disagreements between label and model: who does the expert side with?\n", o.to_markdown(), "\n"]
unc = m[m.set.isin(["S1", "S2", "S3", "S4"]) & m.code.isin(["UNCERTAIN", "OTHER"])].groupby(["set", "code"]).item_id.nunique().unstack(fill_value=0)
L += ["Items the expert called Uncertain or Other in those sets:\n", unc.to_markdown() if len(unc) else "none", "\n"]
# S6
s6 = base[base.set == "S6"].groupby("item_id").code.agg(lambda x: ",".join(NAME.get(c, c) for c in x)); L += ["## 5. Identical files filed under Anthracnose and Golmichi (S6)\n", f"Expert answers per file: {s6.value_counts().to_dict()}\n"]
# proposals
pro = base[(base.code != base.source_label) & (~base.conf.str.startswith("unsure")) & (~base.adequate.str.startswith("n"))].copy()
pro["priority"] = pro.source_label.map(lambda c: 0 if c in ("MNG001", "MNG005", "MNG006") else 1).astype(int) + pro.code.map(lambda c: 0 if c in ("MNG001", "MNG005", "MNG006") else 1).astype(int)
if len(forms) >= 2: pro = pro.merge(cs.rename("consensus2"), on="item_id", how="left"); pro["meets_relabel_rule"] = pro.consensus2.eq(pro.code)
else: pro["meets_relabel_rule"] = False
pro["proposed_action"] = np.where(pro.meets_relabel_rule, "PROPOSE relabel in a NEW dataset version after adjudication", "single-expert disagreement: adjudicate (second expert or user decision) before any action")
pro["proposed_label"] = pro.code.map(lambda c: NAME.get(c, c)); pro["source_label_name"] = pro.source_label.map(lambda c: NAME.get(c, c)); pro["model_prediction_name"] = pro.model_prediction.map(lambda c: NAME.get(c, c))
pro = pro.sort_values(["priority", "set", "item_id"])[["priority", "item_id", "master_image_id", "review_set", "source_label_name", "proposed_label", "model_prediction_name", "expert", "conf", "symptoms_seen", "notes", "meets_relabel_rule", "proposed_action"]]
pro.to_csv(os.path.join(a.out, "proposed_label_corrections.csv"), index=False); base.to_csv(os.path.join(a.out, "expert_vs_key_all_answers.csv"), index=False)
L += ["## 6. Proposed label corrections (PROPOSALS ONLY)\n", f"{len(pro)} answers disagree with the source label on adequate images with confidence above 'unsure'; {int(pro.meets_relabel_rule.sum())} meet the relabel rule (consensus of at least {a.min_experts_for_relabel} experts). Priority 0 = Anthracnose, Gall Midge or Healthy on both sides. The master dataset and the frozen release are not modified; a correction needs adjudication and a new dataset version.\n"]
L += [pro.groupby(["source_label_name", "proposed_label"]).size().rename("answers").reset_index().to_markdown(index=False) if len(pro) else "none", "\n"]
sym = base[base.set.isin(["S1", "S2", "S5"]) & base.symptoms_seen.astype(str).str.len().gt(0)].groupby(["source_label", "code"]).symptoms_seen.apply(lambda x: " | ".join(x.head(5)))
sym.to_csv(os.path.join(a.out, "symptom_notes_sample.csv")); L += ["## 7. What this does not show\n", "The review set is not a random sample of the dataset, so the rates above are not dataset-wide label-noise rates. Agreement with the source label in the S5 controls is the closest indication. The expert saw only the photograph; a field visit may be needed for some conditions.\n"]
open(os.path.join(a.out, "EXPERT_REVIEW_ANALYSIS.md"), "w", encoding="utf-8").write("\n".join(L)); print("analysis written:", len(base), "definite answers,", len(pro), "proposals")
