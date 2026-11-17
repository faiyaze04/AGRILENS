#!/usr/bin/env python3
"""Train one run of the integrated AGRILENS multi-crop model from a YAML config.  python train_integrated.py <config.yaml>
Uses only splits/train.csv (and splits/val.csv for selection and early stopping). Test tiers are never read. The dataset is never written."""
import io, json, os, random, sys, time
import numpy as np, pandas as pd, psutil, timm, torch, torch.nn as nn, yaml
from PIL import Image
from torchvision.transforms import v2 as T
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agl_common import *


class RandomJPEG:
    def __init__(self, p, lo, hi): self.p, self.lo, self.hi = p, lo, hi
    def __call__(self, im):
        if torch.rand(1).item() > self.p: return im
        q = int(torch.randint(self.lo, self.hi + 1, (1,)).item()); b = io.BytesIO(); im.save(b, "JPEG", quality=q); b.seek(0); return Image.open(b).convert("RGB")


def make_tf(a):
    return T.Compose([T.RandomApply([T.RandomRotation(a["rotation_degrees"], fill=(124, 116, 104))], p=0.5), T.RandomResizedCrop(224, scale=tuple(a["crop_scale"]), ratio=(0.75, 4 / 3), antialias=True),
                      T.RandomHorizontalFlip(), T.RandomVerticalFlip(), T.ColorJitter(**a["colour_jitter"]), T.RandomApply([T.GaussianBlur(5, (0.1, 1.5))], p=a["blur_p"]),
                      RandomJPEG(a["jpeg_p"], *a["jpeg_quality"]), T.ToImage(), T.ToDtype(torch.float32, scale=True), T.Normalize(MEAN, STD)])


class DS(torch.utils.data.Dataset):
    def __init__(s, cache, ids, y, tf): s.cache, s.ids, s.y, s.tf = cache, ids, y, tf
    def __len__(s): return len(s.ids)
    def __getitem__(s, i): return s.tf(Image.fromarray(load_cached(s.cache, s.ids[i]))), s.y[i]


class Sampler(torch.utils.data.Sampler):
    """Each draw: class uniformly, then leaf group uniformly inside the class, then an image inside the group (no image is duplicated on disk)."""
    def __init__(s, df, seed, n):
        s.n, s.seed, s.epoch = n, seed, 1; s.by = {k: [g.index.to_numpy() for _, g in x.groupby("leaf_group_id")] for k, x in df.groupby("model_index")}; s.cls = sorted(s.by)
    def set_epoch(s, e): s.epoch = e
    def __iter__(s):
        rng = np.random.default_rng(s.seed * 100003 + s.epoch); out = []
        for _ in range(s.n): c = s.cls[rng.integers(len(s.cls))]; g = s.by[c][rng.integers(len(s.by[c]))]; out.append(int(g[rng.integers(len(g))]))
        return iter(out)
    def __len__(s): return s.n


def wi(_): torch.set_num_threads(1)


def main(cfgp):
    cfg = yaml.safe_load(open(cfgp)); run, mode, seed = cfg["run_id"], cfg["recipe"], cfg["seed"]; root, cache, outroot = cfg["dataset"]["root"], cfg["cache"], cfg["output_dir"]
    out = os.path.join(outroot, run); os.makedirs(out, exist_ok=True); random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.set_num_threads(cfg["compute"]["torch_threads"])
    frozen = verify_dataset(root); tax = taxonomy(root); K = len(tax)
    tr = pd.read_csv(os.path.join(root, "splits", "train.csv")); va = pd.read_csv(os.path.join(root, "splits", "val.csv"))
    for t in ("test_known_device", "test_heldout_device"): assert not (set(tr.image_id) & set(pd.read_csv(os.path.join(root, "splits", f"{t}.csv")).image_id))
    tr = tr.reset_index(drop=True); ds = DS(cache, tr.image_id.tolist(), tr.model_index.astype(int).tolist(), make_tf(cfg["augmentation"]))
    model = timm.create_model(MODEL_NAME, pretrained=True, num_classes=K); nf = FROZEN_UNTIL[mode]; un = UNFREEZE[mode]
    nn.init.zeros_(model.classifier.weight); nn.init.zeros_(model.classifier.bias)
    x0 = torch.randn(2, 3, 224, 224); model.eval()
    with torch.no_grad(): assert torch.allclose(model(x0), trainable_forward(model, prefix_forward(model, x0, nf), nf), atol=1e-5)
    for p in model.parameters(): p.requires_grad = False
    for n, p in model.named_parameters():
        if any(n == u or n.startswith(u + ".") for u in un): p.requires_grad = True
    head = [p for n, p in model.named_parameters() if p.requires_grad and n.startswith("classifier")]; body = [p for n, p in model.named_parameters() if p.requires_grad and not n.startswith("classifier")]
    o = cfg["optim"]; opt = torch.optim.AdamW([{"params": head, "lr": o["lr_head"]}, {"params": body, "lr": o["lr_backbone"]}], weight_decay=o["weight_decay"]); base = [g["lr"] for g in opt.param_groups]
    crit = nn.CrossEntropyLoss(label_smoothing=o["label_smoothing"]); E = o["epochs_max"]; spe = cfg["sampling"]["samples_per_epoch"]; bs = o["batch_size"]; steps = spe // bs; total = E * steps
    sampler = Sampler(tr, seed, spe); dl = torch.utils.data.DataLoader(ds, batch_size=bs, sampler=sampler, num_workers=cfg["compute"]["workers"], drop_last=True, prefetch_factor=4, persistent_workers=True, worker_init_fn=wi, generator=torch.Generator().manual_seed(seed * 1000))
    proc = psutil.Process(os.getpid()); best = {"f1": -1, "loss": 9e9, "epoch": 0}; log = []; t0 = time.time(); step = 0; bad = 0
    ntrain = sum(p.numel() for p in model.parameters() if p.requires_grad)
    json.dump({"config": cfg, "frozen_dataset_files_sha256": frozen, "classes": tax.model_label.tolist(), "torch": torch.__version__, "timm": timm.__version__, "trainable_params": ntrain, "host_cpus": os.cpu_count()}, open(os.path.join(out, "run_info.json"), "w"), indent=1)
    yva = va.model_index.astype(int).to_numpy()
    for ep in range(1, E + 1):
        sampler.set_epoch(ep); model.eval()
        for n, m in model.named_modules():
            if any(n == u or n.startswith(u + ".") for u in un) and len(list(m.children())) == 0: m.train()
        te = time.time(); c0 = proc.cpu_times(); tl = tc = tn = 0; psutil.cpu_percent(None)
        for xb, yb in dl:
            f = min(1.0, (step + 1) / steps) * 0.5 * (1 + np.cos(np.pi * step / total))
            for g, b in zip(opt.param_groups, base): g["lr"] = b * f
            with torch.no_grad(): feat = prefix_forward(model, xb, nf)
            lg = trainable_forward(model, feat, nf); loss = crit(lg, yb); opt.zero_grad(); loss.backward(); opt.step(); step += 1
            tl += loss.item() * len(yb); tc += (lg.argmax(1) == yb).sum().item(); tn += len(yb)
        wall = time.time() - te; c1 = proc.cpu_times(); P = predict_single_view(model, cache, va.image_id.tolist()); m = metrics(yva, P, K)
        row = {"epoch": ep, "train_loss": tl / tn, "train_acc_augmented": tc / tn, "val_loss": m["loss"], "val_acc": m["accuracy"], "val_macro_f1": m["macro_f1"], "epoch_seconds": wall,
               "process_cpu_cores": ((c1.user - c0.user) + (c1.system - c0.system)) / wall, "system_cpu_percent": psutil.cpu_percent(None), "rss_gb": proc.memory_info().rss / 2**30}
        if m["macro_f1"] > best["f1"] + 1e-4 or (abs(m["macro_f1"] - best["f1"]) <= 1e-4 and m["loss"] < best["loss"]):
            best = {"f1": m["macro_f1"], "loss": m["loss"], "epoch": ep}; bad = 0; torch.save({"state_dict": model.state_dict(), "classes": tax.model_label.tolist(), "epoch": ep, "run_id": run, "config": cfg}, os.path.join(out, "best.pt"))
        else: bad += 1
        log.append(row); pd.DataFrame(log).to_csv(os.path.join(out, "epochs.csv"), index=False); print(json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in row.items()}), flush=True)
        if bad >= o["patience"]: print("early stop", ep, flush=True); break
    ck = torch.load(os.path.join(out, "best.pt"), weights_only=False); model.load_state_dict(ck["state_dict"]); P = predict_single_view(model, cache, va.image_id.tolist()); m = metrics(yva, P, K)
    m["by_crop"] = {c: metrics(yva[(va.crop == c).to_numpy()], P[(va.crop == c).to_numpy()], K)["accuracy"] for c in sorted(va.crop.unique())}
    json.dump(m, open(os.path.join(out, "val_metrics.json"), "w"), indent=1)
    pd.concat([va[["image_id", "crop", "class_id", "model_index", "source_id", "capture_device"]].reset_index(drop=True), pd.DataFrame(P, columns=[f"p{i}" for i in range(K)])], axis=1).to_csv(os.path.join(out, "val_predictions.csv"), index=False)
    s = {"run_id": run, "recipe": mode, "seed": seed, "epochs_run": ep, "best_epoch": best["epoch"], "val_macro_f1": m["macro_f1"], "val_accuracy": m["accuracy"], "val_loss": m["loss"], "train_minutes": (time.time() - t0) / 60,
         "mean_epoch_seconds": float(np.mean([r["epoch_seconds"] for r in log])), "mean_process_cpu_cores": float(np.mean([r["process_cpu_cores"] for r in log])), "peak_rss_gb": float(max(r["rss_gb"] for r in log)), "trainable_params": ntrain, "hardware": "CPU only"}
    json.dump(s, open(os.path.join(out, "summary.json"), "w"), indent=1); print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
