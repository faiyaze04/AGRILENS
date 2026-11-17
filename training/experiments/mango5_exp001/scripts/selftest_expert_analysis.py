"""Self-test of analyse_expert_review.py with SIMULATED expert answers (two fake experts). Output goes to a temp folder and is deleted. Nothing here is real review data."""
import os, subprocess, sys, tempfile, shutil
import numpy as np, pandas as pd
ROOT = r"D:\AGRILENS_Training\AGL-MANGO-MD"; key = pd.read_csv(ROOT + r"\expert_review_package_KEY\answer_key.csv"); form = pd.read_csv(ROOT + r"\expert_review_package\expert_response_form.csv").fillna("")
N = {"MNG001": "Anthracnose", "MNG002": "Bacterial Canker", "MNG005": "Gall Midge", "MNG006": "Healthy", "MNG007": "Powdery Mildew"}; rng = np.random.default_rng(0); d = tempfile.mkdtemp(prefix="expert_selftest_")
for e in ("SIM1", "SIM2"):
    f = form.copy(); labs = []
    for r in key.itertuples():
        u = rng.random(); lab = N.get(r.source_label, "Uncertain")
        if u < 0.12: lab = N[rng.choice(list(N))]
        elif u < 0.17: lab = "Uncertain"
        labs.append(lab)
    f["expert_label"] = labs; f["confidence_certain_probable_unsure"] = rng.choice(["certain", "probable", "unsure"], len(f)); f["image_adequate_yes_no"] = "yes"; f["symptoms_seen"] = "simulated"; f.to_csv(os.path.join(d, f"expert_response_form_{e}.csv"), index=False)
out = os.path.join(d, "out"); r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "analyse_expert_review.py"), "--forms", d, "--out", out, "--simulated"], capture_output=True, text=True)
print(r.stdout[-300:], r.stderr[-1500:]); print(sorted(os.listdir(out)) if os.path.exists(out) else "no output")
md = open(os.path.join(out, "EXPERT_REVIEW_ANALYSIS.md"), encoding="utf-8").read() if os.path.exists(out) else ""; print(md[:1800]); shutil.rmtree(d, ignore_errors=True)
