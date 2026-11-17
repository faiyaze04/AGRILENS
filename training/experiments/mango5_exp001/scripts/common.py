"""Shared code for AGL-MANGO five-class experiments (dataset v1.1.0-rc1). No production file is read or written."""
import hashlib, json, os
import numpy as np
import pandas as pd
import torch

RC = r"D:\AGRILENS_Training\AGL-MANGO-MD\AGL-MANGO-MD-v1.1.0-rc1"
EXP = r"D:\AGRILENS_Training\AGL-MANGO-MD\experiments\mango5_exp001"
CACHE = EXP + r"\cache"
CLASSES = ["MNG001", "MNG002", "MNG005", "MNG006", "MNG007"]
CLASS_NAMES = {"MNG001": "Anthracnose", "MNG002": "Bacterial Canker", "MNG005": "Gall Midge (provisional)", "MNG006": "Healthy", "MNG007": "Powdery Mildew"}
CIDX = {c: i for i, c in enumerate(CLASSES)}
MEAN = (0.485, 0.456, 0.406); STD = (0.229, 0.224, 0.225)
CONF_T, MARGIN_T = 0.40, 0.12   # production thresholds, used for REPORTING only
MODEL_NAME = "mobilenetv4_conv_small.e2400_r224_in1k"
UNFREEZE = {"A_frozen_head": ["classifier"], "B_partial_ft": ["blocks.4", "conv_head", "norm_head", "classifier"]}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()


def verify_frozen_files(names=("splits/train.csv", "splits/val.csv", "splits/test_known_device.csv", "splits/test_heldout_device.csv", "manifests/master_image_manifest.csv")):
    """Abort if a frozen manifest differs from FREEZE_CHECKSUMS.sha256."""
    rec = {}
    for ln in open(RC + r"\FREEZE_CHECKSUMS.sha256", encoding="utf-8"):
        if ln.strip(): h, p = ln.rstrip("\n").split("  ", 1); rec[p] = h
    for n in names:
        assert sha256(os.path.join(RC, n.replace("/", os.sep))) == rec[n], f"frozen file changed: {n}"
    return {n: rec[n] for n in names}


def load_cached(mid):
    return np.load(os.path.join(CACHE, mid + ".npy"))


def prefix_forward(model, x, mode):
    """Frozen part of the network (run under no_grad). A: everything up to the pooled 1280-d feature; B: stem and stages 0-3."""
    x = model.bn1(model.conv_stem(x))
    for i in range(4): x = model.blocks[i](x)
    if mode == "A_frozen_head":
        x = model.blocks[4](x); x = model.global_pool(x); x = model.conv_head(x); x = model.norm_head(x); x = model.flatten(x)
    return x


def trainable_forward(model, x, mode):
    if mode == "A_frozen_head": return model.classifier(x)
    x = model.blocks[4](x); x = model.global_pool(x); x = model.conv_head(x); x = model.norm_head(x); x = model.flatten(x)
    return model.classifier(x)


def metrics_from_probs(y, P, classes_present=None):
    """y: int labels (0..4), P: n x 5 probabilities. Returns dict with accuracy, per-class P/R/F1, macro-F1 over classes with support, confusion matrix."""
    n = len(y); K = P.shape[1]; pred = P.argmax(1)
    cm = np.zeros((K, K), int)
    for t, p in zip(y, pred): cm[t, p] += 1
    sup = cm.sum(1); present = [k for k in range(K) if sup[k] > 0] if classes_present is None else classes_present
    per = {}
    for k in range(K):
        tp = cm[k, k]; fp = cm[:, k].sum() - tp; fn = cm[k].sum() - tp
        pr = tp / (tp + fp) if tp + fp else float("nan"); rc = tp / (tp + fn) if tp + fn else float("nan")
        f1 = 2 * pr * rc / (pr + rc) if (pr == pr and rc == rc and pr + rc > 0) else (0.0 if sup[k] > 0 else float("nan"))
        per[CLASSES[k]] = {"support": int(sup[k]), "precision": pr, "recall": rc, "f1": f1}
    macro = float(np.nanmean([per[CLASSES[k]]["f1"] for k in present])) if present else float("nan")
    eps = 1e-12
    loss = float(-np.log(np.clip(P[np.arange(n), y], eps, 1)).mean()) if n else float("nan")
    return {"n": int(n), "accuracy": float((pred == y).mean()) if n else float("nan"), "macro_f1": macro, "loss": loss, "per_class": per,
            "confusion_matrix": cm.tolist(), "classes_with_support": [CLASSES[k] for k in present]}


def confidence_report(y, P):
    """Class-wise confidence distribution (confidence = max softmax probability) by TRUE class, split by correct / wrong, plus abstention at production thresholds (reporting only)."""
    top = np.sort(P, 1)[:, ::-1]; conf = top[:, 0]; margin = top[:, 0] - top[:, 1]; pred = P.argmax(1); out = {}
    bins = np.linspace(0, 1, 11)
    for k, c in enumerate(CLASSES):
        m = y == k
        if not m.any(): continue
        ok = m & (pred == k); bad = m & (pred != k)
        q = lambda a: {"n": int(len(a)), "mean": float(a.mean()) if len(a) else None, "p10": float(np.percentile(a, 10)) if len(a) else None,
                       "median": float(np.median(a)) if len(a) else None, "p90": float(np.percentile(a, 90)) if len(a) else None}
        abst = (conf[m] < CONF_T) | (margin[m] < MARGIN_T)
        out[c] = {"confidence_when_correct": q(conf[ok]), "confidence_when_wrong": q(conf[bad]), "true_class_probability_mean": float(P[m, k].mean()),
                  "histogram_of_confidence_0.1_bins": np.histogram(conf[m], bins)[0].tolist(), "abstain_at_conf0.40_or_margin0.12": float(abst.mean()),
                  "correct_and_not_abstained": float((ok & ~((conf < CONF_T) | (margin < MARGIN_T))).sum() / m.sum())}
    return out


def bootstrap_ci(y, P, groups, reps=1000, seed=0, classes_present=None):
    """95% interval of accuracy and macro-F1, resampling leaf groups (not images)."""
    rng = np.random.default_rng(seed); ug = np.unique(groups); idx = {g: np.nonzero(groups == g)[0] for g in ug}; acc, mf = [], []
    for _ in range(reps):
        pick = np.concatenate([idx[g] for g in rng.choice(ug, len(ug))])
        m = metrics_from_probs(y[pick], P[pick], classes_present); acc.append(m["accuracy"]); mf.append(m["macro_f1"])
    return {"accuracy_95ci": [float(np.percentile(acc, 2.5)), float(np.percentile(acc, 97.5))], "macro_f1_95ci": [float(np.nanpercentile(mf, 2.5)), float(np.nanpercentile(mf, 97.5))], "reps": reps, "resampled_unit": "leaf_group"}


@torch.no_grad()
def predict(model, ids, bs=64):
    from torchvision.transforms import v2 as T
    import torchvision.transforms.functional as TF
    model.eval(); out = []
    for i in range(0, len(ids), bs):
        xs = []
        for mid in ids[i:i + bs]:
            a = load_cached(mid); h, w = a.shape[:2]; t = (h - 224) // 2; l = (w - 224) // 2
            xs.append(torch.from_numpy(a[t:t + 224, l:l + 224].copy()).permute(2, 0, 1))
        x = (torch.stack(xs).float() / 255.0 - torch.tensor(MEAN).view(1, 3, 1, 1)) / torch.tensor(STD).view(1, 3, 1, 1)
        out.append(torch.softmax(model(x), 1).numpy())
    return np.concatenate(out) if out else np.zeros((0, 5))
