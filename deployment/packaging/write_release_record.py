#!/usr/bin/env python3
"""Write deployment/release_manifests/<release>.json: the identity and evidence of one release candidate (versions, checksums of the
device package, model, dataset freeze file, gate calibration and the single release evaluation, and the evaluation verdicts).
  python write_release_record.py --dataset <AGL-MULTICROP-MD-1.0.0> --tests-junit <junit.xml>"""
import argparse, hashlib, json, os, xml.etree.ElementTree as ET
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); PKG = os.path.join(R, "AGRILENS_RaspberryPi")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
ap = argparse.ArgumentParser(); ap.add_argument("--dataset", required=True); ap.add_argument("--tests-junit", required=True); a = ap.parse_args()
man = json.load(open(os.path.join(PKG, "RELEASE_MANIFEST.json"), encoding="utf-8"))
cal_p = os.path.join(R, "training", "evaluation", "calibration_1.0.0", "FROZEN_GATE_CALIBRATION.json"); cal = json.load(open(cal_p))
ev_dir = os.path.join(R, "training", "evaluation", "release_eval_1.0.0"); ev = json.load(open(os.path.join(ev_dir, "release_evaluation.json")))
suite = ET.parse(a.tests_junit).getroot(); suite = suite.find("testsuite") if suite.tag == "testsuites" else suite
t = {k: int(suite.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}; t["passed"] = t["tests"] - t["failures"] - t["errors"] - t["skipped"]
rec = {"release": man["release"], "app_version": man["app_version"], "build_timestamp": man["build_timestamp"],
       "model": {"id": man["model_id"], "version": man["model_version"], "sha256": man["model_sha256"], "bytes": os.path.getsize(os.path.join(PKG, "agrilens.onnx")),
                 "manifest": "models/candidates/agrilens-multicrop-1.0.0/MODEL_MANIFEST.json"},
       "dataset": {"id_version": man["dataset_version"], "freeze_checksums_sha256": sha(os.path.join(a.dataset, "FREEZE_CHECKSUMS.sha256"))},
       "device_package": {"path": "AGRILENS_RaspberryPi/", "files": len(man["files_sha256"]), "SHA256SUMS_sha256": sha(os.path.join(PKG, "SHA256SUMS")),
                          "RELEASE_MANIFEST_sha256": sha(os.path.join(PKG, "RELEASE_MANIFEST.json")), "main_py_sha256": man["files_sha256"]["main.py"],
                          "ota_files_fetched_by_devices": man["ota_files_fetched_by_devices"]},
       "gate_calibration": {"file": "training/evaluation/calibration_1.0.0/FROZEN_GATE_CALIBRATION.json", "sha256": sha(cal_p), "confidence": cal["confidence_threshold"], "margin": cal["ood_margin"], "ood_logit": cal["ood_logit_frozen"]},
       "release_evaluation": {"lock_file_sha256": sha(os.path.join(ev_dir, "RELEASE_EVALUATION_RUN_ONCE.json")), "results_sha256": sha(os.path.join(ev_dir, "release_evaluation.json")), "criteria": ev["criteria"]},
       "automated_tests": t,
       "rollback_release": {"path": "deployment/rollback/AGRILENS-5.0.1-rollback/", "SHA256SUMS_sha256": sha(os.path.join(R, "deployment", "rollback", "AGRILENS-5.0.1-rollback", "SHA256SUMS"))},
       "status": {"published": False, "deployed": False, "raspberry_pi_validation": "pending", "c270_field_validation": "pending", "expert_label_review": "pending",
                  "release_criteria": "ALL PASS" if ev["criteria"]["ALL_PASS"] else "FAILED: " + ", ".join(k for k, v in ev["criteria"].items() if k != "ALL_PASS" and not v)}}
out = os.path.join(R, "deployment", "release_manifests", man["release"] + ".json"); os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(rec, open(out, "w", encoding="utf-8", newline="\n"), indent=1); print(out); print(json.dumps(rec["status"], indent=1))
