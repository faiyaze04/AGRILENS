#!/usr/bin/env python3
"""Export the selected checkpoint to ONNX, verify shapes, class order and PyTorch/ONNX parity (criterion C9) on 256 validation images, and write
models/candidates/agrilens-multicrop-1.0.0/{agrilens.onnx, labels.txt, MODEL_MANIFEST.json}.
  python export_onnx.py --checkpoint <best.pt> --dataset <root> --cache <cache> --out <repo>/models/candidates/agrilens-multicrop-1.0.0 --prod-labels <models/production/.../labels.txt>"""
import argparse, hashlib, json, os, sys, time
import numpy as np, onnx, onnxruntime as ort, pandas as pd, timm, torch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agl_common import *
ap = argparse.ArgumentParser()
for n in ("checkpoint", "dataset", "cache", "out", "prod-labels"): ap.add_argument("--" + n, required=True)
ap.add_argument("--status", default="RELEASE CANDIDATE for AGRILENS 5.0.0 (not deployed)")
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
ck = torch.load(a.checkpoint, weights_only=False); classes = ck["classes"]; K = len(classes)
prod = [l.strip() for l in open(a.prod_labels, encoding="utf-8") if l.strip()]; assert classes == prod, "class order differs from the production labels.txt"
model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=K); model.load_state_dict(ck["state_dict"]); model.eval()
p = os.path.join(a.out, "agrilens.onnx")
torch.onnx.export(model, torch.randn(1, 3, 224, 224), p, input_names=["input"], output_names=["logits"], dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}}, opset_version=17, dynamo=False)
onnx.checker.check_model(onnx.load(p)); s = ort.InferenceSession(p, providers=["CPUExecutionProvider"])
ins, outs = s.get_inputs()[0], s.get_outputs()[0]; assert list(ins.shape[1:]) == [3, 224, 224] and outs.shape[-1] == K
va = pd.read_csv(os.path.join(a.dataset, "splits", "val.csv")).sample(256, random_state=0)
X = []
for iid in va.image_id:
    x = load_cached(a.cache, iid); h, w = x.shape[:2]; t, l = (h - 224) // 2, (w - 224) // 2; X.append(x[t:t + 224, l:l + 224])
X = ((np.stack(X).astype(np.float32) / 255 - np.array(MEAN, np.float32)) / np.array(STD, np.float32)).transpose(0, 3, 1, 2).copy()
with torch.no_grad(): tl = model(torch.from_numpy(X)).numpy()
ol = np.concatenate([s.run(None, {"input": X[i:i + 32]})[0] for i in range(0, len(X), 32)])
parity = {"images": len(X), "max_abs_logit_diff": float(np.abs(tl - ol).max()), "argmax_agreement": float((tl.argmax(1) == ol.argmax(1)).mean())}
assert parity["max_abs_logit_diff"] <= 1e-3 and parity["argmax_agreement"] == 1.0, parity
open(os.path.join(a.out, "labels.txt"), "w", encoding="utf-8", newline="\n").write("\n".join(classes) + "\n")
sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
man = {"model_id": "AGRILENS-MULTICROP", "model_version": "1.0.0", "status": a.status, "file": "agrilens.onnx", "sha256": sha(p), "bytes": os.path.getsize(p),
       "labels_file": "labels.txt", "labels_sha256": sha(os.path.join(a.out, "labels.txt")), "classes": classes, "class_order": "identical to the production 4.9.4 labels.txt",
       "architecture": {"timm": MODEL_NAME, "init": "ImageNet-1k", "recipe": ck["config"]["recipe"], "trainable": UNFREEZE[ck["config"]["recipe"]]},
       "input": {"name": "input", "shape": "N x 3 x 224 x 224", "preprocessing": "the application's Classifier (six views: full resize, square fit, 256/224 crop, each natural and screen-restored; logit ensemble); ImageNet mean/std"},
       "output": {"name": "logits", "num_classes": K}, "training": {"dataset": "AGL-MULTICROP-MD 1.0.0", "run_id": ck["run_id"], "best_epoch": ck["epoch"], "config": ck["config"]},
       "checkpoint_sha256": sha(a.checkpoint), "onnx_opset": 17, "parity_vs_pytorch_256_validation_images": parity,
       "software": {"torch": torch.__version__, "timm": timm.__version__, "onnx": onnx.__version__, "onnxruntime": ort.__version__}, "exported_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
json.dump(man, open(os.path.join(a.out, "MODEL_MANIFEST.json"), "w"), indent=1); print(json.dumps({k: man[k] for k in ("sha256", "bytes")}), parity)
