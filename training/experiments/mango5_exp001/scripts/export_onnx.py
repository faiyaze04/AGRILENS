#!/usr/bin/env python3
"""Export the selected checkpoint to an ONNX CANDIDATE (not integrated anywhere) and write the model version manifest.
  python export_onnx.py <run_id>
Writes only inside experiments/mango5_exp001/models. The production model, labels and app are not read or written."""
import json, os, sys, time
import numpy as np, onnx, onnxruntime as ort, pandas as pd, timm, torch
sys.path.insert(0, os.path.dirname(__file__))
from common import *

run = sys.argv[1]; sel = json.load(open(EXP + r"\SELECTION.json")); assert sel["selected_run"] == run
md = EXP + r"\models"; os.makedirs(md, exist_ok=True)
ck_path = EXP + rf"\runs\{run}\best.pt"; ck = torch.load(ck_path, weights_only=False)
model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=5); model.load_state_dict(ck["state_dict"]); model.eval()
mid = f"mango5_exp001_{run}_candidate"; onnx_path = md + rf"\{mid}.onnx"
torch.onnx.export(model, torch.randn(1, 3, 224, 224), onnx_path, input_names=["input"], output_names=["logits"], dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}}, opset_version=17, dynamo=False)
onnx.checker.check_model(onnx.load(onnx_path))
va = pd.read_csv(os.path.join(RC, "splits", "val.csv")).head(128)       # parity check on validation images only
X = np.stack([ (lambda a: a[(a.shape[0]-224)//2:(a.shape[0]-224)//2+224, (a.shape[1]-224)//2:(a.shape[1]-224)//2+224])(load_cached(i)) for i in va.master_image_id]).astype(np.float32) / 255.0
X = ((X - np.array(MEAN, np.float32)) / np.array(STD, np.float32)).transpose(0, 3, 1, 2).copy()
with torch.no_grad(): tl = model(torch.from_numpy(X)).numpy()
sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"]); ol = np.concatenate([sess.run(None, {"input": X[i:i + 32]})[0] for i in range(0, len(X), 32)])
parity = {"images": len(X), "max_abs_logit_diff": float(np.abs(tl - ol).max()), "argmax_agreement": float((tl.argmax(1) == ol.argmax(1)).mean())}
t = time.time(); [sess.run(None, {"input": X[:1]}) for _ in range(50)]; lat1 = (time.time() - t) / 50 * 1000
open(md + rf"\{mid}_labels.txt", "w").write("\n".join(f"{c}_{n.split(' (')[0].upper().replace(' ', '_')}" for c, n in CLASS_NAMES.items()) + "\n")
vm = json.load(open(EXP + rf"\runs\{run}\val_metrics.json")); summ = json.load(open(EXP + rf"\runs\{run}\summary.json"))
man = {"model_id": mid, "status": "EXPERIMENTAL CANDIDATE - not integrated, not deployed; production 24-class model, labels and thresholds untouched",
       "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "experiment": "mango5-exp001", "run_id": run, "mode": summ["mode"], "seed": summ["seed"], "best_epoch": summ["best_epoch"],
       "architecture": {"timm_name": MODEL_NAME, "pretrained_init": "ImageNet-1k (timm)", "num_classes": 5}, "classes": [f"{c} {CLASS_NAMES[c]}" for c in CLASSES],
       "provisional_class": "MNG005 Gall Midge (pending expert verification)",
       "input": {"name": "input", "shape": "N x 3 x 224 x 224", "preprocessing": "RGB, shorter side to 256 (bilinear), centre crop 224, scale to 0-1, ImageNet mean/std (outside the graph)"},
       "output": {"name": "logits", "note": "apply softmax; production thresholds (confidence 0.40, margin 0.12) are NOT changed or applied here"},
       "onnx": {"file": f"models/{mid}.onnx", "sha256": sha256(onnx_path), "bytes": os.path.getsize(onnx_path), "opset": 17, "parity_vs_pytorch_on_128_val_images": parity, "desktop_cpu_batch1_latency_ms": round(lat1, 2)},
       "checkpoint": {"file": f"runs/{run}/best.pt", "sha256": sha256(ck_path)}, "labels_file": f"models/{mid}_labels.txt",
       "dataset": {"id": "AGL-MANGO-MD", "version": "v1.1.0-rc1", "freeze_checksum_file_sha256": sha256(RC + r"\FREEZE_CHECKSUMS.sha256")},
       "config_sha256": sha256(EXP + rf"\configs\{run}.yaml"), "validation": {"accuracy": vm["accuracy"], "macro_f1": vm["macro_f1"], "loss": vm["loss"]},
       "software": {"torch": torch.__version__, "timm": timm.__version__, "onnx": onnx.__version__, "onnxruntime": ort.__version__},
       "claims_policy": "see AGL-MANGO-MD-v1.1.0-rc1/docs/EVALUATION_TIERS.md; no field-accuracy or device-independence claim beyond the evaluated tiers"}
json.dump(man, open(md + rf"\{mid}_VERSION_MANIFEST.json", "w"), indent=1); print(json.dumps(man["onnx"], indent=1))
