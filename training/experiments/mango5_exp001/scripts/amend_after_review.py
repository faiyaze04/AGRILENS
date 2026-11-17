#!/usr/bin/env python3
"""Documentation amendment after the review: write the v2 version manifest (cross-source results moved to 'exploratory_diagnostics').
The candidate files (ONNX, checkpoint, v1 manifest) are NOT modified; the as-built copies are preserved in candidates/."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

run = "B_partial_ft_s43"; md = EXP + r"\models"; v1 = json.load(open(md + rf"\mango5_exp001_{run}_candidate_VERSION_MANIFEST.json"))
v2 = {k: v for k, v in v1.items() if k != "test_tiers_run_once"}
tiers = v1["test_tiers_run_once"]
v2["official_test_tiers_run_once"] = {k: v for k, v in tiers.items() if not k.startswith("diagnostic")}
v2["exploratory_diagnostics"] = {"status": "EXPLORATORY ONLY. Different throw-away models trained on diagnostic manifests; not results of this candidate; not used for selection.", "disclosure": "CROSS_SOURCE_DIAGNOSTICS_DISCLOSURE.md",
                                 "results": {k: v for k, v in tiers.items() if k.startswith("diagnostic")}}
v2["manifest_version"] = 2; v2["supersedes"] = "mango5_exp001_B_partial_ft_s43_candidate_VERSION_MANIFEST.json (kept unchanged)"
v2["candidate_bundle"] = {"folder": "candidates/mango5_exp001_B_partial_ft_s43_v1", "checksums": "CANDIDATE_CHECKSUMS.sha256", "write_protected": True}
v2["status"] = "EXPERIMENTAL CANDIDATE (selected, accepted as experimental candidate 2026-11-17). NOT approved for production; not integrated; production app, model, labels and thresholds untouched."
v2["known_issues"] = ["held-out-device accuracy 79.4% (Anthracnose and Gall Midge only)", "errors concentrated in particular sessions and in the Anthracnose / Gall Midge pair (ERROR_ANALYSIS_REPORT.md)",
                      "experiments scored a single 256/224 view; the kiosk ensembles six views (see field_validation/C270_COLLECTION_READINESS_REPORT.md)", "Gall Midge label provisional", "no field (C270) data yet"]
json.dump(v2, open(md + rf"\mango5_exp001_{run}_candidate_VERSION_MANIFEST_v2.json", "w"), indent=1); print("v2 manifest written; v1 sha256", sha256(md + rf"\mango5_exp001_{run}_candidate_VERSION_MANIFEST.json"))
