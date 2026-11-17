#!/usr/bin/env python3
"""
AGRILENS 5.0.0 exhibition checks that can run on a desktop PC (Windows or Linux). DESKTOP ONLY: nothing here is a Raspberry Pi,
C270 or touchscreen result. Read-only with respect to the package: the GUI tests run a temporary copy with a temporary home folder.

  python exhibition_desktop_check.py --package AGRILENS_RaspberryPi --out <dir> [--gui-seconds 90] [--soak-runs 1200] [--camera]

Checks
  1. content   every class has English and Hindi crop/condition names and its own recommendation (EN and HI)
  2. samples   the 24 sample images through the app's own six-view predict and result-screen code, release gates, EN and HI
  3. unsupported  synthetic non-leaf inputs must give UNKNOWN or LOW CONFIDENCE (cautionary screen), never a diagnosis
  4. soak      repeated predictions: latency and process memory over time
  5. gui       the real Tk application, offline (proxy to a closed port): starts and keeps running; after a forced kill it
               starts again; with a truncated (corrupt) user config it still starts. Console and errors are kept.
  6. camera    (optional) detect / read / close / re-detect with whatever webcam this PC has (not the C270)
"""
import argparse, ctypes, json, os, platform, random, shutil, subprocess, sys, tempfile, time
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app_harness as H  # noqa: E402


def rss_mb():
    try:
        if platform.system() == "Windows":
            class PMC(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong), ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            c = PMC(); c.cb = ctypes.sizeof(PMC)
            k32 = ctypes.windll.kernel32
            k32.GetCurrentProcess.restype = ctypes.c_void_p
            k32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), ctypes.c_ulong]
            if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return None, None
            return c.WorkingSetSize / 2**20, c.PeakWorkingSetSize / 2**20
        for ln in open("/proc/self/status"):
            if ln.startswith("VmRSS"): cur = int(ln.split()[1]) / 1024
            if ln.startswith("VmHWM"): peak = int(ln.split()[1]) / 1024
        return cur, peak
    except Exception:
        return None, None


def render(app, labels, probs, raw, th, lang, selected_plant=None):
    parsed = [app.parse_label(lbl) for lbl in labels]
    rows = [(MagicMock(), MagicMock(), MagicMock()) for _ in range(6)]
    fake = SimpleNamespace(lang=lang, classifier=SimpleNamespace(labels=list(labels)), selected_plant=selected_plant, crops=[p[0] for p in parsed], parsed=parsed,
                           threshold=th["confidence_threshold"], ood_margin=th["ood_margin"], ood_logit=th["ood_logit"],
                           banner_frame=MagicMock(), banner=MagicMock(), plant_lbl=MagicMock(), disease_lbl=MagicMock(), cam_border=MagicMock(), diagnose_btn=MagicMock(),
                           bar=MagicMock(), step_rows=rows, BAR_W=300, BAR_H=20, px=lambda n: n, _draw_bar=MagicMock())
    app.AgriLensApp._render_diagnosis(fake, list(probs), raw)
    t = lambda m: (m.config.call_args.kwargs.get("text", "") if m.config.call_args else "")
    steps = []
    for r in rows:
        for m in r:
            if m.config.call_args and len(t(m)) > 12: steps.append(t(m))
    return {"button": t(fake.diagnose_btn), "banner": t(fake.banner), "plant": t(fake.plant_lbl), "disease": t(fake.disease_lbl), "steps": steps}


VERDICT = {"UNKNOWN LEAF": "UNKNOWN", "LOW CONFIDENCE": "LOW_CONFIDENCE", "HEALTHY CROP": "HEALTHY", "DISEASE FOUND": "DISEASE"}
has_devanagari = lambda s: any("\u0900" <= ch <= "\u097f" for ch in s)


def check_content(app, labels):
    out, ok = [], True
    for lbl in labels:
        crop, cond, healthy = app.parse_label(lbl)
        hi_crop, hi_cond = app.translate_crop_hi(crop), app.translate_cond_hi(cond)
        en_steps, hi_steps = app.get_recommendation(crop, cond, "EN"), app.get_recommendation(crop, cond, "HI")
        r = {"label": lbl, "crop": crop, "condition": cond, "hi_crop": hi_crop, "hi_condition": hi_cond,
             "hi_crop_translated": has_devanagari(hi_crop), "hi_condition_translated": has_devanagari(hi_cond),
             "recommendation_specific_en": en_steps is not app.DEFAULT_STEPS, "recommendation_specific_hi": hi_steps is not app.DEFAULT_STEPS_HI,
             "steps_en": len(en_steps), "steps_hi": len(hi_steps)}
        r["ok"] = r["hi_crop_translated"] and r["hi_condition_translated"] and r["steps_en"] >= 3 and r["steps_hi"] >= 3 and r["steps_en"] == r["steps_hi"]
        ok &= r["ok"]; out.append(r)
    return {"ok": ok, "classes": out}


def check_samples(app, clf, th):
    from PIL import Image
    res, ok = [], True
    for label, path in H.sample_images(os.path.join(os.path.dirname(app.__file__), "diagnosis_samples")):
        img = Image.open(path).convert("RGB"); probs, ms, raw = clf.predict(img)
        top = clf.labels[max(range(len(probs)), key=lambda i: probs[i])]
        en, hi = render(app, clf.labels, probs, raw, th, "EN"), render(app, clf.labels, probs, raw, th, "HI")
        crop = label.split("_")[0]; en_locked = render(app, clf.labels, probs, raw, th, "EN", selected_plant=crop)
        r = {"sample": os.path.basename(path), "expected": label, "top1": top, "top1_correct": top == label, "confidence": round(max(probs), 3), "max_logit": round(float(max(raw)), 2),
             "screen_en": VERDICT.get(en["button"], en["button"]), "banner_en": en["banner"], "disease_en": en["disease"], "screen_hi_button": hi["button"], "banner_hi": hi["banner"],
             "hi_text_present": has_devanagari(hi["banner"] + hi["disease"] + hi["plant"]), "screen_en_crop_locked": VERDICT.get(en_locked["button"], en_locked["button"]), "ms": round(ms, 1)}
        r["ok"] = r["top1_correct"] and r["screen_en"] in ("HEALTHY", "DISEASE") and r["hi_text_present"]
        ok &= r["ok"]; res.append(r)
    return {"ok": ok, "thresholds": th, "samples": res}


def synthetic_images(app_dir):
    from PIL import Image, ImageDraw
    random.seed(0); W, Hh = 640, 480; imgs = {}
    for name, col in (("black", (0, 0, 0)), ("white", (255, 255, 255)), ("grey", (128, 128, 128)), ("table_brown", (120, 90, 60)), ("sky_blue", (120, 170, 230))):
        imgs[name] = Image.new("RGB", (W, Hh), col)
    imgs["noise"] = Image.frombytes("RGB", (W, Hh), bytes(random.getrandbits(8) for _ in range(W * Hh * 3)))
    g = Image.new("RGB", (W, Hh)); d = ImageDraw.Draw(g)
    for x in range(W): d.line([(x, 0), (x, Hh)], fill=(x * 255 // W, 80, 255 - x * 255 // W))
    imgs["gradient"] = g
    t = Image.new("RGB", (W, Hh), (240, 240, 240)); d = ImageDraw.Draw(t)
    for i in range(0, Hh, 40): d.text((20, i), "AGRILENS EXPISCOR 2026 exhibition text card", fill=(20, 20, 20))
    imgs["text_card"] = t
    for f in ("agrilens_logo.jpg", "gundecha_logo.png"):
        p = os.path.join(app_dir, "logos", f)
        if os.path.exists(p): imgs["logo_" + f.split(".")[0]] = Image.open(p).convert("RGB")
    return imgs


def check_unsupported(app, clf, th):
    res, ok = [], True
    for name, img in synthetic_images(os.path.dirname(app.__file__)).items():
        probs, _, raw = clf.predict(img)
        en, hi = render(app, clf.labels, probs, raw, th, "EN"), render(app, clf.labels, probs, raw, th, "HI")
        v = VERDICT.get(en["button"], en["button"])
        r = {"input": name, "screen": v, "banner_en": en["banner"], "banner_hi": hi["banner"], "confidence": round(max(probs), 3), "max_logit": round(float(max(raw)), 2),
             "cautionary": v in ("UNKNOWN", "LOW_CONFIDENCE")}
        ok &= r["cautionary"]; res.append(r)
    return {"ok": ok, "inputs": res}


def check_soak(clf, runs):
    from PIL import Image
    imgs = [Image.open(p).convert("RGB") for _, p in H.sample_images(os.path.join(os.path.dirname(H.load_app().__file__), "diagnosis_samples"))]
    lat, mem = [], []; t0 = time.time()
    for i in range(runs):
        _, ms, _ = clf.predict(imgs[i % len(imgs)]); lat.append(ms)
        if i % max(1, runs // 12) == 0: mem.append((i, *rss_mb()))
    mem.append((runs, *rss_mb())); lat_s = sorted(lat)
    q = lambda p: lat_s[min(len(lat_s) - 1, int(round(p / 100 * len(lat_s) + 0.5)) - 1)]
    first, last = mem[1][1], mem[-1][1]
    return {"runs": runs, "seconds": round(time.time() - t0, 1), "latency_ms": {"mean": round(sum(lat) / len(lat), 1), "median": round(q(50), 1), "p95": round(q(95), 1), "max": round(max(lat), 1)},
            "memory_mb_samples": [{"after_runs": i, "rss": round(c, 1) if c else None, "peak": round(p, 1) if p else None} for i, c, p in mem],
            "rss_growth_mb_after_warmup": round(last - first, 1) if first and last else None, "ok": (last - first) < 50 if first and last else True}


def run_gui(pkg, seconds, home, label, extra_env=None):
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), PYTHONUNBUFFERED="1", PYTHONDONTWRITEBYTECODE="1",
               HTTPS_PROXY="http://127.0.0.1:9", HTTP_PROXY="http://127.0.0.1:9", https_proxy="http://127.0.0.1:9", http_proxy="http://127.0.0.1:9", NO_PROXY="", no_proxy="")
    env.update(extra_env or {})
    log = os.path.join(str(home), f"gui_{label}.log")
    with open(log, "w", encoding="utf-8", errors="replace") as f:
        p = subprocess.Popen([sys.executable, "-u", os.path.join(pkg, "main.py")], cwd=pkg, env=env, stdout=f, stderr=subprocess.STDOUT)
        t0 = time.time(); alive = True
        while time.time() - t0 < seconds:
            if p.poll() is not None: alive = False; break
            time.sleep(1)
        code = p.poll()
        if code is None: p.kill(); p.wait(10)    # forced stop = simulated unexpected shutdown
    text = open(log, encoding="utf-8", errors="replace").read()
    return {"run": label, "seconds_requested": seconds, "seconds_alive": round(time.time() - t0, 1), "alive_whole_time": alive, "exit_code_if_exited": code, "forced_kill_at_end": code is None,
            "traceback_in_output": "Traceback" in text, "startup_line": next((ln for ln in text.splitlines() if ln.startswith("AGRILENS 5.")), ""),
            "output_tail": text.splitlines()[-12:], "log": log}


def check_gui(pkg_src, seconds):
    tmp = tempfile.mkdtemp(prefix="agl_exh_"); pkg = os.path.join(tmp, "AGRILENS_5.0.0"); shutil.copytree(pkg_src, pkg); home = os.path.join(tmp, "home"); os.makedirs(home)
    r = [run_gui(pkg, seconds, home, "1_first_start_offline")]
    ucfg = os.path.join(home, ".agrilens_kiosk_config.json")
    r.append(run_gui(pkg, max(30, seconds // 2), home, "2_restart_after_forced_kill"))
    with open(ucfg, "w", encoding="utf-8") as f: f.write('{"confidence_threshold": 0.4, "language": "HI", "ood_lo')   # power cut during a config write
    r.append(run_gui(pkg, max(30, seconds // 2), home, "3_start_with_truncated_user_config"))
    ok = all(x["alive_whole_time"] and not x["traceback_in_output"] and "rejection gates from calibration of AGRILENS-MULTICROP 1.0.0" in x["startup_line"] for x in r)
    return {"ok": ok, "temp_dir": tmp, "network": "blocked for the app (HTTP(S) proxy set to a closed local port)", "runs": r}


def check_camera(app):
    cam = app.Camera(auto_detect=False); out = {}
    t0 = time.time(); ok, msg = cam.detect_webcam(); out["detect"] = {"ok": ok, "message": msg, "seconds": round(time.time() - t0, 2)}
    if ok:
        n = good = 0; t0 = time.time()
        while time.time() - t0 < 5: n += 1; good += cam.read() is not None
        out["reads_5s"] = {"reads": n, "frames": good}
        cam.close(); out["after_close_has_camera"] = bool(getattr(cam, "cap", None))
        t0 = time.time(); ok2, msg2 = cam.detect_webcam(); out["re_detect"] = {"ok": ok2, "message": msg2, "seconds": round(time.time() - t0, 2)}
        f2 = sum(cam.read() is not None for _ in range(30)); out["frames_after_re_detect"] = f2; cam.close()
        out["ok"] = good > 0 and ok2 and f2 > 0
    else:
        out["ok"] = None
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--package", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--gui-seconds", type=int, default=90); ap.add_argument("--soak-runs", type=int, default=1200); ap.add_argument("--camera", action="store_true"); ap.add_argument("--skip-gui", action="store_true"); ap.add_argument("--gui-only", action="store_true")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); pkg = os.path.abspath(a.package)
    os.environ["AGRILENS_APP_PATH"] = os.path.join(pkg, "main.py")
    app = H.load_app(os.path.join(pkg, "main.py")); clf = app.Classifier(os.path.join(pkg, "agrilens.onnx"), os.path.join(pkg, "labels.txt"))
    th, src = app.resolve_gate_thresholds({}, clf.model_sha256)
    R = {"NOTE": "Desktop PC checks only. Not Raspberry Pi 5, not the C270, not the touchscreen.", "host": {"platform": platform.platform(), "python": platform.python_version(), "cpu": platform.processor()},
         "app_version": app.APP_VERSION, "model": f"{app.MODEL_ID} {app.MODEL_VERSION}", "model_sha256": clf.model_sha256, "mode": clf.mode, "gates": th, "gate_source": src}
    if not a.gui_only:
        R["content"] = check_content(app, clf.labels); R["samples"] = check_samples(app, clf, th); R["unsupported"] = check_unsupported(app, clf, th); R["soak"] = check_soak(clf, a.soak_runs)
    if a.camera: R["camera_this_pc"] = check_camera(app)
    if not a.skip_gui: R["gui"] = check_gui(pkg, a.gui_seconds)
    R["summary"] = {k: R[k]["ok"] for k in ("content", "samples", "unsupported", "soak", "gui", "camera_this_pc") if k in R}
    json.dump(R, open(os.path.join(a.out, "gui_check_results.json" if a.gui_only else "desktop_check_results.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(R["summary"]))


if __name__ == "__main__":
    main()
