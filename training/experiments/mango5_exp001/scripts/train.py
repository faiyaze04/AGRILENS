#!/usr/bin/env python3
"""Train one run of the AGL-MANGO five-class experiment from a YAML config.
  python train.py configs\\<run>.yaml
Uses only the frozen training manifest (and the frozen validation manifest for model selection / early stopping).
Test tiers are never read here. Production files are never touched."""
import csv, json, os, random, sys, time
import numpy as np, pandas as pd, torch, torch.nn as nn, yaml, psutil, timm
from PIL import Image
from torchvision.transforms import v2 as T
sys.path.insert(0, os.path.dirname(__file__))
from common import *


class RandomJPEG:
    def __init__(self, p, lo, hi): self.p, self.lo, self.hi = p, lo, hi
    def __call__(self, im):
        if torch.rand(1).item() > self.p: return im
        import io; q = int(torch.randint(self.lo, self.hi + 1, (1,)).item()); b = io.BytesIO(); im.save(b, "JPEG", quality=q); b.seek(0); return Image.open(b).convert("RGB")


def make_train_tf(c):
    a = c["augmentation"]
    return T.Compose([T.RandomApply([T.RandomRotation(a["rotation_degrees"], fill=(124, 116, 104))], p=0.5),
                      T.RandomResizedCrop(224, scale=tuple(a["crop_scale"]), ratio=(0.75, 4 / 3), antialias=True),
                      T.RandomHorizontalFlip(), T.RandomVerticalFlip(), T.ColorJitter(**a["colour_jitter"]),
                      T.RandomApply([T.GaussianBlur(5, (0.1, 1.5))], p=a["blur_p"]), RandomJPEG(a["jpeg_p"], *a["jpeg_quality"]),
                      T.ToImage(), T.ToDtype(torch.float32, scale=True), T.Normalize(MEAN, STD)])


class TrainSet(torch.utils.data.Dataset):
    def __init__(self, ids, labels, tf): self.ids, self.labels, self.tf = ids, labels, tf
    def __len__(self): return len(self.ids)
    def __getitem__(self, i): return self.tf(Image.fromarray(load_cached(self.ids[i]))), self.labels[i]


def epoch_indices(df, seed, epoch, n):
    """Class-balanced, leaf-group-balanced draw: class uniformly, then leaf group uniformly inside the class, then an image inside the group."""
    rng = np.random.default_rng(seed * 100003 + epoch); by = {}
    for k, g in df.groupby("class_id"): by[k] = [v.index.to_numpy() for _, v in g.groupby("leaf_group_id")]
    cls = list(by); out = []
    for _ in range(n):
        c = cls[rng.integers(len(cls))]; grp = by[c][rng.integers(len(by[c]))]; out.append(int(grp[rng.integers(len(grp))]))
    return out


class EpochSampler(torch.utils.data.Sampler):
    """Draws the class- and leaf-group-balanced indices of the current epoch (set_epoch before iterating)."""
    def __init__(self, df, seed, n): self.df, self.seed, self.n, self.epoch = df, seed, n, 1
    def set_epoch(self, e): self.epoch = e
    def __iter__(self): return iter(epoch_indices(self.df, self.seed, self.epoch, self.n))
    def __len__(self): return self.n


def worker_init(_):
    torch.set_num_threads(1)


def evaluate(model, df):
    ids = df.master_image_id.tolist(); y = df.class_id.map(CIDX).to_numpy(); P = predict(model, ids)
    return y, P


def main(cfg_path):
    cfg = yaml.safe_load(open(cfg_path)); run = cfg["run_id"]; mode = cfg["mode"]; seed = cfg["seed"]
    assert cfg["authorisation"]["training_authorised"] is True
    out = os.path.join(EXP, "runs", run); os.makedirs(out, exist_ok=True)
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.set_num_threads(cfg["compute"]["torch_threads"])
    frozen = verify_frozen_files()
    tr = pd.read_csv(os.path.join(RC, cfg["data"]["train_manifest"].replace("/", os.sep)))
    if cfg["data"].get("train_role"): tr = tr[tr.role == cfg["data"]["train_role"]].reset_index(drop=True)
    assert set(tr.class_id) <= set(CLASSES)
    va = pd.read_csv(os.path.join(RC, cfg["data"]["val_manifest"].replace("/", os.sep))) if cfg["data"].get("val_manifest") else None
    # safeguard: training manifest must not contain any test-tier image
    for t in ("test_known_device", "test_heldout_device"):
        ids_t = set(pd.read_csv(os.path.join(RC, "splits", t + ".csv")).master_image_id)
        if cfg["data"].get("allow_test_overlap") is not True: assert not (set(tr.master_image_id) & ids_t), f"training data overlaps {t}"
    labels = tr.class_id.map(CIDX).tolist(); ids = tr.master_image_id.tolist()
    ds = TrainSet(ids, labels, make_train_tf(cfg)); print(run, "train images", len(tr), "val", None if va is None else len(va), flush=True)
    model = timm.create_model(MODEL_NAME, pretrained=True, num_classes=len(CLASSES))
    x0 = torch.randn(2, 3, 224, 224); model.eval()
    with torch.no_grad(): assert torch.allclose(model(x0), trainable_forward(model, prefix_forward(model, x0, mode), mode), atol=1e-5)
    nn.init.zeros_(model.classifier.weight); nn.init.zeros_(model.classifier.bias)   # new head starts at uniform predictions (loss ln 5)
    for p in model.parameters(): p.requires_grad = False
    un = UNFREEZE[mode]
    for n, p in model.named_parameters():
        if any(n == u or n.startswith(u + ".") for u in un): p.requires_grad = True
    ntrain = sum(p.numel() for p in model.parameters() if p.requires_grad); print("trainable params", ntrain, "of", sum(p.numel() for p in model.parameters()), flush=True)
    head = [p for n, p in model.named_parameters() if p.requires_grad and n.startswith("classifier")]
    body = [p for n, p in model.named_parameters() if p.requires_grad and not n.startswith("classifier")]
    groups = [{"params": head, "lr": cfg["optim"]["lr_head"]}] + ([{"params": body, "lr": cfg["optim"]["lr_backbone"]}] if body else [])
    opt = torch.optim.AdamW(groups, weight_decay=cfg["optim"]["weight_decay"]); base = [g["lr"] for g in opt.param_groups]
    crit = nn.CrossEntropyLoss(label_smoothing=cfg["optim"]["label_smoothing"])
    E = cfg["optim"]["epochs_max"]; spe = cfg["sampling"]["samples_per_epoch"]; bs = cfg["optim"]["batch_size"]; steps_per = spe // bs; total = E * steps_per
    fixed = cfg["optim"].get("fixed_epochs"); patience = cfg["optim"].get("patience", 3)
    nw = cfg["compute"]["workers"]; proc = psutil.Process(os.getpid()); psutil.cpu_percent(None)
    sampler = EpochSampler(tr, seed, spe); gen = torch.Generator().manual_seed(seed * 1000)
    dl = torch.utils.data.DataLoader(ds, batch_size=bs, sampler=sampler, num_workers=nw, drop_last=True, generator=gen, prefetch_factor=4, persistent_workers=True, worker_init_fn=worker_init)
    best = {"f1": -1, "loss": 9e9, "epoch": 0}; log = []; t_start = time.time(); step = 0; bad = 0
    json.dump({"config": cfg, "frozen_manifest_sha256": frozen, "torch": torch.__version__, "timm": timm.__version__, "trainable_params": ntrain, "pretrained": MODEL_NAME,
               "host": {"cpus": os.cpu_count(), "ram_gb": round(psutil.virtual_memory().total / 2**30, 1)}}, open(os.path.join(out, "run_info.json"), "w"), indent=1)
    for ep in range(1, E + 1):
        sampler.set_epoch(ep)
        model.eval()
        for n, m in model.named_modules():            # frozen parts stay in eval mode; trainable parts train
            if any(n == u or n.startswith(u + ".") for u in un) and len(list(m.children())) == 0: m.train()
        t0 = time.time(); c0 = proc.cpu_times(); tl = tc = tn = 0; psutil.cpu_percent(None)
        for xb, yb in dl:
            f = min(1.0, (step + 1) / steps_per) * 0.5 * (1 + np.cos(np.pi * step / total))     # 1-epoch warm-up then cosine
            for g, b in zip(opt.param_groups, base): g["lr"] = b * f
            with torch.no_grad(): feat = prefix_forward(model, xb, mode)
            logits = trainable_forward(model, feat, mode); loss = crit(logits, yb)
            opt.zero_grad(); loss.backward(); opt.step(); step += 1
            tl += loss.item() * len(yb); tc += (logits.argmax(1) == yb).sum().item(); tn += len(yb)
        wall = time.time() - t0; c1 = proc.cpu_times(); sysu = psutil.cpu_percent(None)
        row = {"epoch": ep, "train_loss": tl / tn, "train_acc_augmented": tc / tn, "epoch_seconds": wall, "process_cpu_seconds": (c1.user - c0.user) + (c1.system - c0.system),
               "system_cpu_percent": sysu, "rss_gb": proc.memory_info().rss / 2**30, "lr_head": opt.param_groups[0]["lr"]}
        if va is not None:
            y, P = evaluate(model, va); m = metrics_from_probs(y, P); row.update(val_loss=m["loss"], val_acc=m["accuracy"], val_macro_f1=m["macro_f1"])
            better = (m["macro_f1"] > best["f1"] + 1e-4) or (abs(m["macro_f1"] - best["f1"]) <= 1e-4 and m["loss"] < best["loss"])
            if better:
                best = {"f1": m["macro_f1"], "loss": m["loss"], "epoch": ep}; bad = 0
                torch.save({"state_dict": model.state_dict(), "classes": CLASSES, "epoch": ep, "run_id": run, "val_macro_f1": m["macro_f1"], "config": cfg}, os.path.join(out, "best.pt"))
            else: bad += 1
        log.append(row); pd.DataFrame(log).to_csv(os.path.join(out, "epochs.csv"), index=False)
        print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
        if fixed and ep >= fixed: break
        if va is not None and bad >= patience: print("early stop at epoch", ep, flush=True); break
    train_seconds = time.time() - t_start
    torch.save({"state_dict": model.state_dict(), "classes": CLASSES, "epoch": ep, "run_id": run, "config": cfg}, os.path.join(out, "last.pt"))
    summ = {"run_id": run, "mode": mode, "seed": seed, "epochs_run": ep, "best_epoch": best["epoch"], "best_val_macro_f1": best["f1"], "train_seconds": train_seconds,
            "mean_epoch_seconds": float(np.mean([r["epoch_seconds"] for r in log])), "mean_system_cpu_percent": float(np.mean([r["system_cpu_percent"] for r in log])),
            "mean_process_cpu_cores_used": float(np.sum([r["process_cpu_seconds"] for r in log]) / np.sum([r["epoch_seconds"] for r in log])), "peak_rss_gb": float(max(r["rss_gb"] for r in log)),
            "hardware": "CPU only, torch threads %d, dataloader workers %d" % (cfg["compute"]["torch_threads"], nw), "gpu": "none"}
    if va is not None:     # validation report of the BEST checkpoint
        ck = torch.load(os.path.join(out, "best.pt"), weights_only=False); model.load_state_dict(ck["state_dict"])
        y, P = evaluate(model, va); m = metrics_from_probs(y, P); m["confidence"] = confidence_report(y, P); m["bootstrap"] = bootstrap_ci(y, P, va.leaf_group_id.to_numpy(), 500, seed)
        m["by_source"] = {s: metrics_from_probs(y[(va.source_id == s).to_numpy()], P[(va.source_id == s).to_numpy()])["accuracy"] for s in va.source_id.unique()}
        json.dump(m, open(os.path.join(out, "val_metrics.json"), "w"), indent=1)
        pd.DataFrame(m["confusion_matrix"], index=CLASSES, columns=CLASSES).to_csv(os.path.join(out, "val_confusion_matrix.csv"))
        pd.concat([va[["master_image_id", "class_id", "source_id", "capture_device", "leaf_group_id"]].reset_index(drop=True), pd.DataFrame(P, columns=[f"p_{c}" for c in CLASSES])], axis=1).to_csv(os.path.join(out, "val_predictions.csv"), index=False)
        summ.update(val_accuracy=m["accuracy"], val_loss=m["loss"], val_macro_f1=m["macro_f1"])
    json.dump(summ, open(os.path.join(out, "summary.json"), "w"), indent=1); print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
