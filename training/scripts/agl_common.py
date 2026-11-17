"""Shared code for AGRILENS integrated-model training and evaluation on AGL-MULTICROP-MD.
Training never writes to the dataset. Images are read through the versioned split manifests; a resized cache (shorter side 256, bilinear,
EXIF-transposed, RGB, uint8) is built once outside the dataset and every cached file is created from an image whose SHA-256 was checked."""
import hashlib, json, os
import numpy as np
import pandas as pd
import torch

MEAN = (0.485, 0.456, 0.406); STD = (0.229, 0.224, 0.225)
MODEL_NAME = "mobilenetv4_conv_small.e2400_r224_in1k"
UNFREEZE = {"R1_last_stage": ["blocks.4", "conv_head", "norm_head", "classifier"], "R2_last_two_stages": ["blocks.3", "blocks.4", "conv_head", "norm_head", "classifier"]}
FROZEN_UNTIL = {"R1_last_stage": 4, "R2_last_two_stages": 3}   # number of leading blocks run under no_grad


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()


def verify_dataset(root, names=("manifests/image_manifest.csv", "manifests/class_taxonomy.csv", "splits/train.csv", "splits/val.csv", "splits/test_known_device.csv", "splits/test_heldout_device.csv")):
    rec = {}
    for ln in open(os.path.join(root, "FREEZE_CHECKSUMS.sha256"), encoding="utf-8"):
        if ln.strip(): h, p = ln.rstrip("\n").split("  ", 1); rec[p] = h
    for n in names: assert sha256(os.path.join(root, n.replace("/", os.sep))) == rec[n], f"frozen dataset file changed: {n}"
    return {n: rec[n] for n in names}


def taxonomy(root):
    t = pd.read_csv(os.path.join(root, "manifests", "class_taxonomy.csv")); t = t[t.training_eligible.astype(str).str.lower() == "true"].copy()
    t["model_index"] = t.model_index.astype(float).astype(int); t = t.sort_values("model_index")
    assert list(t.model_index) == list(range(len(t))); return t


def load_cached(cache, iid): return np.load(os.path.join(cache, iid + ".npy"))


def prefix_forward(model, x, n_frozen):
    x = model.bn1(model.conv_stem(x))
    for i in range(n_frozen): x = model.blocks[i](x)
    return x


def trainable_forward(model, x, n_frozen):
    for i in range(n_frozen, len(model.blocks)): x = model.blocks[i](x)
    x = model.global_pool(x); x = model.conv_head(x); x = model.norm_head(x); x = model.flatten(x); return model.classifier(x)


def metrics(y, P, K):
    y = np.asarray(y); pred = P.argmax(1); cm = np.zeros((K, K), int)
    for t, p in zip(y, pred): cm[t, p] += 1
    per = []
    for k in range(K):
        tp = cm[k, k]; fp = cm[:, k].sum() - tp; fn = cm[k].sum() - tp; pr = tp / (tp + fp) if tp + fp else float("nan"); rc = tp / (tp + fn) if tp + fn else float("nan")
        f1 = 2 * pr * rc / (pr + rc) if (pr == pr and rc == rc and pr + rc > 0) else (0.0 if cm[k].sum() else float("nan")); per.append({"support": int(cm[k].sum()), "precision": pr, "recall": rc, "f1": f1})
    present = [p["f1"] for p in per if p["support"] > 0]
    loss = float(-np.log(np.clip(P[np.arange(len(y)), y], 1e-12, 1)).mean()) if len(y) else float("nan")
    return {"n": int(len(y)), "accuracy": float((pred == y).mean()) if len(y) else float("nan"), "macro_f1": float(np.nanmean(present)) if present else float("nan"), "loss": loss, "per_class": per, "confusion_matrix": cm.tolist()}


@torch.no_grad()
def predict_single_view(model, cache, ids, bs=64):
    model.eval(); out = []
    for i in range(0, len(ids), bs):
        xs = []
        for iid in ids[i:i + bs]:
            a = load_cached(cache, iid); h, w = a.shape[:2]; t = (h - 224) // 2; l = (w - 224) // 2; xs.append(torch.from_numpy(a[t:t + 224, l:l + 224].copy()).permute(2, 0, 1))
        x = (torch.stack(xs).float() / 255.0 - torch.tensor(MEAN).view(1, 3, 1, 1)) / torch.tensor(STD).view(1, 3, 1, 1)
        out.append(torch.softmax(model(x), 1).numpy())
    return np.concatenate(out) if out else np.zeros((0, 1))
