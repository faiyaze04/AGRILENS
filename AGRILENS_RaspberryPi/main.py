#!python3.13
"""
AGRILENS - AI Plant Health & Disease Diagnosis Kiosk
Target Runtime: Python 3.13+
Hardware: Raspberry Pi 5 (8GB) + 7" Capacitive Touch Display + USB Webcam
Model: MobileNetV4 (ONNX) - 98.31% Accuracy
Features:
- Separate [CAPTURE] / [RETAKE] and [DIAGNOSE] buttons
- Integrated Leaf Image Quality AI (Sharpness, Lighting & Foliage Presence check)
- 30% Confidence Threshold with Auto (Beta Production) mode
- Blue [ADMIN] Button with Webcam Detection and Close Application
"""

import io
import os
import sys
import json
import glob
import subprocess
import platform
import queue
import random
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import filedialog
import tkinter.font as tkFont
from collections import deque

# Automatically include Raspberry Pi OS system package paths in sys.path
for _p in [
    "/usr/lib/python3/dist-packages",
    "/usr/local/lib/python3/dist-packages",
    "/usr/lib/python3.13/dist-packages",
    "/usr/lib/python3.11/dist-packages",
]:
    if os.path.exists(_p) and _p not in sys.path:
        sys.path.append(_p)

def _auto_install_package(import_name, pip_name=None):
    if pip_name is None:
        pip_name = import_name
    try:
        return __import__(import_name)
    except ImportError:
        print(f"[AGRILENS] Missing '{pip_name}'. Auto-installing for {sys.executable}...")
        for cmd in [
            [sys.executable, "-m", "pip", "install", pip_name, "--break-system-packages"],
            [sys.executable, "-m", "pip", "install", pip_name],
        ]:
            try:
                subprocess.check_call(cmd)
                print(f"[AGRILENS] Successfully installed '{pip_name}'.")
                return __import__(import_name)
            except Exception:
                pass
        return None

# Resilient Pillow & ImageTk import (supports Pillow 7.x through 13.x+, Windows & Raspberry Pi OS)
try:
    from PIL import Image, ImageOps, ImageDraw, ImageEnhance
except ImportError:
    _auto_install_package("PIL", "pillow")
    try:
        from PIL import Image, ImageOps, ImageDraw, ImageEnhance
    except ImportError:
        raise SystemExit(
            "Pillow is missing!\n"
            "PC / Windows: Tools -> Manage packages... -> install 'pillow' (or pip install pillow)\n"
            "Raspberry Pi: sudo apt install -y python3-pil python3-pil.imagetk"
        )

# Resampling compatibility across all Pillow versions (<9.1, 9.x, 10+, 13+)
_RESAMPLE_ENUM = getattr(Image, "Resampling", Image)
RESAMPLE_BILINEAR = getattr(_RESAMPLE_ENUM, "BILINEAR", getattr(Image, "BILINEAR", 2))
RESAMPLE_LANCZOS = getattr(_RESAMPLE_ENUM, "LANCZOS", getattr(Image, "ANTIALIAS", 1))
RESAMPLE = RESAMPLE_BILINEAR

# Resilient ImageTk wrapper with native Tkinter fallback (fixes missing _imagingtk C module on Linux)
try:
    from PIL import ImageTk as _PIL_ImageTk
    from PIL import _imagingtk  # noqa: F401
    _HAS_IMAGINGTK = True
except Exception:
    _PIL_ImageTk = None
    _HAS_IMAGINGTK = False


class ImageTk:
    """Drop-in replacement for PIL.ImageTk that works with or without the _imagingtk C module."""
    @staticmethod
    def PhotoImage(image=None, **kwargs):
        if _HAS_IMAGINGTK and _PIL_ImageTk is not None:
            try:
                return _PIL_ImageTk.PhotoImage(image, **kwargs)
            except Exception:
                pass
        if image is not None:
            bio = io.BytesIO()
            image.save(bio, format="PNG", compress_level=1)
            return tk.PhotoImage(data=bio.getvalue(), **kwargs)
        return tk.PhotoImage(**kwargs)

try:
    import numpy as np
except ImportError:
    _auto_install_package("numpy", "numpy")
    try:
        import numpy as np
    except ImportError:
        np = None

try:
    import cv2
except ImportError:
    _auto_install_package("cv2", "opencv-python")
    try:
        import cv2
    except ImportError:
        cv2 = None

# =============================================================================
# 1. COLOR THEME (Dark Theme with Green, White & Red Accents)
# =============================================================================
# Dark Backgrounds
BG     = "#08100a"       # Obsidian forest dark background
PANEL  = "#0e1a12"       # Dark foliage slate panel
CARD   = "#15261a"       # Component card container
BORDER = "#213d29"       # Crisp dark green border

# Pure White & Crisp Text
WHITE  = "#ffffff"       # Crisp pure white
TEXT   = "#f8fafc"       # Clean off-white
MUTED  = "#94a3b8"       # Silver slate secondary text
DARK   = "#041208"       # Dark text on bright white or bright green buttons

# Green Theme Shades (Primary / Healthy / Confirm)
GREEN_PRIMARY = "#16a34a"   # Emerald Lush Green
GREEN_ACCENT  = "#22c55e"   # Bright vibrant leaf green
GREEN_GLOW    = "#4ade80"   # Light highlight green
GREEN_HOVER   = "#15803d"   # Darker green hover

# Red Accents (Disease Alert / Close / Critical)
RED_ALERT   = "#ef4444"     # Vivid disease warning & [CLOSE APPLICATION]
RED_HOVER   = "#dc2626"     # Deep red hover
RED_CARD    = "#2d1212"     # Subtle dark red card background

# Secondary & Status
AMBER_WARN  = "#f59e0b"     # Out-of-catalog warning & [RETAKE]
GREY_BTN    = "#283b2f"     # Subtle card buttons
WHITE_BTN   = "#ffffff"     # High-contrast white buttons

FONT = "Segoe UI" if platform.system() == "Windows" else "DejaVu Sans"

# Application Version & Build Information
APP_VERSION = "4.2.0"
BUILD_TIMESTAMP = "2026-11-01 07:12:32 IST"

# =============================================================================
# 2. PATH DISCOVERY & SETTINGS
# =============================================================================
CANDIDATE_MODEL_DIRS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "model") if "__file__" in globals() else "",
    os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else "",
    os.path.join(os.getcwd(), "model"),
    os.getcwd(),
    r"C:\Users\Shreyance Engineer\.gemini\antigravity\scratch\agrilens_ui\model",
    r"G:\My Drive\EXPISCOR 2026",
    "/home/pi/agrilens_ui/model",
    "/home/pi/agrilens_ui",
]

def find_file(filename):
    for d in CANDIDATE_MODEL_DIRS:
        if d and os.path.exists(d):
            p = os.path.join(d, filename)
            if os.path.exists(p):
                return p
    return filename

MODEL_PATH = find_file("agrilens.onnx")
LABELS_PATH = find_file("labels.txt")

APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
DIAGNOSIS_SAMPLES_DIR = os.path.join(APP_BASE_DIR, "diagnosis_samples")
DIAGNOSIS_SPECIES_FOLDERS = ("Apple", "Mango", "Potato", "Tomato")


def ensure_diagnosis_samples_dir():
    """Ensures the fixed folder structure diagnosis_samples/{Apple,Mango,Potato,Tomato} exists."""
    try:
        os.makedirs(DIAGNOSIS_SAMPLES_DIR, exist_ok=True)
        for sp in DIAGNOSIS_SPECIES_FOLDERS:
            os.makedirs(os.path.join(DIAGNOSIS_SAMPLES_DIR, sp), exist_ok=True)
    except Exception:
        pass
    return DIAGNOSIS_SAMPLES_DIR

# Calibrated confidence & Out-Of-Distribution (OOD) rejection thresholds
CONFIDENCE_THRESHOLD = 0.50  # Minimum positive identification threshold (50%)
OOD_MARGIN_THRESHOLD = 0.18  # Minimum gap between 1st and 2nd class
OOD_LOGIT_THRESHOLD  = 2.00  # Minimum raw logit activation for supported crops
SHARPNESS_MIN_THRESHOLD = 35.0  # Minimum spatial Laplacian focus sharpness variance

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiosk_config.json") if "__file__" in globals() else "kiosk_config.json"
USER_CONFIG_PATH = os.path.expanduser("~/.agrilens_kiosk_config.json")
DEFAULT_CONFIG = {
    "confidence_threshold": CONFIDENCE_THRESHOLD,
    "ood_margin": OOD_MARGIN_THRESHOLD,
    "ood_logit": OOD_LOGIT_THRESHOLD,
    "sharpness_min": SHARPNESS_MIN_THRESHOLD,
    "cam_contrast": 100,
    "cam_brightness": 0,
    "cam_saturation": 100,
    "cam_sharpness": 100,
    "cam_wb_temp": 0,
    "cam_zoom": 100,
    "cam_flip_h": False,
    "cam_flip_v": False,
    "cam_auto_exp": True,
    "cam_auto_wb": True,
}

def _clamp_num(val, default, lo, hi, as_int=False):
    try:
        v = float(val)
        v = max(float(lo), min(float(hi), v))
        return int(round(v)) if as_int else v
    except Exception:
        return int(default) if as_int else float(default)


def load_kiosk_config():
    cfg = dict(DEFAULT_CONFIG)
    for path in (CONFIG_PATH, USER_CONFIG_PATH):
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cfg.update(data)
            except Exception as e:
                print(f"Notice: loading config from {path} ({e})")

    # Sanitize & clamp loaded parameters so corrupted JSON values never break startup
    cfg["confidence_threshold"] = _clamp_num(cfg.get("confidence_threshold"), CONFIDENCE_THRESHOLD, 0.30, 0.95)
    cfg["ood_margin"] = _clamp_num(cfg.get("ood_margin"), OOD_MARGIN_THRESHOLD, 0.10, 0.60)
    cfg["ood_logit"] = _clamp_num(cfg.get("ood_logit"), OOD_LOGIT_THRESHOLD, 1.00, 6.50)
    cfg["sharpness_min"] = _clamp_num(cfg.get("sharpness_min"), SHARPNESS_MIN_THRESHOLD, 20.0, 120.0)

    # Auto-migrate legacy overly-strict thresholds (0.65 / 0.30 / 4.20) in ~/.agrilens_kiosk_config.json
    if cfg["ood_logit"] >= 4.0 and cfg["confidence_threshold"] >= 0.64:
        cfg["confidence_threshold"] = CONFIDENCE_THRESHOLD
        cfg["ood_margin"] = OOD_MARGIN_THRESHOLD
        cfg["ood_logit"] = OOD_LOGIT_THRESHOLD
        cfg["sharpness_min"] = SHARPNESS_MIN_THRESHOLD

    cfg["cam_contrast"] = _clamp_num(cfg.get("cam_contrast"), 100, 50, 200, as_int=True)
    cfg["cam_brightness"] = _clamp_num(cfg.get("cam_brightness"), 0, -50, 50, as_int=True)
    cfg["cam_saturation"] = _clamp_num(cfg.get("cam_saturation"), 100, 0, 200, as_int=True)
    cfg["cam_sharpness"] = _clamp_num(cfg.get("cam_sharpness"), 100, 50, 250, as_int=True)
    cfg["cam_wb_temp"] = _clamp_num(cfg.get("cam_wb_temp"), 0, -50, 50, as_int=True)
    cfg["cam_zoom"] = _clamp_num(cfg.get("cam_zoom"), 100, 100, 200, as_int=True)
    for bkey, bdef in (("cam_flip_h", False), ("cam_flip_v", False), ("cam_auto_exp", True), ("cam_auto_wb", True)):
        val = cfg.get(bkey, bdef)
        cfg[bkey] = val if isinstance(val, bool) else bdef
    return cfg

def save_kiosk_config(cfg):
    for path in (USER_CONFIG_PATH, CONFIG_PATH):
        if not path:
            continue
        try:
            if os.path.exists(path):
                try:
                    os.chmod(path, 0o666)
                except Exception:
                    pass
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
        except Exception as e:
            print(f"Notice: unable to save kiosk config to {path} ({e})")

def ensure_rpi_autostart():
    """
    Automatically registers AGRILENS to launch immediately on Raspberry Pi boot
    (zero-delay XDG + Wayfire/Labwc compositor autostart) to skip showing the home screen.
    """
    if platform.system() != "Linux" or "__file__" not in globals():
        return
    try:
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        py_exe = sys.executable or "/usr/bin/python3"
        launch_cmd = f"/bin/sh -c \"cd '{script_dir}' && '{py_exe}' '{script_path}'\""

        # 1. XDG Autostart (launches automatically on desktop session start)
        autostart_dir = os.path.expanduser("~/.config/autostart")
        os.makedirs(autostart_dir, exist_ok=True)
        desktop_file = os.path.join(autostart_dir, "agrilens.desktop")
        content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=AGRILENS Kiosk\n"
            "Comment=AGRILENS AI Plant Health Kiosk Auto-Start\n"
            f"Exec={launch_cmd}\n"
            f"Path={script_dir}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        with open(desktop_file, "w", encoding="utf-8") as f:
            f.write(content)
        os.chmod(desktop_file, 0o755)

        # Clean up any duplicate compositor autostart entries so only one instance launches on boot
        wf_ini = os.path.expanduser("~/.config/wayfire.ini")
        if os.path.exists(wf_ini):
            try:
                with open(wf_ini, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                cleaned = [ln for ln in lines if "agrilens_kiosk" not in ln]
                if len(cleaned) != len(lines):
                    with open(wf_ini, "w", encoding="utf-8") as f:
                        f.writelines(cleaned)
            except Exception:
                pass

        labwc_auto = os.path.expanduser("~/.config/labwc/autostart")
        if os.path.exists(labwc_auto):
            try:
                with open(labwc_auto, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                cleaned = [ln for ln in lines if script_path not in ln]
                if len(cleaned) != len(lines):
                    with open(labwc_auto, "w", encoding="utf-8") as f:
                        f.writelines(cleaned)
            except Exception:
                pass
    except Exception as e:
        print(f"Notice: autostart registration skipped ({e})")

ADMIN_PASSWORD = "AGRILENS"
PREVIEW_FPS = 25
RESAMPLE = RESAMPLE_BILINEAR

# =============================================================================
# 3. FARMER RECOMMENDATIONS DATABASE
# =============================================================================
DISCLAIMER = (
    "Agricultural advice only. Consult your local extension officer "
    "before applying chemical treatments."
)

RECOMMENDATIONS = [
    (("healthy",), [
        "The crop shows healthy leaf tissue. No chemical spray is required.",
        "Water at the base early in the morning; keep the foliage dry.",
        "Inspect lower leaves weekly for early signs of spots or insects.",
        "Maintain clean soil borders and remove fallen debris from the bed.",
    ]),
    (("scab",), [
        "Remove and safely burn or bury infected leaves to stop fungal spores.",
        "Prune crowded branches to let sunlight and drying winds circulate.",
        "Apply recommended protective fungicide (e.g., Mancozeb or Captan).",
        "Avoid overhead watering that keeps leaves wet through the night.",
    ]),
    (("black rot",), [
        "Prune dead twigs and cankered branches 15 cm below infected margins.",
        "Collect and destroy all mummified fruit and infected leaf fall.",
        "Spray an approved protective fungicide from bud burst to petal fall.",
        "Always disinfect pruning shears with alcohol between every tree.",
    ]),
    (("rust", "cedar apple rust"), [
        "Check and remove any wild juniper/cedar host bushes within 500 m.",
        "Apply recommended fungicides at the pink-bud and petal-fall stages.",
        "Rake and destroy fallen autumn foliage to prevent winter carryover.",
    ]),
    (("bacterial spot",), [
        "Immediately pick and dispose of spotted foliage; never work while wet.",
        "Apply copper-based bactericide sprays as directed by local guidelines.",
        "Use drip irrigation to prevent water splashing spores onto foliage.",
        "Practice crop rotation with non-solanaceous crops for 2-3 years.",
    ]),
    (("early blight",), [
        "Prune lower infected leaves; burn or bury them (do not compost).",
        "Apply clean organic mulch to prevent rain splashing spores from soil.",
        "Spray recommended fungicide (e.g., Mancozeb or Chlorothalonil).",
        "Rotate fields next season; avoid planting tomato after potato.",
    ]),
    (("late blight",), [
        "URGENT: Highly contagious blight that spreads rapidly in cool damp air.",
        "Immediately uproot and destroy severely infected tomato plants.",
        "Apply systemic fungicide immediately to protect adjacent healthy plants.",
        "Stop all overhead sprinkler irrigation immediately.",
    ]),
    (("leaf mold",), [
        "Increase spacing between plants and prune lower suckers for airflow.",
        "Ventilate field or greenhouse thoroughly to lower relative humidity.",
        "Spray approved protective copper or sulfur fungicide if spread continues.",
    ]),
    (("septoria",), [
        "Pinch off infected lower leaves as soon as circular spots appear.",
        "Keep ground mulched and keep overhead water away from leaves.",
        "Apply protective fungicide sprays on a 7 to 10 day schedule.",
    ]),
    (("spider mite",), [
        "Spray undersides of leaves with a forceful jet of clean water.",
        "Apply organic neem oil extract or insecticidal soap every 5-7 days.",
        "Maintain regular irrigation; spider mites thrive in dry dusty heat.",
    ]),
    (("target spot",), [
        "Remove lower infected foliage to reduce fungal spore pressure.",
        "Improve plant spacing and stake vines to boost canopy airflow.",
        "Apply recommended protective fungicide (e.g., Chlorothalonil or Mancozeb).",
        "Use drip irrigation and mulch to prevent soil splash onto lower leaves.",
    ]),
    (("yellow leaf curl",), [
        "Viral infection transmitted by whiteflies. Plants cannot be cured.",
        "Uproot and bag diseased plants immediately to protect neighbors.",
        "Install yellow sticky traps and reflective mulch to deter whiteflies.",
        "Select certified TYLCV-resistant seedlings for your next cycle.",
    ]),
    (("mosaic",), [
        "Viral disease. Remove and safely dispose of infected plants.",
        "Disinfect hands and tools with soap and water after handling plants.",
        "Do not allow smoking or tobacco handling near tomato crops.",
    ]),
    (("anthracnose",), [
        "Prune dead twigs, diseased leaves, and dry inflorescences.",
        "Spray Copper Oxychloride (0.3%) before flowering and after harvest.",
        "Prune the tree canopy to allow sun to penetrate internal branches.",
    ]),
    (("powdery mildew",), [
        "Spray wettable sulfur (0.2%) or Hexaconazole at panicle emergence.",
        "Prune overcrowded shoots to lower internal canopy humidity.",
        "Collect and burn fallen infested flower panicles.",
    ]),
    (("die back", "dieback"), [
        "Cut infected twigs 8-10 cm below the visible margin of dried wood.",
        "Immediately paint cut surfaces with fresh Bordeaux paste.",
        "Maintain balanced tree nutrition with recommended NPK and zinc.",
    ]),
    (("bacterial canker",), [
        "Prune cankered branches and treat wound surfaces with copper spray.",
        "Spray Streptocycline (100 ppm) combined with copper oxychloride.",
        "Plant protective windbreaks to prevent wind-borne leaf abrasions.",
    ]),
    (("sooty mo",), [
        "Black fungus grows on sweet honeydew secreted by hoppers or mealybugs.",
        "Spray 2% dilute starch solution or neem oil to flake off soot layer.",
        "Treat the underlying sucking pests (mango hoppers or scale insects).",
    ]),
    (("cutting weevil", "gall midge"), [
        "Collect and safely dispose of clipped or deformed gall-bearing leaves.",
        "Spray approved botanical or neem-based insecticide at new leaf flush.",
        "Plow the soil beneath the canopy to expose overwintering pupae.",
    ]),
]

UNSURE_STEPS = [
    "Check the Image Quality rating shown below the camera view.",
    "Hold one single leaf flat and fully centered inside the green box.",
    "Make sure lighting is even and there is no harsh direct glare or shadow.",
    "Auto mode is in Beta Production. Tap 'SELECT CROP' to focus on your crop.",
]

OOD_STEPS = [
    "This leaf does not match features of supported crops (Apple, Mango, Potato, Tomato).",
    "Non-target plants (e.g. money plant, ornamental flora, weeds) are outside catalog.",
    "If diagnosing a supported crop, tap 'SELECT CROP' to lock your target crop.",
    "To support this plant species, add it to the dataset and retrain the model.",
]

DEFAULT_STEPS = [
    "Possible crop condition observed on this specimen.",
    "Isolate this plant to prevent potential spread to adjacent rows.",
    "Bring this leaf sample to your local agricultural office for inspection.",
    "Avoid overhead watering to minimize standing leaf moisture.",
]

def get_recommendation(crop, condition):
    text = f"{crop} {condition}".lower()
    for keys, steps in RECOMMENDATIONS:
        if any(k in text for k in keys):
            return steps
    return DEFAULT_STEPS


def parse_label(label):
    clean = label.strip()
    while "__" in clean:
        clean = clean.replace("__", "_")
    healthy = "healthy" in clean.lower()
    if ("other" in clean.lower()) or ("background" in clean.lower()):
        return "", clean.replace("_", " ").title(), False
    for sep in (" - ", ": ", "_"):
        if sep in clean:
            parts = clean.split(sep, 1)
            crop = parts[0].replace("_", " ").title().strip()
            cond = parts[1].replace("_", " ").title().strip()
            return crop, cond, healthy
    return "", clean.replace("_", " ").title(), healthy


# =============================================================================
# 3.5. LEAF REGION DETECTION & SMART ROI EXTRACTION ENGINE
# =============================================================================
class LeafOutlineSegmenter:
    """
    Non-destructive Leaf ROI detector optimized for both real leaves and mobile screen testing:
    - Detects foliage & leaf regions using Excess Green (ExG), HSV color saturation, and Canny edges.
    - Rejects outer frame borders (such as mobile phone bezels or dark room edges).
    - Preserves natural background context inside the cropped square ROI (does NOT paint #000000 black
      masks that distort MobileNetV4 convolutional filters).
    - Graceful fallback: If the leaf already fills the frame or no sub-region is isolated,
      uses the complete image without alteration.
    """
    @staticmethod
    def extract_leaf(pil_image, min_area_ratio=0.06, max_area_ratio=0.65):
        if pil_image is None:
            return None, False, {"msg": "Camera frame not available."}
        if np is None or cv2 is None:
            return pil_image, False, {"msg": "OpenCV/NumPy unavailable, using complete image."}

        try:
            orig_np = np.array(pil_image.convert("RGB"))
            h, w = orig_np.shape[:2]
            total_area = float(w * h)

            # 1. Compute foliage / leaf color mask (Excess Green + HSV green/yellow-green leaf range)
            r = orig_np[:, :, 0].astype(np.float32)
            g = orig_np[:, :, 1].astype(np.float32)
            b = orig_np[:, :, 2].astype(np.float32)
            exg = 2.0 * g - r - b
            green_dom = g - 0.55 * r - 0.45 * b

            hsv = cv2.cvtColor(orig_np, cv2.COLOR_RGB2HSV)
            hue = hsv[:, :, 0]
            sat = hsv[:, :, 1]
            val = hsv[:, :, 2]

            # Exclude warm skin/wood/indoor walls (Hue < 24 unless G > R) while supporting blue-lit phone screens
            is_foliage = (
                ((exg > 10.0) & (g > 28.0))
                | ((green_dom > 6.0) & (g > r) & (val > 35))
                | ((hue >= 24) & (hue <= 102) & (sat >= 32) & (val >= 30) & (val <= 248))
            )
            foliage_mask = np.where(is_foliage, 255, 0).astype(np.uint8)

            # Zero out outer 4% border so a dark phone bezel or screen frame doesn't bridge across the image
            bh_pad, bw_pad = max(2, int(h * 0.04)), max(2, int(w * 0.04))
            foliage_mask[:bh_pad, :] = 0
            foliage_mask[h - bh_pad:, :] = 0
            foliage_mask[:, :bw_pad] = 0
            foliage_mask[:, w - bw_pad:] = 0

            kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
            closed = cv2.morphologyEx(foliage_mask, cv2.MORPH_CLOSE, kernel_close)

            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return pil_image, False, {"msg": "Full frame used for diagnosis.", "area_ratio": 1.0}

            contours = sorted(contours, key=cv2.contourArea, reverse=True)
            best_cnt = None
            best_area = 0.0

            for cnt in contours:
                area = float(cv2.contourArea(cnt))
                ratio = area / total_area
                if ratio < min_area_ratio:
                    continue
                if ratio > max_area_ratio:
                    # Leaf or screen already fills a large portion of the frame -> keep full frame intact
                    # so multi-scale square center crops in Classifier.predict() preserve full leaf context!
                    return pil_image, True, {
                        "msg": f"Leaf fills frame ({ratio * 100:.1f}% area).",
                        "area_ratio": ratio,
                        "bbox": (0, 0, w, h)
                    }
                best_cnt = cnt
                best_area = area
                break

            if best_cnt is None:
                return pil_image, False, {"msg": "Full frame used for diagnosis.", "area_ratio": 1.0}

            # Crop a clean square bounding box around the detected leaf with generous 1.45x context margin
            # so outer leaf edges and brown/yellow necrotic lesions are never clipped off
            bx, by, bw, bh = cv2.boundingRect(best_cnt)
            cx = bx + bw // 2
            cy = by + bh // 2
            side = int(max(bw, bh) * 1.45)
            side = max(min(w, h) // 2, min(side, min(w, h)))

            x0 = max(0, min(w - side, cx - side // 2))
            y0 = max(0, min(h - side, cy - side // 2))
            cropped_np = orig_np[y0:y0 + side, x0:x0 + side]
            result_pil = Image.fromarray(cropped_np)

            return result_pil, True, {
                "msg": f"Leaf ROI focused ({best_area / total_area * 100:.1f}% area).",
                "area_ratio": best_area / total_area,
                "bbox": (x0, y0, side, side)
            }

        except Exception as e:
            return pil_image, False, {"msg": f"Full frame used ({e}).", "area_ratio": 1.0}


# =============================================================================
# 4. LEAF IMAGE QUALITY AI (Sharpness, Lighting & Foliage Validator)
# =============================================================================
class LeafQualityAI:
    """
    Evaluates leaf image quality for field disease diagnostics:
    1. Sharpness / Focus (Motion blur & focus detection via spatial high-freq gradients)
    2. Lighting & Exposure (Luminance distribution & specular glare / darkness check)
    3. Foliage & Leaf Presence (Excess Green Index & central leaf coverage check)
    """
    @staticmethod
    def assess(pil_image, min_sharpness=55.0):
        if np is None or pil_image is None:
            return 80, "GOOD", "Image Quality: Acceptable", GREEN_ACCENT

        try:
            # Resize thumbnail for fast 1ms evaluation
            thumb = pil_image.resize((224, 224), RESAMPLE)
            arr = np.asarray(thumb.convert("RGB"), dtype=np.float32)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

            # 1. Luminance & Exposure check
            gray = 0.299 * r + 0.587 * g + 0.114 * b
            mean_lum = float(np.mean(gray))

            if mean_lum < 42.0:
                exposure_score = max(10, int(mean_lum * 1.5))
                lighting_status = "Too Dark (Low Light)"
            elif mean_lum > 220.0:
                exposure_score = max(15, int((255 - mean_lum) * 2.5))
                lighting_status = "Overexposed (Too Bright / Glare)"
            else:
                exposure_score = min(100, int(100 - abs(mean_lum - 128) * 0.45))
                lighting_status = "Good Lighting"

            # 2. Sharpness / Blur check (Spatial Laplacian variance)
            lap = (
                gray[1:-1, :-2] + gray[1:-1, 2:] +
                gray[:-2, 1:-1] + gray[2:, 1:-1] -
                4.0 * gray[1:-1, 1:-1]
            )
            sharp_var = float(np.var(lap))

            # Calibrated sharpness scoring relative to min_sharpness
            base_s = max(10.0, float(min_sharpness))
            if sharp_var > (base_s * 4.0):
                sharpness_score = 98
                sharp_status = "Sharp & In Focus"
            elif sharp_var > (base_s * 2.0):
                sharpness_score = int(70 + (sharp_var - base_s * 2.0) * (28.0 / (base_s * 2.0)))
                sharp_status = "Good Focus"
            elif sharp_var >= base_s:
                sharpness_score = int(45 + (sharp_var - base_s) * (25.0 / base_s))
                sharp_status = "Slightly Blurry"
            else:
                sharpness_score = max(10, int(sharp_var * (45.0 / base_s)))
                sharp_status = "Blurry (Motion Blur)"

            # 3. Leaf Presence (Center Box Coverage via Excess Green Index: 2G - R - B)
            h, w = arr.shape[:2]
            y0, y1 = int(h * 0.2), int(h * 0.8)
            x0, x1 = int(w * 0.2), int(w * 0.8)
            center_g = g[y0:y1, x0:x1]
            center_r = r[y0:y1, x0:x1]
            center_b = b[y0:y1, x0:x1]

            exg = 2.0 * center_g - center_r - center_b
            leaf_pixels = np.mean((exg > 8.0) | ((center_g > center_r) & (center_g > 35.0)))

            if leaf_pixels > 0.35:
                presence_score = 95
                presence_status = "Leaf Centered"
            elif leaf_pixels > 0.18:
                presence_score = 75
                presence_status = "Partial Leaf"
            else:
                presence_score = 30
                presence_status = "No Leaf in Box"

            # Composite Quality Score (0 - 100%)
            overall_score = int(0.40 * sharpness_score + 0.30 * exposure_score + 0.30 * presence_score)
            overall_score = max(5, min(99, overall_score))

            # Verdict & Color
            if overall_score >= 75 and sharpness_score >= 60 and exposure_score >= 50:
                rating = "EXCELLENT"
                msg = f"Quality: {overall_score}% (Sharp & Clear - Ready to Diagnose)"
                color = GREEN_ACCENT
            elif overall_score >= 50:
                rating = "GOOD"
                msg = f"Quality: {overall_score}% ({sharp_status})"
                color = GREEN_PRIMARY
            elif sharpness_score < 45:
                rating = "POOR"
                msg = f"Quality: {overall_score}% ({sharp_status} — Hold still & Retake)"
                color = AMBER_WARN
            elif exposure_score < 45:
                rating = "POOR"
                msg = f"Quality: {overall_score}% ({lighting_status} — Adjust Light)"
                color = AMBER_WARN
            else:
                rating = "POOR"
                msg = f"Quality: {overall_score}% ({presence_status} — Center Leaf in Box)"
                color = RED_ALERT

            return overall_score, rating, msg, color

        except Exception as e:
            return 75, "GOOD", f"Quality: Ready ({e})", GREEN_ACCENT


# =============================================================================
# 5. WEBCAM INTERFACE (Multi-Backend, High-Speed Video Capture)
# =============================================================================
class Camera:
    def __init__(self, auto_detect=True):
        self._lock = threading.Lock()
        self.cap = None
        self.cv2 = None
        self.kind = "none"
        self.port = -1
        self.backend = "none"
        self.width = 640
        self.height = 480
        self.device_name = "USB Camera"
        self.fail_count = 0

        # USB Hardware + ISP Parameters
        self.contrast = 100      # 50% to 200% (100% = neutral)
        self.brightness = 0      # -50% to +50% (0% = neutral)
        self.saturation = 100    # 0% to 200% (100% = neutral)
        self.sharpness = 100     # 50% to 250% (100% = neutral)
        self.wb_temp = 0         # -50 (Cool) to +50 (Warm) (0 = neutral)
        self.zoom = 100          # 100% (1.0x) to 200% (2.0x Macro Zoom)
        self.flip_h = False      # Mirror horizontally
        self.flip_v = False      # Flip vertically (180 deg)
        self.auto_exp = True     # USB UVC Auto-Exposure + Backlight Compensation
        self.auto_wb = True      # USB UVC Auto White Balance
        self.focus_peaking = False  # Neon edge highlight for Manual Focus Mod

        # Silence noisy OpenCV C++ backend/obsensor log spam
        try:
            import cv2
            self.cv2 = cv2
            self.cv2.utils.logging.setLogLevel(self.cv2.utils.logging.LOG_LEVEL_ERROR)
        except Exception:
            pass

        if auto_detect:
            self.detect_webcam()

    def _fetch_friendly_names_async(self):
        """Discovers friendly hardware device names in background without blocking the UI."""
        def worker():
            names = []
            if sys.platform.startswith("win"):
                try:
                    cmd = ["powershell", "-NoProfile", "-Command",
                           "Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName"]
                    res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                    for line in res.stdout.splitlines():
                        clean = line.strip()
                        if clean and clean not in names:
                            names.append(clean)
                except Exception:
                    pass
            elif sys.platform.startswith("linux"):
                for p in sorted(glob.glob("/sys/class/video4linux/video*/name")):
                    try:
                        with open(p, "r") as f:
                            n = f.read().strip()
                            if n and n not in names:
                                names.append(n)
                    except Exception:
                        pass
            if names and self.kind != "none":
                dev = names[self.port] if (0 <= self.port < len(names)) else names[0]
                self.device_name = dev
                self.kind = f"{dev} (Port {self.port}, {self.backend}, {self.width}x{self.height})"
        threading.Thread(target=worker, daemon=True).start()

    def detect_webcam(self):
        """
        Fast, high-robustness camera scanner using prioritized platform backends:
        - Windows: DirectShow (CAP_DSHOW) -> Default (CAP_ANY)
        - Linux/RPi: Video4Linux2 (CAP_V4L2) -> Default (CAP_ANY)
        Configures resolution, buffersize, and warm-up reads before locking connection.
        """
        with self._lock:
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None

            if self.cv2 is None:
                try:
                    import cv2
                    self.cv2 = cv2
                    self.cv2.utils.logging.setLogLevel(self.cv2.utils.logging.LOG_LEVEL_ERROR)
                except ImportError:
                    self.kind = "none"
                    return False, "OpenCV (cv2) is not installed."

            # Build prioritized backend list
            if sys.platform.startswith("win"):
                backends = [
                    ("DirectShow", self.cv2.CAP_DSHOW),
                    ("Default", self.cv2.CAP_ANY)
                ]
            elif sys.platform.startswith("linux"):
                backends = [
                    ("V4L2", self.cv2.CAP_V4L2),
                    ("Default", self.cv2.CAP_ANY)
                ]
            else:
                backends = [("Default", self.cv2.CAP_ANY)]

            # Probe ports with cascading backends (ports 0, 1, 2)
            for b_name, b_id in backends:
                for port in range(3):
                    try:
                        c = self.cv2.VideoCapture(port, b_id)
                        if not c.isOpened():
                            continue

                        # Configure 640x480 resolution & single-frame buffer before reading
                        c.set(self.cv2.CAP_PROP_FRAME_WIDTH, 640)
                        c.set(self.cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        try:
                            c.set(self.cv2.CAP_PROP_BUFFERSIZE, 1)
                        except Exception:
                            pass

                        # Multi-frame warmup: Allow auto-exposure (AEC) and auto-gain (AGC) to stabilize
                        ok, frame = False, None
                        for _ in range(4):
                            ok, frame = c.read()
                            if ok and frame is not None and frame.size > 0:
                                break
                            time.sleep(0.025)

                        if ok and frame is not None and frame.size > 0:
                            h, w = frame.shape[:2]
                            self.cap = c
                            self.port = port
                            self.backend = b_name
                            self.width = w
                            self.height = h
                            self.device_name = "USB Camera"
                            self.kind = f"USB Camera (Port {port}, {b_name}, {w}x{h})"
                            self.fail_count = 0
                            break

                        c.release()
                    except Exception:
                        pass
                if self.cap is not None:
                    break

            if self.cap is None:
                self.kind = "none"
                self.port = -1
                self.backend = "none"
                return False, "No active webcam found. Please plug in USB camera and click DETECT WEBCAM."

        # Apply USB hardware controls & query friendly model name outside the lock
        self.apply_hardware_controls()
        self._fetch_friendly_names_async()
        return True, f"Connected: {self.kind}"

    def apply_hardware_controls(self):
        """Pushes UVC hardware parameters (Auto-Exposure, 50Hz Anti-Flicker, Auto-WB) over USB."""
        if not self.cap or self.cv2 is None:
            return
        port = self.port
        auto_exp = self.auto_exp
        auto_wb = self.auto_wb
        wb_kelvin = int(4500 + self.wb_temp * 34)

        def _hw_worker():
            with self._lock:
                if self.cap and self.cap.isOpened() and self.cv2 is not None:
                    try:
                        if hasattr(self.cv2, "CAP_PROP_AUTO_EXPOSURE"):
                            # V4L2 UVC: 3 = Aperture Priority (Auto), 1 = Manual
                            self.cap.set(self.cv2.CAP_PROP_AUTO_EXPOSURE, 3 if auto_exp else 1)
                        if hasattr(self.cv2, "CAP_PROP_BACKLIGHT"):
                            self.cap.set(self.cv2.CAP_PROP_BACKLIGHT, 1 if auto_exp else 0)
                        if hasattr(self.cv2, "CAP_PROP_AUTO_WB"):
                            self.cap.set(self.cv2.CAP_PROP_AUTO_WB, 1 if auto_wb else 0)
                        if not auto_wb and hasattr(self.cv2, "CAP_PROP_WB_TEMPERATURE"):
                            self.cap.set(self.cv2.CAP_PROP_WB_TEMPERATURE, wb_kelvin)
                    except Exception:
                        pass

            if sys.platform.startswith("linux") and port >= 0:
                dev = f"/dev/video{port}"
                exp_val = 3 if auto_exp else 1
                bl_val = 1 if auto_exp else 0
                awb_val = 1 if auto_wb else 0
                cmds = [
                    ["v4l2-ctl", "-d", dev, "-c", f"power_line_frequency=1,exposure_auto={exp_val},backlight_compensation={bl_val},white_balance_temperature_auto={awb_val}"],
                ]
                if not auto_wb:
                    cmds.append(["v4l2-ctl", "-d", dev, "-c", f"white_balance_temperature={wb_kelvin}"])
                for cmd in cmds:
                    try:
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                    except Exception:
                        pass

        threading.Thread(target=_hw_worker, daemon=True).start()

    def _apply_isp(self, img):
        """Real-time Image Signal Processing (ISP) pipeline for USB frames."""
        try:
            # 1. Orientation Flips (Mirror / 180 Vertical Flip)
            if self.flip_h:
                img = img.transpose(getattr(Image, "Transpose", Image).FLIP_LEFT_RIGHT)
            if self.flip_v:
                img = img.transpose(getattr(Image, "Transpose", Image).FLIP_TOP_BOTTOM)

            # 2. Macro Digital Zoom (100% = 1.0x to 200% = 2.0x center crop)
            if self.zoom > 102:
                w, h = img.size
                zf = max(1.0, min(2.0, self.zoom / 100.0))
                cw, ch = max(16, int(w / zf)), max(16, int(h / zf))
                x0 = (w - cw) // 2
                y0 = (h - ch) // 2
                img = img.crop((x0, y0, x0 + cw, y0 + ch)).resize((w, h), RESAMPLE)

            # 3. White Balance Warmth Tint (-50 Cool to +50 Warm)
            if abs(self.wb_temp) >= 2 and np is not None:
                arr = np.asarray(img, dtype=np.int16)
                shift = int(self.wb_temp * 0.9)
                arr[:, :, 0] = np.clip(arr[:, :, 0] + shift, 0, 255)   # Red warmth
                arr[:, :, 2] = np.clip(arr[:, :, 2] - shift, 0, 255)   # Blue coolness
                img = Image.fromarray(arr.astype(np.uint8))

            # 4. Brightness (-50% to +50% -> factor 0.50 to 1.50)
            if abs(self.brightness) >= 1:
                bf = max(0.3, 1.0 + (self.brightness / 100.0))
                img = ImageEnhance.Brightness(img).enhance(bf)

            # 5. Contrast (50% to 200% -> factor 0.50 to 2.00)
            if abs(self.contrast - 100) >= 1:
                cf = max(0.3, self.contrast / 100.0)
                img = ImageEnhance.Contrast(img).enhance(cf)

            # 6. Saturation / Color Vibrancy (0% to 200% -> factor 0.00 to 2.00)
            if abs(self.saturation - 100) >= 1:
                sf = max(0.0, self.saturation / 100.0)
                img = ImageEnhance.Color(img).enhance(sf)

            # 7. Sharpness / Leaf Vein Detail (50% to 250% -> factor 0.50 to 2.50)
            if abs(self.sharpness - 100) >= 2:
                shf = max(0.2, self.sharpness / 100.0)
                img = ImageEnhance.Sharpness(img).enhance(shf)
        except Exception:
            pass
        return img

    def compute_focus_metric(self, img):
        """Computes real-time focus sharpness (0-100%) for calibrating the manual focus ring."""
        if np is None or img is None:
            return 75, 50.0
        try:
            small = img.resize((240, 180), RESAMPLE)
            arr = np.asarray(small, dtype=np.float32)
            gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
            h, w = gray.shape
            c = gray[int(h * 0.15):int(h * 0.85), int(w * 0.15):int(w * 0.85)]
            lap = (
                -4.0 * c[1:-1, 1:-1]
                + c[:-2, 1:-1] + c[2:, 1:-1]
                + c[1:-1, :-2] + c[1:-1, 2:]
            )
            lap_var = float(np.var(lap))
            pct = int(max(5, min(100, (lap_var / 140.0) * 100.0)))
            return pct, lap_var
        except Exception:
            return 70, 50.0

    def render_focus_peaking(self, img):
        """Highlights razor-sharp leaf veins/edges in neon green when twisting the manual focus ring."""
        if not self.focus_peaking or np is None or img is None:
            return img
        try:
            arr = np.asarray(img, dtype=np.uint8).copy()
            gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.float32)
            gx = np.abs(gray[:, 2:] - gray[:, :-2])[1:-1, :]
            gy = np.abs(gray[2:, :] - gray[:-2, :])[:, 1:-1]
            mag = gx + gy
            mask = mag > 42.0
            sub = arr[1:-1, 1:-1]
            sub[mask] = [0, 255, 110]
            return Image.fromarray(arr)
        except Exception:
            return img

    def read(self):
        """Reads the latest camera frame, applies ISP controls, and handles dropped signals."""
        with self._lock:
            if not self.cap or not self.cap.isOpened():
                return None
            try:
                ok, frame = self.cap.read()
                if ok and frame is not None and frame.size > 0:
                    self.fail_count = 0
                    rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
                else:
                    self.fail_count += 1
                    if self.fail_count > 30:  # ~1 second of continuous frame drops
                        try:
                            self.cap.release()
                        except Exception:
                            pass
                        self.cap = None
                        self.kind = "none"
                    return None
            except Exception:
                self.fail_count += 1
                if self.fail_count > 30:
                    try:
                        self.cap.release()
                    except Exception:
                        pass
                    self.cap = None
                    self.kind = "none"
                return None
        pil_img = Image.fromarray(rgb)
        return self._apply_isp(pil_img)

    def close(self):
        """Safely releases the hardware camera handle."""
        with self._lock:
            if self.cap:
                try:
                    self.cap.release()
                except Exception:
                    pass
                self.cap = None


# =============================================================================
# 6. AI CLASSIFIER (MobileNetV4 ONNX Engine)
# =============================================================================
class Classifier:
    def __init__(self, model_file, labels_file):
        self.model_path = model_file
        self.labels_path = labels_file
        self.mode = "DEMO"
        self.error_reason = ""
        self.labels = self._load_labels()
        self.session = None
        self.input_name = None
        self.input_shape = [1, 3, 224, 224]
        self.layout = "NCHW"
        self.w, self.h = 224, 224

        self._init_engine()

    def _load_labels(self):
        if os.path.exists(self.labels_path):
            try:
                with open(self.labels_path, "r", encoding="utf-8") as f:
                    lines = [line.strip() for line in f if line.strip()]
                    clean = []
                    for line in lines:
                        parts = line.split(maxsplit=1)
                        lbl = parts[1] if (len(parts) == 2 and parts[0].isdigit()) else line
                        while "__" in lbl:
                            lbl = lbl.replace("__", "_")
                        clean.append(lbl)
                    if clean:
                        return clean
            except Exception as e:
                print("Labels load error:", e)

        return [
            "Apple_Rust", "Apple_Scab", "Apple_healthy",
            "Mango_Anthracnose", "Mango_Bacterial_Canker", "Mango_Cutting_Weevil",
            "Mango_Die_Back", "Mango_Gall_Midge", "Mango_Healthy",
            "Mango_Powdery_Mildew", "Mango_Sooty_Mould",
            "Potato_Early_blight", "Potato_Late_blight", "Potato_healthy",
            "Tomato_Bacterial_spot", "Tomato_Early_blight", "Tomato_Late_blight",
            "Tomato_Leaf_Mold", "Tomato_Septoria_leaf_spot",
            "Tomato_Spider_mites_Two_spotted_spider_mite", "Tomato_Target_Spot",
            "Tomato_Tomato_YellowLeaf_Curl_Virus", "Tomato_Tomato_mosaic_virus", "Tomato_healthy"
        ]

    def _init_engine(self):
        if not os.path.exists(self.model_path):
            self.mode = "DEMO"
            self.error_reason = "Model file not found"
            return

        if np is None:
            self.mode = "DEMO"
            self.error_reason = "numpy not installed"
            return

        try:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            self.session = ort.InferenceSession(self.model_path, opts, providers=["CPUExecutionProvider"])
            inp = self.session.get_inputs()[0]
            self.input_name = inp.name

            shape = []
            for d in inp.shape:
                try:
                    shape.append(int(d))
                except (ValueError, TypeError):
                    shape.append(1)
            self.input_shape = shape

            if len(shape) == 4 and shape[1] in (1, 3):
                self.layout, self.h, self.w = "NCHW", shape[2], shape[3]
            else:
                self.layout, self.h, self.w = "NHWC", shape[1], shape[2]

            self.mode = "ONNX (98.31%)"
            self.error_reason = ""
        except ImportError:
            _auto_install_package("onnxruntime", "onnxruntime")
            try:
                import onnxruntime as ort
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 4
                self.session = ort.InferenceSession(self.model_path, opts, providers=["CPUExecutionProvider"])
                inp = self.session.get_inputs()[0]
                self.input_name = inp.name
                shape = []
                for d in inp.shape:
                    try:
                        shape.append(int(d))
                    except (ValueError, TypeError):
                        shape.append(1)
                self.input_shape = shape
                if len(shape) == 4 and shape[1] in (1, 3):
                    self.layout, self.h, self.w = "NCHW", shape[2], shape[3]
                else:
                    self.layout, self.h, self.w = "NHWC", shape[1], shape[2]
                self.mode = "ONNX (98.31%)"
                self.error_reason = ""
            except Exception as e_retry:
                self.mode = "DEMO"
                self.error_reason = f"onnxruntime not installed ({e_retry})"
        except Exception as e:
            self.mode = "DEMO"
            self.error_reason = str(e)

    def _prep_tensor(self, rgb_img):
        img = ImageOps.fit(rgb_img, (self.w, self.h), RESAMPLE)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        if self.layout == "NCHW":
            arr = np.transpose(arr, (2, 0, 1))
        return arr

    @staticmethod
    def _dehaze_screen_glare(pil_img):
        """
        Compensates for optical washout, lifted black levels (glare), and blue OLED/LCD
        backlight cast when photographing a mobile phone screen or under harsh ambient light,
        while strictly preserving the leaf's R:G color ratio.
        """
        if np is None or pil_img is None:
            return pil_img
        try:
            arr = np.asarray(pil_img.convert("RGB"), dtype=np.float32)
            h, w = arr.shape[:2]
            inner = arr[int(h * 0.12):int(h * 0.88), int(w * 0.12):int(w * 0.88)]
            p_low = np.percentile(inner, 1.5, axis=(0, 1))
            rg_floor = max(0.0, min(float(p_low[0]), float(p_low[1])) - 10.0) * 0.85
            b_floor = max(rg_floor, (float(p_low[2]) - 10.0) * 0.88)
            floor_vec = np.array([rg_floor, rg_floor, b_floor], dtype=np.float32)

            shifted = np.maximum(0.0, arr - floor_vec)
            inner_shifted = np.maximum(0.0, inner - floor_vec)

            p_high_ch = np.percentile(inner_shifted, 99.2, axis=(0, 1))
            rg_high = max(float(p_high_ch[0]), float(p_high_ch[1]), 45.0)
            if float(p_high_ch[2]) > rg_high * 1.04:
                shifted[:, :, 2] *= (rg_high / float(p_high_ch[2]))

            scale = min(1.65, 248.0 / rg_high)
            out = np.clip(shifted * scale, 0, 255).astype(np.uint8)
            img = Image.fromarray(out)
            return ImageEnhance.Sharpness(img).enhance(1.25)
        except Exception:
            return pil_img

    def predict(self, pil_image):
        t0 = time.perf_counter()

        # If running in DEMO mode because of missing onnxruntime
        if self.session is None or np is None:
            time.sleep(0.05)
            n = len(self.labels)
            probs = [1.0 / n] * n
            return probs, (time.perf_counter() - t0) * 1000, None

        rgb = pil_image.convert("RGB")
        iw, ih = rgb.size
        min_s = min(iw, ih)

        # Multi-scale 1:1 square center views (100%, 76%, 58% of min_side) in both natural RGB
        # and screen-glare-dehazed RGB to strip phone bezels and counter screen/ambient washout
        views = []
        scales = (1.0, 0.76, 0.58) if min_s >= 120 else (1.0,)
        for scale in scales:
            s = max(64, int(min_s * scale))
            x0, y0 = (iw - s) // 2, (ih - s) // 2
            sq = rgb.crop((x0, y0, x0 + s, y0 + s))
            views.append(sq)
            views.append(self._dehaze_screen_glare(sq))

        batch_tensors = np.stack([self._prep_tensor(v) for v in views], axis=0)

        try:
            batch_out = self.session.run(None, {self.input_name: batch_tensors})[0]
        except Exception:
            batch_out = np.stack(
                [self.session.run(None, {self.input_name: batch_tensors[i:i+1]})[0][0] for i in range(len(views))],
                axis=0
            )

        best_probs = None
        best_raw = None
        best_score = -1e9

        neg_indices = {
            i for i, lbl in enumerate(self.labels)
            if ("other" in lbl.lower()) or ("background" in lbl.lower())
        }

        for i in range(len(batch_out)):
            r_out = batch_out[i]
            exps = np.exp(r_out - np.max(r_out))
            p_vec = exps / np.sum(exps)

            # Score by strongest non-negative crop probability AND raw neural logit energy
            plant_probs = [p_vec[j] for j in range(len(p_vec)) if j not in neg_indices]
            plant_logits = [r_out[j] for j in range(len(r_out)) if j not in neg_indices]
            max_plant_p = float(max(plant_probs)) if plant_probs else float(np.max(p_vec))
            max_plant_l = float(max(plant_logits)) if plant_logits else float(np.max(r_out))
            score = max_plant_p + 0.08 * min(8.0, max(0.0, max_plant_l)) + (0.03 if i < 4 else 0.0)
            if score > best_score:
                best_score = score
                best_probs = p_vec.tolist()
                best_raw = r_out

        ms = (time.perf_counter() - t0) * 1000
        return best_probs, ms, best_raw


# =============================================================================
# 7. INTERACTIVE UI COMPONENTS (Rounded Buttons & Tooltips)
# =============================================================================
class RoundedButton(tk.Canvas):
    """
    Anti-aliased pill-shaped rounded button.
    Renders with 3x supersampled Pillow graphics for smooth curves on dark background.
    Supports hover, press, disable states and standard config() updates.
    """
    _cache = {}

    def __init__(self, parent, text, command, bg_color=GREEN_PRIMARY, fg_color=WHITE,
                 hover_bg=None, width=None, height=38, radius=None, font=None,
                 border_color=None, border_width=1, parent_bg=PANEL, state="normal"):
        self.parent = parent
        self.text = text
        self.command = command
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.parent_bg = parent_bg
        self.state = state
        self.border_color = border_color
        self.border_width = border_width
        self.hover_bg = hover_bg or self._tint(bg_color, 1.15)
        self.active_bg = self._tint(bg_color, 0.85)

        self.font = font or (FONT, 11, "bold")
        self.height = max(24, int(height))
        self.radius = radius if radius is not None else (self.height // 2)

        if width is None:
            w = self._measure_text_width(text) + 28
        elif width <= 35:
            w = max(int(width * 10 + 20), self._measure_text_width(text) + 24)
        else:
            w = int(width)
        self.width = max(32, w)

        super().__init__(parent, width=self.width, height=self.height, bg=parent_bg,
                         highlightthickness=0, bd=0, cursor="hand2" if state != "disabled" else "arrow")

        self.normal_img = self._get_img(self.bg_color)
        self.hover_img = self._get_img(self.hover_bg)
        self.active_img = self._get_img(self.active_bg)
        self.disabled_img = self._get_img(GREY_BTN)

        img = self.disabled_img if self.state == "disabled" else self.normal_img
        self.img_item = self.create_image(self.width // 2, self.height // 2, image=img)
        self.text_item = self.create_text(
            self.width // 2, self.height // 2, text=self.text,
            fill=MUTED if self.state == "disabled" else self.fg_color,
            font=self.font
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _measure_text_width(self, text):
        try:
            if isinstance(self.font, tuple):
                f = tkFont.Font(family=self.font[0], size=self.font[1], weight=self.font[2] if len(self.font) > 2 else "normal")
            else:
                f = tkFont.nametofont(self.font)
            return f.measure(text)
        except Exception:
            return len(text) * 9

    def _tint(self, hex_color, factor):
        try:
            hex_color = hex_color.lstrip("#")
            r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r = min(255, max(0, int(r * factor)))
            g = min(255, max(0, int(g * factor)))
            b = min(255, max(0, int(b * factor)))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _get_img(self, fill):
        key = (self.width, self.height, self.radius, fill, self.border_color, self.border_width, self.parent_bg)
        if key in self._cache:
            return self._cache[key]
        if len(self._cache) > 256:
            self._cache.clear()
        scale = 3
        sw, sh, sr = self.width * scale, self.height * scale, self.radius * scale
        im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=fill,
                            outline=self.border_color, width=self.border_width * scale if self.border_color else 0)
        res = im.resize((self.width, self.height), RESAMPLE_LANCZOS)
        photo = ImageTk.PhotoImage(res)
        self._cache[key] = photo
        return photo

    def _on_enter(self, e):
        if self.state != "disabled":
            self.itemconfig(self.img_item, image=self.hover_img)

    def _on_leave(self, e):
        if self.state != "disabled":
            self.itemconfig(self.img_item, image=self.normal_img)

    def _on_press(self, e):
        if self.state != "disabled":
            self.itemconfig(self.img_item, image=self.active_img)

    def _on_release(self, e):
        if self.state != "disabled":
            self.itemconfig(self.img_item, image=self.hover_img)
            if self.command:
                self.command()

    def config(self, **kwargs):
        redraw = False
        if "text" in kwargs:
            self.text = kwargs.pop("text")
            self.itemconfig(self.text_item, text=self.text)
        if "fg" in kwargs:
            self.fg_color = kwargs.pop("fg")
            self.itemconfig(self.text_item, fill=self.fg_color)
        if "bg" in kwargs:
            self.bg_color = kwargs.pop("bg")
            self.hover_bg = self._tint(self.bg_color, 1.15)
            self.active_bg = self._tint(self.bg_color, 0.85)
            redraw = True
        if "border" in kwargs:
            self.border_color = kwargs.pop("border")
            redraw = True
        if "state" in kwargs:
            self.state = kwargs.pop("state")
            if self.state == "disabled":
                super().config(cursor="arrow")
                self.itemconfig(self.img_item, image=self.disabled_img)
                self.itemconfig(self.text_item, fill=MUTED)
            else:
                super().config(cursor="hand2")
                self.itemconfig(self.img_item, image=self.normal_img)
                self.itemconfig(self.text_item, fill=self.fg_color)
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if redraw:
            self.normal_img = self._get_img(self.bg_color)
            self.hover_img = self._get_img(self.hover_bg)
            self.active_img = self._get_img(self.active_bg)
            self.itemconfig(self.img_item, image=self.normal_img)
            self.itemconfig(self.text_item, fill=self.fg_color)
        if kwargs:
            super().config(**kwargs)

    configure = config

    def cget(self, key):
        if key == "text":
            return self.text
        elif key == "bg":
            return self.bg_color
        elif key == "fg":
            return self.fg_color
        elif key == "state":
            return self.state
        return super().cget(key)


class ToolTip:
    """
    Floating glassmorphic tooltip with accent border for mouse-over (i) badges.
    Supports both mouse-over (<Enter>/<Leave>) and touchscreen tap (<Button-1>).
    """
    def __init__(self, widget, title, text, font_family=FONT, enter_cb=None, leave_cb=None):
        self.widget = widget
        self.title = title
        self.text = text
        self.font_family = font_family
        self.enter_cb = enter_cb
        self.leave_cb = leave_cb
        self.tip_window = None

        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)
        self.widget.bind("<Button-1>", self.toggle_tip)

    def show_tip(self, event=None):
        if self.enter_cb:
            self.enter_cb(self.title, self.text)

        if self.tip_window or not self.text:
            return

        try:
            x = self.widget.winfo_rootx() + 26
            y = self.widget.winfo_rooty() - 12
        except Exception:
            return

        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.attributes("-topmost", True)
        except Exception:
            pass

        frame = tk.Frame(
            tw, bg=CARD, highlightbackground=GREEN_ACCENT,
            highlightthickness=1, padx=12, pady=10
        )
        frame.pack()

        tk.Label(
            frame, text=f"ⓘ  {self.title}",
            font=(self.font_family, 10, "bold"),
            fg=GREEN_ACCENT, bg=CARD, anchor="w"
        ).pack(fill="x", pady=(0, 4))

        tk.Label(
            frame, text=self.text,
            font=(self.font_family, 9),
            fg=TEXT, bg=CARD, justify="left", wraplength=280
        ).pack(fill="x")

        tw.wm_geometry(f"+{x}+{y}")

    def hide_tip(self, event=None):
        if self.leave_cb:
            self.leave_cb()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def toggle_tip(self, event=None):
        if self.tip_window:
            self.hide_tip()
        else:
            self.show_tip()


# =============================================================================
# 8. APPLICATION USER INTERFACE
# =============================================================================
class AgriLensApp:
    def __init__(self, root):
        self.root = root
        self.running = True
        self.paused = False
        self.latest_frame = None
        self.captured_frame = None

        cfg = load_kiosk_config()
        self.threshold = float(cfg.get("confidence_threshold", CONFIDENCE_THRESHOLD))
        self.ood_margin = float(cfg.get("ood_margin", OOD_MARGIN_THRESHOLD))
        self.ood_logit = float(cfg.get("ood_logit", OOD_LOGIT_THRESHOLD))
        self.sharpness_min = float(cfg.get("sharpness_min", SHARPNESS_MIN_THRESHOLD))

        self.selected_plant = None
        self.last_probs = None
        self.last_raw_out = None
        self.latency_ms = 0.0

        self.entered_password = ""
        self.camera = Camera(auto_detect=False)
        self.camera.contrast = int(cfg.get("cam_contrast", 100))
        self.camera.brightness = int(cfg.get("cam_brightness", 0))
        self.camera.saturation = int(cfg.get("cam_saturation", 100))
        self.camera.sharpness = int(cfg.get("cam_sharpness", 100))
        self.camera.wb_temp = int(cfg.get("cam_wb_temp", 0))
        self.camera.zoom = int(cfg.get("cam_zoom", 100))
        self.camera.flip_h = bool(cfg.get("cam_flip_h", False))
        self.camera.flip_v = bool(cfg.get("cam_flip_v", False))
        self.camera.auto_exp = bool(cfg.get("cam_auto_exp", True))
        self.camera.auto_wb = bool(cfg.get("cam_auto_wb", True))

        self.classifier = None
        self.plants = ["Apple", "Mango", "Potato", "Tomato"]
        self.crops = []
        self.parsed = []
        self.sliders = {}
        self.slider_badges = {}
        self.cam_sliders = {}
        self.cam_slider_badges = {}

        self._setup_window()
        self._build_top_bar()
        self._build_body()
        self._build_plant_picker()
        self._build_password_screen()
        self._build_admin_panel()
        self._build_camera_panel()

        # Display immediate responsive startup status on canvas
        self.canvas.itemconfig(
            self.msg_txt,
            text="⚡ INITIALIZING AGRILENS AI VISION ENGINE...\nConnecting to camera..."
        )
        self.banner.config(text="STARTING UP — PLEASE WAIT...", bg=GREY_BTN, fg=WHITE)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", self._on_escape_key)
        self.root.bind("<space>", self._on_space_key)
        self.root.bind("<Key>", self._on_key_press)

        # Non-blocking async bootstrap: window paints immediately in <0.1s
        self.root.after(30, self._start_async_bootstrap)

    def _any_overlay_open(self):
        for attr in ("picker", "pwd_screen", "admin", "cam_panel"):
            w = getattr(self, attr, None)
            if w is not None and w.winfo_ismapped():
                return True
        return False

    def _on_escape_key(self, event=None):
        if self._any_overlay_open():
            self.close_overlays()
        else:
            self.close()

    def _on_space_key(self, event=None):
        if not self._any_overlay_open():
            self.handle_capture_or_retake()

    def _on_key_press(self, event=None):
        if hasattr(self, "pwd_screen") and self.pwd_screen.winfo_ismapped() and event is not None:
            ks = getattr(event, "keysym", "")
            ch = getattr(event, "char", "")
            if ks == "BackSpace":
                self._pwd_backspace()
            elif ks in ("Return", "KP_Enter"):
                self._pwd_submit()
            elif ch and len(ch) == 1 and ch.isalnum():
                self._pwd_key_press(ch.upper())

    def _setup_window(self):
        ensure_rpi_autostart()
        # Lock Tkinter font DPI scaling to standard 96 DPI (1.3333) so small 7" physical
        # screen dimensions in EDID never inflate font sizes on Raspberry Pi / Waveshare.
        try:
            self.root.tk.call("tk", "scaling", 96.0 / 72.0)
        except Exception:
            pass
        self.root.title("")
        self.root.configure(bg=BG)
        self.root.attributes("-fullscreen", True)
        self.root.update_idletasks()
        self.root.update()

        sw = self.root.winfo_width()
        sh = self.root.winfo_height()
        if sw < 400 or sh < 300:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()

        # On Raspberry Pi + Waveshare 7" (1024x600 native, 1920x1080 max EDID),
        # clamp to 1024x600 so early-boot 1920x1080 EDID never enlarges the UI.
        if platform.system() == "Linux" and (sw > 1024 or sh > 600):
            sw, sh = 1024, 600

        self.W = sw if sw > 0 else 1024
        self.H = sh if sh > 0 else 600
        self.root.geometry(f"{self.W}x{self.H}+0+0")
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.focus_force()
            if platform.system() == "Windows":
                import ctypes
                self.root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.ShowWindow(hwnd, 5)  # SW_SHOW
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            self.root.after(400, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass
        self.root.after(100, lambda: self.root.attributes("-fullscreen", True))

        self.S = min(self.W / 1024, self.H / 600)
        self.TOP_H = self.px(48)

    def px(self, val):
        return max(1, round(val * self.S))

    def f(self, size, bold=False):
        return (FONT, max(8, round(size * self.S)), "bold" if bold else "normal")

    def _button(self, parent, text, bg, cmd, width=None, height=None, size=11, fg=None, radius=None, border=None, parent_bg=None):
        if fg is None:
            fg = DARK if bg in (WHITE, GREEN_ACCENT, GREEN_GLOW) else WHITE
        if height is None:
            height = self.px(38)
        if parent_bg is None:
            try:
                parent_bg = parent.cget("bg")
            except Exception:
                parent_bg = PANEL

        return RoundedButton(
            parent, text=text, command=cmd,
            bg_color=bg, fg_color=fg,
            width=width, height=height, radius=radius,
            font=self.f(size, True),
            border_color=border,
            parent_bg=parent_bg
        )

    # ---- 1. Top Bar with Brand, Crop Filter, Admin & Gundecha Academy Logo ----
    def _build_school_logo(self, parent):
        px = self.px
        logo_path = find_file(os.path.join("assets", "gundecha_logo.png"))
        if not os.path.exists(logo_path):
            logo_path = find_file("gundecha_logo.png")

        if os.path.exists(logo_path):
            try:
                raw_logo = Image.open(logo_path)
                lh = px(38)
                aspect = raw_logo.width / max(1, raw_logo.height)
                lw = max(1, int(lh * aspect))
                resized = raw_logo.resize((lw, lh), RESAMPLE)

                pad_x, pad_y = px(4), px(2)
                bw, bh = lw + 2 * pad_x, lh + 2 * pad_y
                scale = 2
                badge_im = Image.new("RGBA", (bw * scale, bh * scale), (0, 0, 0, 0))
                d = ImageDraw.Draw(badge_im)
                d.rounded_rectangle(
                    [0, 0, bw * scale - 1, bh * scale - 1],
                    radius=px(10) * scale,
                    fill=(255, 255, 255, 245),
                    outline=(210, 220, 215, 255),
                    width=scale
                )
                badge_im = badge_im.resize((bw, bh), RESAMPLE)
                badge_im.paste(resized, (pad_x, pad_y), resized)

                self._school_logo_photo = ImageTk.PhotoImage(badge_im)
                logo_lbl = tk.Label(
                    parent, image=self._school_logo_photo, bg=PANEL, cursor="hand2", bd=0
                )
                logo_lbl.pack(side="right", padx=(px(4), px(12)), pady=px(5))
                logo_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://www.gundechaedu.org/"))
                ToolTip(logo_lbl, "Gundecha Education Academy", "Official Partner Institution\nClick to open official portal: gundechaedu.org", font_family=FONT)
                return
            except Exception as e:
                print("Notice: logo load error:", e)

        school_box = tk.Frame(parent, bg=WHITE, padx=px(6), pady=px(2))
        school_box.pack(side="right", padx=(px(4), px(12)), pady=px(8))
        tk.Label(school_box, text="GEA", font=self.f(11, True), fg=DARK, bg=WHITE).pack()

    def _build_top_bar(self):
        px = self.px
        top = tk.Frame(self.root, bg=PANEL, height=self.TOP_H)
        top.pack(side="top", fill="x")
        top.pack_propagate(False)

        # Crop Filter Button (Auto - Beta)
        self.plant_btn = self._button(
            top, "SELECT CROP (AUTO)", CARD, self.open_plant_picker,
            height=px(38), size=10, fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.plant_btn.pack(side="left", padx=(px(10), px(6)), pady=px(7))

        # Header Title
        title_box = tk.Frame(top, bg=PANEL)
        title_box.pack(side="left", padx=px(10), fill="y")
        lbl_brand = tk.Label(title_box, text="AGRILENS", font=self.f(15, True), fg=WHITE, bg=PANEL, cursor="hand2")
        lbl_brand.pack(anchor="w")
        ToolTip(lbl_brand, "AGRILENS Edge Vision Kiosk", f"Version: v{APP_VERSION}\nBuild: {BUILD_TIMESTAMP}\nModel: MobileNetV4 ONNX (24 Classes)", font_family=FONT)
        tk.Label(title_box, text="AI Agricultural Health Diagnostics", font=self.f(8, True), fg=GREEN_ACCENT, bg=PANEL).pack(anchor="w")

        # Far Right: Official Gundecha Education Academy Logo
        self._build_school_logo(top)

        # ADMIN BUTTON (Right beside the school badge)
        self.admin_btn = self._button(
            top, "ADMIN", CARD, self.open_password_screen,
            width=px(88), height=px(38), size=10, fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.admin_btn.pack(side="right", padx=(px(4), px(8)), pady=px(7))

    # ---- 2. Split Screen Body ----
    def _build_body(self):
        px = self.px
        pad = px(6)
        body_h = self.H - self.TOP_H

        body = tk.Frame(self.root, bg=BG, width=self.W, height=body_h)
        body.pack(side="top", fill="both", expand=True)
        body.pack_propagate(False)

        # Allocate 56.5% width to the Camera Panel so the full 4:3 (640x480) FoV displays large & uncropped on 1024x600
        left_w = int(self.W * 0.565)
        right_w = self.W - left_w

        # LEFT SIDE - Full-FoV Camera Window + Quality AI Bar + Action Buttons
        left = tk.Frame(body, bg=BG, width=left_w, height=body_h)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        self.CAM_W = left_w - 2 * pad - 4
        half_btn_w = self.CAM_W // 2 - px(5)
        btn_h = px(42)

        # 1. BOTTOM: SEPARATE ACTION BUTTONS BAR ([CAPTURE LEAF / PICK FROM FILE] and [DIAGNOSE LEAF])
        btn_box = tk.Frame(left, bg=BG)
        btn_box.pack(side="bottom", fill="x", padx=pad + 2, pady=(0, pad))

        # Button 1: CAPTURE (swaps to RETAKE when frozen, or PICK FROM FILE when no camera)
        self.capture_btn = self._button(
            btn_box, "CAPTURE LEAF", GREEN_PRIMARY, self.handle_capture_or_retake,
            width=half_btn_w, height=btn_h, size=11, fg=WHITE, radius=px(21), parent_bg=BG
        )
        self.capture_btn.pack(side="left", padx=(0, px(4)))

        # Button 2: DIAGNOSE (Runs AI Inference)
        self.diagnose_btn = self._button(
            btn_box, "DIAGNOSE LEAF", CARD, self.handle_diagnose,
            width=half_btn_w, height=btn_h, size=11, fg=WHITE, border=BORDER, radius=px(21), parent_bg=BG
        )
        self.diagnose_btn.pack(side="right", padx=(px(4), 0))

        # 2. DIRECTLY ABOVE BUTTONS: IMAGE QUALITY AI STATUS BAR
        quality_frame = tk.Frame(left, bg=PANEL, padx=px(6), pady=px(3))
        quality_frame.pack(side="bottom", fill="x", padx=pad + 2, pady=(0, px(4)))

        self.quality_lbl = tk.Label(
            quality_frame, text="Leaf Quality AI: Align leaf inside box",
            font=self.f(9, True), fg=MUTED, bg=PANEL, anchor="center",
            wraplength=self.CAM_W - px(12)
        )
        self.quality_lbl.pack(fill="x")

        # 3. LARGE 4:3 FULL-FOV CAMERA OUTPUT DISPLAY (Matches 640x480 webcam aspect ratio so 100% FoV is visible)
        avail_cam_h = max(px(240), body_h - btn_h - px(46))
        fov_4_3_h = int(round(self.CAM_W * 3 / 4))
        self.CAM_H = min(avail_cam_h, fov_4_3_h)

        self.cam_border = tk.Frame(left, bg=CARD, padx=2, pady=2)
        self.cam_border.pack(side="top", pady=(pad, px(3)), expand=True)

        # Clean Camera Canvas with subtle targeting frame
        self.canvas = tk.Canvas(self.cam_border, width=self.CAM_W, height=self.CAM_H,
                                bg="#050a07", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.handle_capture_or_retake())

        cw, ch = self.CAM_W, self.CAM_H
        self.img_item = self.canvas.create_image(cw // 2, ch // 2, anchor="center")

        # Leaf Alignment Targeting Box - Covers complete Full-FoV image area
        margin = px(3)
        self.guide = self.canvas.create_rectangle(
            margin, margin, cw - margin, ch - margin,
            outline=GREEN_ACCENT, width=px(2), dash=(8, 5)
        )

        # Live webcam / File Mode indicator overlay (left-aligned so longer labels never clip)
        self.live_badge = self.canvas.create_text(
            px(10), px(8), anchor="nw", fill=GREEN_ACCENT, font=self.f(9, True),
            text="LIVE WEBCAM"
        )

        self.msg_txt = self.canvas.create_text(
            cw // 2, ch // 2, fill=MUTED, font=self.f(11),
            justify="center", text="Connecting to webcam..."
        )

        # RIGHT SIDE - Farmer Diagnosis & Recommendations (Arranged cleanly for 7" 1024x600 screen)
        right = tk.Frame(body, bg=PANEL, width=right_w - pad, height=body_h - 2 * pad)
        right.pack(side="left", fill="both", expand=True, padx=(0, pad), pady=pad)
        right.pack_propagate(False)
        rp = px(10)
        wrap = right_w - pad - 2 * rp - px(6)

        self.banner_frame = tk.Frame(right, bg=GREY_BTN, padx=px(8), pady=px(5))
        self.banner_frame.pack(fill="x")

        self.banner = tk.Label(
            self.banner_frame, text="READY — AIM LEAF AT CAMERA", font=self.f(12, True),
            bg=GREY_BTN, fg=WHITE, pady=px(2), wraplength=wrap
        )
        self.banner.pack(fill="x")

        info = tk.Frame(right, bg=PANEL)
        info.pack(fill="x", padx=rp, pady=(px(6), 0))

        self.plant_lbl = tk.Label(info, text="Mode: Auto-Detect (Beta Production)", font=self.f(10, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w")
        self.plant_lbl.pack(fill="x")

        self.disease_lbl = tk.Label(
            info, text="Aim leaf inside box -> Tap CAPTURE -> Tap DIAGNOSE",
            font=self.f(12, True), fg=WHITE, bg=PANEL, anchor="w",
            justify="left", wraplength=wrap
        )
        self.disease_lbl.pack(fill="x")

        # Confidence Bar
        self.BAR_W, self.BAR_H = wrap, px(18)
        self.bar = tk.Canvas(info, width=self.BAR_W, height=self.BAR_H, bg=CARD, highlightthickness=0)
        self.bar.pack(anchor="w", pady=(px(5), 0))

        tk.Frame(right, bg=BORDER, height=max(1, px(1))).pack(fill="x", padx=rp, pady=(px(7), px(4)))

        tk.Label(
            right, text="RECOMMENDED FARMER ACTIONS", font=self.f(10, True),
            fg=WHITE, bg=PANEL, anchor="w"
        ).pack(fill="x", padx=rp, pady=(0, px(4)))

        # Bottom Hardware / Latency Strip
        self.stats_lbl = tk.Label(
            right, text=f"v{APP_VERSION}", font=self.f(8), fg=MUTED, bg=PANEL,
            anchor="w", justify="left", wraplength=wrap
        )
        self.stats_lbl.pack(side="bottom", fill="x", padx=rp, pady=(0, px(4)))

        tk.Label(
            right, text=DISCLAIMER, font=self.f(8), fg=MUTED, bg=PANEL,
            anchor="w", justify="left", wraplength=wrap
        ).pack(side="bottom", fill="x", padx=rp)

        # Numbered recommendation rows
        steps_box = tk.Frame(right, bg=PANEL)
        steps_box.pack(fill="both", expand=True, padx=rp)

        self.step_rows = []
        for i in range(4):
            row = tk.Frame(steps_box, bg=PANEL)
            num = tk.Label(
                row, text=str(i + 1), font=self.f(9, True),
                bg=GREEN_PRIMARY, fg=WHITE, width=2
            )
            num.pack(side="left", anchor="n", padx=(0, px(7)), pady=(px(1), 0))
            txt = tk.Label(
                row, text="", font=self.f(9), fg=WHITE, bg=PANEL,
                anchor="w", justify="left", wraplength=wrap - px(32)
            )
            txt.pack(side="left", fill="x", expand=True)
            self.step_rows.append((row, num, txt))

        self._draw_bar(0, GREY_BTN, "")

    # ---- 3. Plant Picker Dialog ----
    def _build_plant_picker(self):
        px = self.px
        self.picker = tk.Frame(self.root, bg=BG)
        tk.Label(self.picker, text="SELECT CROP TO DIAGNOSE", font=self.f(20, True), fg=WHITE, bg=BG).pack(pady=(px(24), px(4)))
        tk.Label(self.picker, text="Auto-detection mode automatically identifies all supported plant species",
                 font=self.f(10), fg=MUTED, bg=BG).pack()

        self.picker_grid = tk.Frame(self.picker, bg=BG)
        self.picker_grid.pack(expand=True)

        self._button(self.picker, "REVERT TO SCANNER", GREY_BTN, self.close_overlays, width=px(210), height=px(52), size=11, radius=px(16), fg=WHITE, parent_bg=BG).pack(pady=(0, px(22)))

    def _fill_plant_picker(self):
        for w in self.picker_grid.winfo_children():
            w.destroy()
        options = [("ALL PLANTS (AUTO - BETA)", None)] + [(p.upper(), p) for p in self.plants]
        cols = 3 if len(options) > 4 else 2
        for i, (text, value) in enumerate(options):
            color = GREEN_PRIMARY if value == self.selected_plant else CARD
            border = GREEN_ACCENT if value == self.selected_plant else BORDER
            b = self._button(
                self.picker_grid, text, color,
                lambda v=value: self.select_plant(v),
                width=self.px(220), height=self.px(58), size=11, fg=WHITE,
                border=border, radius=self.px(16), parent_bg=BG
            )
            b.grid(row=i // cols, column=i % cols, padx=self.px(10), pady=self.px(10))

    def open_plant_picker(self):
        self._fill_plant_picker()
        self.picker.place(x=0, y=0, relwidth=1, relheight=1)
        self.picker.lift()

    def select_plant(self, plant):
        self.selected_plant = plant
        if plant is None:
            self.plant_btn.config(text="SELECT CROP (AUTO)")
        else:
            self.plant_btn.config(text=f"CROP: {plant.upper()}")

        if self.paused and self.last_probs:
            self._render_diagnosis(self.last_probs, self.last_raw_out)
        elif not self.paused:
            self._reset_panel()
        self.close_overlays()

    # ---- 4. Security Lock & Touch Keyboard ----
    def _build_password_screen(self):
        px = self.px
        self.pwd_screen = tk.Frame(self.root, bg=BG)

        head = tk.Frame(self.pwd_screen, bg=PANEL, height=self.TOP_H)
        head.pack(side="top", fill="x")
        head.pack_propagate(False)

        tk.Label(head, text="ADMIN SECURITY LOCK", font=self.f(16, True), fg=WHITE, bg=PANEL).pack(side="left", padx=px(16))
        self._button(head, "REVERT", GREY_BTN, self.close_overlays, width=px(96), height=px(38), size=10, radius=px(10), fg=WHITE, parent_bg=PANEL).pack(side="right", padx=px(10), pady=px(6))

        # Centered container so the keyboard & display box have clean, un-stretched proportions
        center_wrap = tk.Frame(self.pwd_screen, bg=BG)
        center_wrap.pack(expand=True)

        disp_box = tk.Frame(center_wrap, bg=PANEL, padx=px(18), pady=px(10), highlightbackground=BORDER, highlightthickness=1)
        disp_box.pack(pady=(px(6), px(12)))

        self.pwd_display_lbl = tk.Label(
            disp_box, text="", font=(FONT, max(16, round(22 * self.S)), "bold"),
            fg=WHITE, bg=CARD, width=14, pady=px(6), relief="flat", bd=0
        )
        self.pwd_display_lbl.pack(pady=(0, px(6)))

        self.pwd_status_lbl = tk.Label(
            disp_box, text="ENTER SYSTEM PASSWORD", font=self.f(10, True), fg=MUTED, bg=PANEL
        )
        self.pwd_status_lbl.pack()

        # Large Square-Proportioned Touch Keyboard (Un-stretched, Easy Finger Tap)
        kb_frame = tk.Frame(center_wrap, bg=BG)
        kb_frame.pack(pady=(0, px(6)))

        rows = [
            ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
            ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
            ["CLEAR", "Z", "X", "C", "V", "B", "N", "M", "BACKSPACE"],
            ["ENTER"]
        ]

        key_w = px(72)
        key_h = px(66)
        action_w = px(108)

        for row in rows:
            r_frame = tk.Frame(kb_frame, bg=BG)
            r_frame.pack(pady=px(5))
            for key in row:
                if key == "ENTER":
                    btn = self._button(
                        r_frame, "✓  ENTER PASSWORD", GREEN_PRIMARY, self._pwd_submit,
                        width=px(240), height=px(62), size=14, fg=WHITE, radius=px(16), parent_bg=BG
                    )
                elif key == "CLEAR":
                    btn = self._button(
                        r_frame, "CLEAR", RED_ALERT, self._pwd_clear,
                        width=action_w, height=key_h, size=12, fg=WHITE, radius=px(14), parent_bg=BG
                    )
                elif key == "BACKSPACE":
                    btn = self._button(
                        r_frame, "⌫ BACK", GREY_BTN, self._pwd_backspace,
                        width=action_w, height=key_h, size=12, fg=WHITE, radius=px(14), parent_bg=BG
                    )
                else:
                    btn = self._button(
                        r_frame, key, CARD, lambda k=key: self._pwd_key_press(k),
                        width=key_w, height=key_h, size=16, fg=WHITE, radius=px(14), border=BORDER, parent_bg=BG
                    )
                btn.pack(side="left", padx=px(4))

    def open_password_screen(self):
        self.entered_password = ""
        self._update_pwd_display()
        self.pwd_status_lbl.config(text="ENTER SYSTEM PASSWORD", fg=MUTED)
        self.pwd_screen.place(x=0, y=0, relwidth=1, relheight=1)
        self.pwd_screen.lift()

    def _pwd_key_press(self, key):
        if len(self.entered_password) < 16:
            self.entered_password += key.upper()
            self._update_pwd_display()

    def _pwd_backspace(self):
        self.entered_password = self.entered_password[:-1]
        self._update_pwd_display()

    def _pwd_clear(self):
        self.entered_password = ""
        self._update_pwd_display()

    def _update_pwd_display(self):
        self.pwd_display_lbl.config(text=self.entered_password if self.entered_password else "--------")

    def _pwd_submit(self):
        if self.entered_password == ADMIN_PASSWORD:
            self.pwd_screen.place_forget()
            self.open_admin_panel()
        else:
            self.pwd_status_lbl.config(text="INCORRECT PASSWORD! TRY AGAIN", fg=RED_ALERT)
            self.entered_password = ""
            self._update_pwd_display()

    # ---- 5. Admin Panel (AI Diagnostics Parameters & Hardware Controls) ----
    def _build_admin_panel(self):
        px = self.px
        self.admin = tk.Frame(self.root, bg=BG)

        head = tk.Frame(self.admin, bg=PANEL, height=self.TOP_H)
        head.pack(side="top", fill="x")
        head.pack_propagate(False)

        tk.Label(head, text="ADMIN CONSOLE & AI PARAMETERS", font=self.f(16, True), fg=WHITE, bg=PANEL).pack(side="left", padx=px(16))
        self._button(head, "REVERT", GREY_BTN, self.close_overlays, width=px(96), height=px(38), size=10, radius=px(10), fg=WHITE, parent_bg=PANEL).pack(side="right", padx=px(10), pady=px(6))

        # Balanced Split Screen Container (53% Left / 47% Right so neither side looks stretched)
        pad_x = px(14)
        pad_y = px(12)
        body_w = self.W - 2 * pad_x
        body_h = self.H - self.TOP_H - 2 * pad_y

        body = tk.Frame(self.admin, bg=BG, width=body_w, height=body_h)
        body.pack(side="top", fill="both", expand=True, padx=pad_x, pady=pad_y)
        body.pack_propagate(False)

        left_w = int(body_w * 0.53)
        right_w = body_w - left_w - px(12)

        # LEFT CARD: AI Diagnostic Sliders & Guidelines (Proportional 53% width)
        card_ai = tk.Frame(body, bg=PANEL, padx=px(16), pady=px(12), width=left_w, height=body_h)
        card_ai.pack(side="left", fill="y", expand=False)
        card_ai.pack_propagate(False)

        tk.Label(card_ai, text="AI DIAGNOSTIC PARAMETERS", font=self.f(12, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_ai, text="Fine-tune confidence, out-of-scope gating & focus thresholds", font=self.f(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(6)))
        tk.Frame(card_ai, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(10)))

        # Bottom Guide Card & Reset Button anchored neatly at bottom of card_ai
        self.guide_card = tk.Frame(card_ai, bg=CARD, padx=px(10), pady=px(8), height=px(86), highlightbackground=BORDER, highlightthickness=1)
        self.guide_card.pack(side="bottom", fill="x", pady=(px(6), 0))
        self.guide_card.pack_propagate(False)

        self.guide_title_lbl = tk.Label(
            self.guide_card, text="ⓘ  PARAMETER GUIDE",
            font=self.f(9, True), fg=GREEN_ACCENT, bg=CARD, anchor="w"
        )
        self.guide_title_lbl.pack(fill="x")

        self.guide_desc_lbl = tk.Label(
            self.guide_card,
            text="Hover or tap any ⓘ icon to view the meaning and impact of each setting.",
            font=self.f(8), fg=MUTED, bg=CARD, justify="left", anchor="w",
            wraplength=left_w - px(56)
        )
        self.guide_desc_lbl.pack(fill="x", pady=(px(3), 0))

        btn_row = tk.Frame(card_ai, bg=PANEL)
        btn_row.pack(side="bottom", fill="x", pady=(px(4), px(4)))
        self._button(
            btn_row, "↺ RESET DEFAULTS", CARD, self._reset_slider_defaults,
            width=px(176), height=px(42), size=10, radius=px(12), fg=GREEN_ACCENT, border=BORDER, parent_bg=PANEL
        ).pack(side="left")

        self.sliders = {}
        self.slider_badges = {}

        slider_specs = [
            {
                "key": "confidence_threshold",
                "name": "Confidence Threshold",
                "min": 30, "max": 95, "step": 1,
                "get_initial": lambda: int(round(self.threshold * 100)),
                "format": lambda v: f"{int(v)}%",
                "to_param": lambda v: float(v) / 100.0,
                "attr": "threshold",
                "info_title": "Confidence Acceptance Threshold",
                "info_text": "Minimum model certainty required to accept a diagnosis. Lower values allow diagnoses in difficult lighting; higher values trigger 'NOT SURE' to avoid false alarms."
            },
            {
                "key": "ood_margin",
                "name": "OOD Ambiguity Margin",
                "min": 10, "max": 60, "step": 1,
                "get_initial": lambda: int(round(self.ood_margin * 100)),
                "format": lambda v: f"{int(v)}%",
                "to_param": lambda v: float(v) / 100.0,
                "attr": "ood_margin",
                "info_title": "Out-of-Scope Ambiguity Gap",
                "info_text": "Minimum probability lead of the #1 diagnosis over the #2 runner-up. If the model is torn between two classes, this margin rejects the specimen as an ambiguous or unknown plant."
            },
            {
                "key": "ood_logit",
                "name": "Neural Logit Energy Gate",
                "min": 10, "max": 65, "step": 1,
                "get_initial": lambda: int(round(self.ood_logit * 10)),
                "format": lambda v: f"{float(v) / 10.0:.2f}",
                "to_param": lambda v: round(float(v) / 10.0, 2),
                "attr": "ood_logit",
                "info_title": "Neural Logit Energy Gate",
                "info_text": "Raw unnormalized neural activation filter. Real leaves from trained species generate strong logit spikes (>2.4). Uncataloged leaves (e.g. money plants) produce low logits and are safely rejected."
            },
            {
                "key": "sharpness_min",
                "name": "Sharpness Quality Gate",
                "min": 20, "max": 120, "step": 5,
                "get_initial": lambda: int(round(self.sharpness_min)),
                "format": lambda v: f"{int(v)}",
                "to_param": lambda v: float(v),
                "attr": "sharpness_min",
                "info_title": "Sharpness & Focus Quality Gate",
                "info_text": "Spatial Laplacian variance threshold for motion blur detection. Lower settings allow softer webcams to pass; higher settings enforce crisp focus before permitting diagnosis."
            },
        ]

        for spec in slider_specs:
            row = tk.Frame(card_ai, bg=PANEL)
            row.pack(fill="x", padx=px(4), pady=(0, px(8)))

            hdr = tk.Frame(row, bg=PANEL)
            hdr.pack(fill="x", pady=(0, px(2)))

            tk.Label(hdr, text=spec["name"], font=self.f(10, True), fg=WHITE, bg=PANEL).pack(side="left")

            i_btn = tk.Label(
                hdr, text=" ⓘ ", font=self.f(9, True),
                fg=GREEN_ACCENT, bg=CARD, cursor="hand2", padx=px(3), pady=0
            )
            i_btn.pack(side="left", padx=px(6))

            init_val = spec["get_initial"]()
            val_lbl = tk.Label(
                hdr, text=spec["format"](init_val), font=self.f(10, True),
                fg=GREEN_ACCENT, bg=CARD, padx=px(8), pady=px(2)
            )
            val_lbl.pack(side="right")
            self.slider_badges[spec["key"]] = (val_lbl, spec["format"])

            ToolTip(
                i_btn,
                spec["info_title"],
                spec["info_text"],
                font_family=FONT,
                enter_cb=lambda t=spec["info_title"], d=spec["info_text"]: self._update_inline_guide(t, d),
                leave_cb=self._revert_inline_guide
            )

            slider = tk.Scale(
                row,
                from_=spec["min"],
                to=spec["max"],
                resolution=spec["step"],
                orient="horizontal",
                showvalue=False,
                width=px(18),
                sliderlength=px(34),
                bg=PANEL,
                troughcolor=BG,
                activebackground=GREEN_ACCENT,
                highlightthickness=0,
                bd=0,
                cursor="hand2"
            )
            slider.set(init_val)
            slider.pack(fill="x")
            self.sliders[spec["key"]] = (slider, spec)

        # Flush pending initial slider set() events before attaching command callbacks
        self.root.update_idletasks()
        for key, (slider, spec) in self.sliders.items():
            slider.config(command=lambda val, s=spec: self._on_slider_change(s, val))

        # RIGHT CARD: Hardware & System (Balanced 47% width)
        card_sys = tk.Frame(body, bg=PANEL, padx=px(18), pady=px(12), width=right_w, height=body_h)
        card_sys.pack(side="right", fill="y", expand=False)
        card_sys.pack_propagate(False)

        tk.Label(card_sys, text="HARDWARE & SYSTEM", font=self.f(12, True), fg=WHITE, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_sys, text="Peripherals & application runtime", font=self.f(9), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(6)))
        tk.Frame(card_sys, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(12)))

        # Bottom-anchored CLOSE APPLICATION section so card_sys distributes cleanly
        exit_box = tk.Frame(card_sys, bg=PANEL)
        exit_box.pack(side="bottom", fill="x", pady=(px(4), px(4)))

        tk.Frame(exit_box, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(12)))

        self.exit_btn = self._button(
            exit_box, "✕ CLOSE APPLICATION", RED_ALERT, self.close,
            width=px(220), height=px(52), size=11, radius=px(14), fg=WHITE, parent_bg=PANEL
        )
        self.exit_btn.pack(pady=(0, px(6)))

        tk.Label(
            exit_box, text="Safely exit the kiosk and return to desktop",
            font=self.f(9), fg=MUTED, bg=PANEL
        ).pack()

        # Upper/Middle sections: Camera Status + Detect Webcam + GitHub Repo
        cam_box = tk.Frame(card_sys, bg=CARD, padx=px(12), pady=px(10), highlightbackground=BORDER, highlightthickness=1)
        cam_box.pack(fill="x", pady=(0, px(12)))

        self.webcam_status_lbl = tk.Label(
            cam_box, text="Checking camera...", font=self.f(10, True), fg=MUTED, bg=CARD, justify="center", wraplength=right_w - px(64)
        )
        self.webcam_status_lbl.pack(pady=(0, px(8)))

        self.detect_btn = self._button(
            cam_box, "🔍 DETECT WEBCAM", GREEN_PRIMARY, self._trigger_detect_webcam,
            width=px(220), height=px(50), size=11, radius=px(14), fg=WHITE, parent_bg=CARD
        )
        self.detect_btn.pack(pady=(0, px(6)))

        self.detect_msg_lbl = tk.Label(
            cam_box, text="Click to scan and connect USB webcam", font=self.f(8), fg=MUTED, bg=CARD, justify="center", wraplength=right_w - px(64)
        )
        self.detect_msg_lbl.pack()

        # CAMERA CONTROL PANEL TAB BUTTON (Replaced GitHub Repo button)
        cam_tab_box = tk.Frame(card_sys, bg=PANEL)
        cam_tab_box.pack(fill="x", pady=(px(4), 0))

        self.cam_ctrl_btn = self._button(
            cam_tab_box, "📷 CAMERA CONTROL PANEL", CARD, self.open_camera_panel,
            width=px(240), height=px(52), size=10, radius=px(14), fg=GREEN_ACCENT, border=GREEN_ACCENT, parent_bg=PANEL
        )
        self.cam_ctrl_btn.pack(pady=(0, px(6)))
        tk.Label(
            cam_tab_box, text=f"Camera Tuning & Focus Calibration\nAGRILENS v{APP_VERSION}",
            font=self.f(8), fg=MUTED, bg=PANEL, justify="center"
        ).pack()

    # ---- 5B. Camera Control Panel Tab ----
    def _build_camera_panel(self):
        px = self.px
        self.cam_panel = tk.Frame(self.root, bg=BG)

        head = tk.Frame(self.cam_panel, bg=PANEL, height=self.TOP_H)
        head.pack(side="top", fill="x")
        head.pack_propagate(False)

        tk.Label(
            head, text="CAMERA CONTROL PANEL",
            font=self.f(15, True), fg=WHITE, bg=PANEL
        ).pack(side="left", padx=px(16))

        self._button(
            head, "REVERT", GREY_BTN, self.close_overlays,
            width=px(96), height=px(38), size=10, radius=px(10), fg=WHITE, parent_bg=PANEL
        ).pack(side="right", padx=(px(4), px(10)), pady=px(6))

        self._button(
            head, "← ADMIN PANEL", CARD, self._back_to_admin_from_camera,
            width=px(136), height=px(38), size=10, radius=px(10), fg=GREEN_ACCENT, border=BORDER, parent_bg=PANEL
        ).pack(side="right", padx=px(4), pady=px(6))

        pad_x = px(14)
        pad_y = px(10)
        body_w = self.W - 2 * pad_x
        body_h = self.H - self.TOP_H - 2 * pad_y

        body = tk.Frame(self.cam_panel, bg=BG, width=body_w, height=body_h)
        body.pack(side="top", fill="both", expand=True, padx=pad_x, pady=pad_y)
        body.pack_propagate(False)

        left_w = int(body_w * 0.47)
        right_w = body_w - left_w - px(12)

        # LEFT CARD: Live Preview + Focus Calibration Meter + Orientation Toggles
        card_prev = tk.Frame(body, bg=PANEL, padx=px(14), pady=px(10), width=left_w, height=body_h)
        card_prev.pack(side="left", fill="y", expand=False)
        card_prev.pack_propagate(False)

        tk.Label(card_prev, text="LIVE FEED & FOCUS HELPER", font=self.f(11, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_prev, text="Adjust focus until the Focus Sharpness Bar peaks in green", font=self.f(8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(6)))

        # Bottom 2x2 Quick Action Toggle Grid
        toggles_box = tk.Frame(card_prev, bg=PANEL)
        toggles_box.pack(side="bottom", fill="x", pady=(px(4), 0))

        half_tw = (left_w - px(38)) // 2
        row_t1 = tk.Frame(toggles_box, bg=PANEL)
        row_t1.pack(fill="x", pady=(0, px(6)))

        self.peaking_btn = self._button(
            row_t1, "PEAKING: OFF", CARD, self._toggle_focus_peaking,
            width=half_tw, height=px(40), size=9, radius=px(12), fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.peaking_btn.pack(side="left")

        self.flip_h_btn = self._button(
            row_t1, "MIRROR H: OFF", CARD, self._toggle_flip_h,
            width=half_tw, height=px(40), size=9, radius=px(12), fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.flip_h_btn.pack(side="right")

        row_t2 = tk.Frame(toggles_box, bg=PANEL)
        row_t2.pack(fill="x")

        self.flip_v_btn = self._button(
            row_t2, "FLIP 180°: OFF", CARD, self._toggle_flip_v,
            width=half_tw, height=px(40), size=9, radius=px(12), fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.flip_v_btn.pack(side="left")

        self.reset_cam_btn = self._button(
            row_t2, "↺ RESET CAMERA", CARD, self._reset_camera_defaults,
            width=half_tw, height=px(40), size=9, radius=px(12), fg=GREEN_ACCENT, border=BORDER, parent_bg=PANEL
        )
        self.reset_cam_btn.pack(side="right")

        # Manual Focus Sharpness Meter Bar (directly above toggles)
        focus_box = tk.Frame(card_prev, bg=CARD, padx=px(8), pady=px(6), highlightbackground=BORDER, highlightthickness=1)
        focus_box.pack(side="bottom", fill="x", pady=(px(4), px(6)))

        self.focus_lbl = tk.Label(
            focus_box, text="Focus Sharpness: --%",
            font=self.f(9, True), fg=WHITE, bg=CARD, anchor="w"
        )
        self.focus_lbl.pack(fill="x", pady=(0, px(3)))

        self.FOCUS_BAR_W = left_w - px(48)
        self.FOCUS_BAR_H = px(14)
        self.focus_bar = tk.Canvas(
            focus_box, width=self.FOCUS_BAR_W, height=self.FOCUS_BAR_H,
            bg=BG, highlightthickness=0
        )
        self.focus_bar.pack(anchor="w")

        # Live Camera Preview Canvas (fills remaining upper space of card_prev)
        self.CAM_CTRL_W = left_w - px(32)
        self.CAM_CTRL_H = max(px(160), body_h - px(215))

        prev_border = tk.Frame(card_prev, bg=CARD, padx=2, pady=2)
        prev_border.pack(side="top", expand=True)

        self.cam_ctrl_canvas = tk.Canvas(
            prev_border, width=self.CAM_CTRL_W, height=self.CAM_CTRL_H,
            bg="#000000", highlightthickness=0
        )
        self.cam_ctrl_canvas.pack()
        self.cam_ctrl_img_item = self.cam_ctrl_canvas.create_image(
            self.CAM_CTRL_W // 2, self.CAM_CTRL_H // 2, anchor="center"
        )
        self.cam_ctrl_msg = self.cam_ctrl_canvas.create_text(
            self.CAM_CTRL_W // 2, self.CAM_CTRL_H // 2,
            fill=MUTED, font=self.f(10), justify="center",
            text="Live Camera Preview"
        )

        # RIGHT CARD: 6 Camera Sliders + Hardware Toggles
        card_ctrl = tk.Frame(body, bg=PANEL, padx=px(16), pady=px(10), width=right_w, height=body_h)
        card_ctrl.pack(side="right", fill="y", expand=False)
        card_ctrl.pack_propagate(False)

        tk.Label(card_ctrl, text="CAMERA & IMAGE CONTROLS", font=self.f(11, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_ctrl, text="Real-time contrast, lighting, white balance & macro zoom", font=self.f(8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(4)))
        tk.Frame(card_ctrl, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(6)))

        # Bottom USB Hardware Mode Toggles (Auto-Exposure & Auto White Balance)
        usb_hw_box = tk.Frame(card_ctrl, bg=PANEL)
        usb_hw_box.pack(side="bottom", fill="x", pady=(px(4), 0))

        half_uw = (right_w - px(42)) // 2
        self.auto_exp_btn = self._button(
            usb_hw_box, "USB AUTO-EXP: ON", GREEN_PRIMARY, self._toggle_auto_exp,
            width=half_uw, height=px(40), size=9, radius=px(12), fg=WHITE, parent_bg=PANEL
        )
        self.auto_exp_btn.pack(side="left")

        self.auto_wb_btn = self._button(
            usb_hw_box, "USB AUTO-WB: ON", GREEN_PRIMARY, self._toggle_auto_wb,
            width=half_uw, height=px(40), size=9, radius=px(12), fg=WHITE, parent_bg=PANEL
        )
        self.auto_wb_btn.pack(side="right")

        self.cam_sliders = {}
        self.cam_slider_badges = {}

        cam_specs = [
            {
                "key": "cam_contrast",
                "name": "Contrast Control",
                "min": 50, "max": 200, "step": 2,
                "get_initial": lambda: int(self.camera.contrast),
                "format": lambda v: f"{int(v)}%",
                "attr": "contrast",
                "hw": False
            },
            {
                "key": "cam_brightness",
                "name": "Brightness Offset",
                "min": -50, "max": 50, "step": 2,
                "get_initial": lambda: int(self.camera.brightness),
                "format": lambda v: f"{int(v):+d}%",
                "attr": "brightness",
                "hw": False
            },
            {
                "key": "cam_saturation",
                "name": "Color Saturation",
                "min": 0, "max": 200, "step": 5,
                "get_initial": lambda: int(self.camera.saturation),
                "format": lambda v: f"{int(v)}%",
                "attr": "saturation",
                "hw": False
            },
            {
                "key": "cam_sharpness",
                "name": "Sharpness & Vein Crisping",
                "min": 50, "max": 250, "step": 5,
                "get_initial": lambda: int(self.camera.sharpness),
                "format": lambda v: f"{int(v)}%",
                "attr": "sharpness",
                "hw": False
            },
            {
                "key": "cam_wb_temp",
                "name": "White Balance (Cool ↔ Warm)",
                "min": -50, "max": 50, "step": 2,
                "get_initial": lambda: int(self.camera.wb_temp),
                "format": lambda v: "Neutral (0)" if int(v) == 0 else (f"Warm +{int(v)}" if int(v) > 0 else f"Cool {int(v)}"),
                "attr": "wb_temp",
                "hw": True
            },
            {
                "key": "cam_zoom",
                "name": "Macro Digital Zoom",
                "min": 100, "max": 200, "step": 5,
                "get_initial": lambda: int(self.camera.zoom),
                "format": lambda v: f"{float(v) / 100.0:.2f}x",
                "attr": "zoom",
                "hw": False
            },
        ]

        for spec in cam_specs:
            row = tk.Frame(card_ctrl, bg=PANEL)
            row.pack(fill="x", padx=px(2), pady=(0, px(4)))

            hdr = tk.Frame(row, bg=PANEL)
            hdr.pack(fill="x", pady=(0, px(1)))

            tk.Label(hdr, text=spec["name"], font=self.f(9, True), fg=WHITE, bg=PANEL).pack(side="left")

            init_val = spec["get_initial"]()
            val_lbl = tk.Label(
                hdr, text=spec["format"](init_val), font=self.f(9, True),
                fg=GREEN_ACCENT, bg=CARD, padx=px(7), pady=px(1)
            )
            val_lbl.pack(side="right")
            self.cam_slider_badges[spec["key"]] = (val_lbl, spec["format"])

            slider = tk.Scale(
                row,
                from_=spec["min"],
                to=spec["max"],
                resolution=spec["step"],
                orient="horizontal",
                showvalue=False,
                width=px(14),
                sliderlength=px(30),
                bg=PANEL,
                troughcolor=BG,
                activebackground=GREEN_ACCENT,
                highlightthickness=0,
                bd=0,
                cursor="hand2"
            )
            slider.set(init_val)
            slider.pack(fill="x")
            self.cam_sliders[spec["key"]] = (slider, spec)

        self.root.update_idletasks()
        for key, (slider, spec) in self.cam_sliders.items():
            slider.config(command=lambda val, s=spec: self._on_cam_slider_change(s, val))
        self._refresh_cam_toggle_buttons()

    def _on_cam_slider_change(self, spec, val):
        v_int = int(round(float(val)))
        if spec["key"] in self.cam_slider_badges:
            lbl, fmt = self.cam_slider_badges[spec["key"]]
            lbl.config(text=fmt(v_int))
        setattr(self.camera, spec["attr"], v_int)
        if spec.get("hw"):
            self.camera.apply_hardware_controls()
        self._save_current_settings()

    def _refresh_cam_toggle_buttons(self):
        if hasattr(self, "peaking_btn"):
            on = self.camera.focus_peaking
            self.peaking_btn.config(
                text=f"PEAKING: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )
        if hasattr(self, "flip_h_btn"):
            on = self.camera.flip_h
            self.flip_h_btn.config(
                text=f"MIRROR H: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )
        if hasattr(self, "flip_v_btn"):
            on = self.camera.flip_v
            self.flip_v_btn.config(
                text=f"FLIP 180°: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )
        if hasattr(self, "auto_exp_btn"):
            on = self.camera.auto_exp
            self.auto_exp_btn.config(
                text=f"USB AUTO-EXP: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )
        if hasattr(self, "auto_wb_btn"):
            on = self.camera.auto_wb
            self.auto_wb_btn.config(
                text=f"USB AUTO-WB: {'ON' if on else 'OFF'}",
                bg=GREEN_PRIMARY if on else CARD
            )

    def _toggle_focus_peaking(self):
        self.camera.focus_peaking = not self.camera.focus_peaking
        self._refresh_cam_toggle_buttons()

    def _toggle_flip_h(self):
        self.camera.flip_h = not self.camera.flip_h
        self._refresh_cam_toggle_buttons()
        self._save_current_settings()

    def _toggle_flip_v(self):
        self.camera.flip_v = not self.camera.flip_v
        self._refresh_cam_toggle_buttons()
        self._save_current_settings()

    def _toggle_auto_exp(self):
        self.camera.auto_exp = not self.camera.auto_exp
        self.camera.apply_hardware_controls()
        self._refresh_cam_toggle_buttons()
        self._save_current_settings()

    def _toggle_auto_wb(self):
        self.camera.auto_wb = not self.camera.auto_wb
        self.camera.apply_hardware_controls()
        self._refresh_cam_toggle_buttons()
        self._save_current_settings()

    def _reset_camera_defaults(self):
        self.camera.contrast = 100
        self.camera.brightness = 0
        self.camera.saturation = 100
        self.camera.sharpness = 100
        self.camera.wb_temp = 0
        self.camera.zoom = 100
        self.camera.flip_h = False
        self.camera.flip_v = False
        self.camera.auto_exp = True
        self.camera.auto_wb = True
        self.camera.focus_peaking = False
        self.camera.apply_hardware_controls()
        self._sync_cam_panel_widgets()
        self._save_current_settings()

    def _sync_cam_panel_widgets(self):
        for key, (slider, spec) in getattr(self, "cam_sliders", {}).items():
            init_val = spec["get_initial"]()
            slider.config(command="")
            slider.set(init_val)
            if key in self.cam_slider_badges:
                lbl, fmt = self.cam_slider_badges[key]
                lbl.config(text=fmt(init_val))
        self.root.update_idletasks()
        for key, (slider, spec) in getattr(self, "cam_sliders", {}).items():
            slider.config(command=lambda val, s=spec: self._on_cam_slider_change(s, val))
        self._refresh_cam_toggle_buttons()

    def open_camera_panel(self):
        self._sync_cam_panel_widgets()
        self.cam_panel.place(x=0, y=0, relwidth=1, relheight=1)
        self.cam_panel.lift()

    def _back_to_admin_from_camera(self):
        self._sync_sliders_to_attributes()
        self._save_current_settings()
        self.cam_panel.place_forget()
        self.open_admin_panel()

    def _update_camera_panel_preview(self, frame):
        if not hasattr(self, "cam_panel") or not self.cam_panel.winfo_ismapped():
            return
        if frame is None:
            self.cam_ctrl_canvas.itemconfig(
                self.cam_ctrl_msg,
                text="No webcam connected.\nUse Admin -> DETECT WEBCAM."
            )
            return

        # Update Focus Sharpness Meter
        pct, raw_lap = self.camera.compute_focus_metric(frame)
        if pct >= 68:
            f_col = GREEN_ACCENT
            f_tag = "PEAK FOCUS — LOCK RING"
        elif pct >= 42:
            f_col = AMBER_WARN
            f_tag = "GOOD — FINE-TUNE RING"
        else:
            f_col = RED_ALERT
            f_tag = "BLURRY — TWIST FOCUS RING"

        self.focus_lbl.config(
            text=f"Focus Sharpness: {pct}% ({f_tag})",
            fg=f_col
        )
        self.focus_bar.delete("all")
        fill_w = max(4, int(self.FOCUS_BAR_W * (pct / 100.0)))
        self.focus_bar.create_rectangle(0, 0, fill_w, self.FOCUS_BAR_H, fill=f_col, width=0)

        # Render live preview showing 100% of camera FoV (with optional neon Focus Peaking overlay)
        prev_img = self.camera.render_focus_peaking(frame) if self.camera.focus_peaking else frame
        disp = self._render_full_fov(prev_img, self.CAM_CTRL_W, self.CAM_CTRL_H)
        self._cam_ctrl_photo = ImageTk.PhotoImage(disp)
        self.cam_ctrl_canvas.itemconfig(self.cam_ctrl_img_item, image=self._cam_ctrl_photo)
        self.cam_ctrl_canvas.itemconfig(self.cam_ctrl_msg, text="")

    def _update_inline_guide(self, title, desc):
        if hasattr(self, "guide_title_lbl") and hasattr(self, "guide_desc_lbl"):
            self.guide_title_lbl.config(text=f"ⓘ  {title.upper()}")
            self.guide_desc_lbl.config(text=desc, fg=TEXT)

    def _revert_inline_guide(self):
        if hasattr(self, "guide_title_lbl") and hasattr(self, "guide_desc_lbl"):
            self.guide_title_lbl.config(text="ⓘ  PARAMETER GUIDE")
            self.guide_desc_lbl.config(
                text="Hover or tap any ⓘ icon to view the meaning and impact of each setting.",
                fg=MUTED
            )

    def _on_slider_change(self, spec, val):
        val_float = float(val)
        if spec["key"] in self.slider_badges:
            lbl, fmt = self.slider_badges[spec["key"]]
            lbl.config(text=fmt(val_float))

        param_val = spec["to_param"](val_float)
        setattr(self, spec["attr"], param_val)
        self._update_inline_guide(spec["info_title"], spec["info_text"])
        self._save_current_settings()

    def _save_current_settings(self):
        cfg = {
            "confidence_threshold": round(self.threshold, 3),
            "ood_margin": round(self.ood_margin, 3),
            "ood_logit": round(self.ood_logit, 2),
            "sharpness_min": round(self.sharpness_min, 1),
            "cam_contrast": int(self.camera.contrast),
            "cam_brightness": int(self.camera.brightness),
            "cam_saturation": int(self.camera.saturation),
            "cam_sharpness": int(self.camera.sharpness),
            "cam_wb_temp": int(self.camera.wb_temp),
            "cam_zoom": int(self.camera.zoom),
            "cam_flip_h": bool(self.camera.flip_h),
            "cam_flip_v": bool(self.camera.flip_v),
            "cam_auto_exp": bool(self.camera.auto_exp),
            "cam_auto_wb": bool(self.camera.auto_wb),
        }
        save_kiosk_config(cfg)

    def _reset_slider_defaults(self):
        defaults = {
            "confidence_threshold": int(CONFIDENCE_THRESHOLD * 100),
            "ood_margin": int(OOD_MARGIN_THRESHOLD * 100),
            "ood_logit": int(OOD_LOGIT_THRESHOLD * 10),
            "sharpness_min": int(SHARPNESS_MIN_THRESHOLD)
        }
        for key, (slider, spec) in self.sliders.items():
            if key in defaults:
                slider.set(defaults[key])
                val_float = float(defaults[key])
                if key in self.slider_badges:
                    lbl, fmt = self.slider_badges[key]
                    lbl.config(text=fmt(val_float))
                param_val = spec["to_param"](val_float)
                setattr(self, spec["attr"], param_val)

        self._save_current_settings()
        self._update_inline_guide(
            "RESET DEFAULTS COMPLETE",
            "All AI diagnostic and quality parameters have been restored to factory recommended calibration defaults."
        )

    def _sync_sliders_to_attributes(self):
        for key, (slider, spec) in getattr(self, "sliders", {}).items():
            try:
                val_float = float(slider.get())
                param_val = spec["to_param"](val_float)
                setattr(self, spec["attr"], param_val)
            except Exception:
                pass
        for key, (slider, spec) in getattr(self, "cam_sliders", {}).items():
            try:
                v_int = int(round(float(slider.get())))
                setattr(self.camera, spec["attr"], v_int)
            except Exception:
                pass

    def open_admin_panel(self):
        for key, (slider, spec) in getattr(self, "sliders", {}).items():
            init_val = spec["get_initial"]()
            slider.config(command="")
            slider.set(init_val)
            if key in self.slider_badges:
                lbl, fmt = self.slider_badges[key]
                lbl.config(text=fmt(init_val))
        self.root.update_idletasks()
        for key, (slider, spec) in getattr(self, "sliders", {}).items():
            slider.config(command=lambda val, s=spec: self._on_slider_change(s, val))

        is_conn = (self.camera and self.camera.kind != "none")
        cam_text = self.camera.kind if is_conn else "No Webcam Connected"
        color = GREEN_PRIMARY if is_conn else RED_ALERT
        self.webcam_status_lbl.config(text=f"Current Status:\n{cam_text}", fg=color)
        self.detect_msg_lbl.config(text="Click DETECT WEBCAM to scan USB ports", fg=MUTED)
        self._revert_inline_guide()
        self.admin.place(x=0, y=0, relwidth=1, relheight=1)
        self.admin.lift()

    def _trigger_detect_webcam(self):
        self.detect_btn.config(state="disabled", text="SCANNING...")
        self.detect_msg_lbl.config(text="Scanning USB ports for video devices...", fg=MUTED)
        self.root.update_idletasks()

        q = queue.Queue()
        def scan_worker():
            ok, msg = self.camera.detect_webcam()
            q.put((ok, msg))

        threading.Thread(target=scan_worker, daemon=True).start()

        def poll_scan():
            try:
                ok, msg = q.get_nowait()
                self._on_detect_webcam_finished(ok, msg)
                return
            except queue.Empty:
                pass
            if self.running:
                self.root.after(40, poll_scan)

        poll_scan()

    def _has_camera(self):
        return bool(self.camera and self.camera.kind != "none")

    def _on_detect_webcam_finished(self, ok, msg):
        if ok:
            self.paused = False
            self.captured_frame = None
            self.webcam_status_lbl.config(text=f"Connected:\n{self.camera.kind}", fg=GREEN_PRIMARY)
            self.detect_msg_lbl.config(text="SUCCESS: Webcam connected and active!", fg=GREEN_PRIMARY)
            self.canvas.itemconfig(self.msg_txt, text="")
            self._reset_panel()
            self._update_stats_bar()
            self.detect_btn.config(state="normal", text="DETECT WEBCAM")
            self.root.after(750, self.close_overlays)
        else:
            self.webcam_status_lbl.config(text="Current Status: No Webcam Found (File Mode Active)", fg=AMBER_WARN)
            self.detect_msg_lbl.config(text=f"{msg} — Using PICK FROM FILE mode.", fg=AMBER_WARN)
            if not self.paused:
                self._reset_panel()
            self._update_stats_bar()
            self.detect_btn.config(state="normal", text="DETECT WEBCAM")

    def close_overlays(self):
        was_admin = (hasattr(self, "admin") and self.admin.winfo_ismapped()) or (hasattr(self, "cam_panel") and self.cam_panel.winfo_ismapped())
        if was_admin:
            self._sync_sliders_to_attributes()
            self._save_current_settings()
        self.picker.place_forget()
        self.pwd_screen.place_forget()
        self.admin.place_forget()
        if hasattr(self, "cam_panel"):
            self.cam_panel.place_forget()
        if was_admin and self.paused and self.last_probs:
            self._render_diagnosis(self.last_probs, self.last_raw_out)

    # ---- 6. Live Camera Loop & AI Pipeline (Non-Blocking Async Bootstrap) ----
    def _start_async_bootstrap(self):
        # Force initial paint so the UI is visible, responsive, and avoids "Not Responding"
        ensure_diagnosis_samples_dir()
        self.root.update_idletasks()
        self._init_queue = queue.Queue()

        def worker():
            classifier = Classifier(MODEL_PATH, LABELS_PATH)
            parsed = [parse_label(l) for l in classifier.labels]
            crops = [p[0] for p in parsed]
            plants = list(dict.fromkeys(c for c in crops if c))
            self.camera.detect_webcam()
            self._init_queue.put((classifier, parsed, crops, plants))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_init_queue()

    def _poll_init_queue(self):
        try:
            res = self._init_queue.get_nowait()
            self._on_bootstrap_complete(*res)
            return
        except queue.Empty:
            pass
        if self.running:
            self.root.after(40, self._poll_init_queue)

    def _on_bootstrap_complete(self, classifier, parsed, crops, plants):
        self.classifier = classifier
        self.parsed = parsed
        self.crops = crops
        self.plants = plants

        self._reset_panel()
        self._update_stats_bar()
        self._preview_loop()

    def _preview_loop(self):
        if not self.running:
            return
        cam_panel_open = hasattr(self, "cam_panel") and self.cam_panel.winfo_ismapped()
        if (not self.paused or cam_panel_open) and self._has_camera():
            frame = self.camera.read()
            if frame is not None:
                if not self.paused:
                    self.latest_frame = frame
                    self._show_image(frame)
                if cam_panel_open:
                    self._update_camera_panel_preview(frame)
            elif not self._has_camera():
                if not self.paused:
                    self._reset_panel()
                if cam_panel_open:
                    self._update_camera_panel_preview(None)
                self._update_stats_bar()
        elif cam_panel_open:
            self._update_camera_panel_preview(None)
        self.root.after(int(1000 / PREVIEW_FPS), self._preview_loop)

    def _render_full_fov(self, img, target_w, target_h):
        """Scales image to display 100% of the complete Field of View (zero edge cropping)."""
        iw, ih = img.size
        if iw <= 0 or ih <= 0:
            return img.resize((target_w, target_h), RESAMPLE)
        scale = min(target_w / iw, target_h / ih)
        nw = max(1, int(round(iw * scale)))
        nh = max(1, int(round(ih * scale)))
        resized = img.resize((nw, nh), RESAMPLE)
        if nw == target_w and nh == target_h:
            return resized
        canvas_im = Image.new("RGB", (target_w, target_h), (5, 10, 7))
        canvas_im.paste(resized, ((target_w - nw) // 2, (target_h - nh) // 2))
        return canvas_im

    def _show_image(self, img):
        disp = self._render_full_fov(img, self.CAM_W, self.CAM_H)
        self._photo = ImageTk.PhotoImage(disp)
        self.canvas.itemconfig(self.img_item, image=self._photo)
        self.canvas.itemconfig(self.msg_txt, text="")

    def _reset_panel(self):
        has_cam = self._has_camera()
        self.banner_frame.config(bg=GREY_BTN)
        if self.selected_plant is None:
            self.plant_lbl.config(text="Mode: Auto-Detect (Beta Production)")
        else:
            self.plant_lbl.config(text=f"Selected Plant: {self.selected_plant.upper()}")

        if has_cam:
            self.banner.config(text="READY — AIM LEAF AT CAMERA", bg=GREY_BTN, fg=WHITE)
            self.disease_lbl.config(text="Aim leaf inside box -> Tap CAPTURE -> Tap DIAGNOSE")
            self.capture_btn.config(text="CAPTURE LEAF", bg=GREEN_PRIMARY, fg=WHITE)
            self.canvas.itemconfig(self.live_badge, text="LIVE WEBCAM", fill=GREEN_ACCENT)
            self.canvas.itemconfig(self.msg_txt, text="")
            self.quality_lbl.config(text="Leaf Quality AI: Align leaf inside box", fg=MUTED)
        else:
            self.banner.config(text="READY — PICK LEAF IMAGE FROM FILE", bg=GREY_BTN, fg=WHITE)
            self.disease_lbl.config(text="Tap PICK FROM FILE -> Select leaf image -> Tap DIAGNOSE")
            self.capture_btn.config(text="PICK FROM FILE", bg=GREEN_PRIMARY, fg=WHITE)
            self.canvas.itemconfig(self.live_badge, text="FILE MODE (NO CAMERA)", fill=AMBER_WARN)
            if not self.paused:
                self.canvas.itemconfig(
                    self.msg_txt,
                    text=(
                        "No camera connected — File Mode Active\n\n"
                        "Tap 'PICK FROM FILE' below (or click here)\n"
                        "Folder: diagnosis_samples/ (Apple, Mango, Potato, Tomato)"
                    )
                )
            self.quality_lbl.config(
                text="File Mode: Pick leaf image from diagnosis_samples/ (Apple, Mango, Potato, Tomato)",
                fg=MUTED
            )

        self.diagnose_btn.config(text="DIAGNOSE LEAF", bg=CARD, fg=WHITE)
        self._draw_bar(0, GREY_BTN, "Waiting for leaf...")
        for row, num, txt in self.step_rows:
            num.config(bg=GREEN_PRIMARY, fg=WHITE)
            txt.config(text="")
            row.pack_forget()
        self.cam_border.config(bg=CARD)

    # ---- 7. SEPARATE ACTIONS: Capture / Pick from File, Retake, and Diagnose ----
    def pick_image_from_file(self):
        """Opens file picker inside the fixed diagnosis_samples/ folder structure when camera is unavailable."""
        base_dir = ensure_diagnosis_samples_dir()
        init_dir = base_dir
        if self.selected_plant:
            cand = os.path.join(base_dir, self.selected_plant)
            if os.path.isdir(cand):
                init_dir = cand

        try:
            self.root.attributes("-topmost", False)
        except Exception:
            pass

        filepath = filedialog.askopenfilename(
            parent=self.root,
            initialdir=init_dir,
            title="Select Leaf Image for Diagnosis (diagnosis_samples)",
            filetypes=[
                ("Leaf Images", "*.jpg *.jpeg *.png *.bmp *.webp *.JPG *.JPEG *.PNG"),
                ("All Files", "*.*"),
            ],
        )
        if not filepath or not os.path.isfile(filepath):
            return False

        try:
            with Image.open(filepath) as raw_im:
                loaded_img = raw_im.convert("RGB")
        except Exception as e:
            self.quality_lbl.config(text=f"Could not open image file: {e}", fg=RED_ALERT)
            return False

        self.latest_frame = loaded_img
        self.last_probs = None
        self.last_raw_out = None
        isolated_leaf, outline_ok, info = LeafOutlineSegmenter.extract_leaf(loaded_img)

        self.paused = True
        self.canvas.itemconfig(self.guide, state="hidden")
        short_name = os.path.basename(filepath)
        if len(short_name) > 26:
            short_name = short_name[:23] + "..."

        if outline_ok and isolated_leaf is not None:
            self.captured_frame = isolated_leaf
            self._show_image(self.captured_frame)
            self.canvas.itemconfig(self.live_badge, text=f"FILE ROI: {short_name}", fill=GREEN_ACCENT)

            score, rating, q_msg, q_color = LeafQualityAI.assess(self.captured_frame, self.sharpness_min)
            self.quality_lbl.config(text=f"File Loaded ({short_name}) | {q_msg}", fg=q_color)
            self.banner_frame.config(bg=GREEN_PRIMARY)
            self.banner.config(text="LEAF IMAGE LOADED — READY TO DIAGNOSE", bg=GREEN_PRIMARY, fg=WHITE)
            self.disease_lbl.config(text="Leaf image loaded from file. Tap DIAGNOSE NOW.")
        else:
            self.captured_frame = loaded_img
            self._show_image(self.captured_frame)
            self.canvas.itemconfig(self.live_badge, text=f"FILE: {short_name}", fill=AMBER_WARN)

            score, rating, q_msg, q_color = LeafQualityAI.assess(self.captured_frame, self.sharpness_min)
            self.quality_lbl.config(text=f"File Loaded ({short_name}) | {q_msg}", fg=q_color)
            self.banner_frame.config(bg=CARD)
            self.banner.config(text="IMAGE LOADED (FULL FRAME) — READY TO DIAGNOSE", bg=CARD, fg=WHITE)
            self.disease_lbl.config(text="Image loaded from file. Tap DIAGNOSE NOW.")

        self.capture_btn.config(text="PICK FROM FILE", bg=AMBER_WARN, fg=WHITE)
        self.diagnose_btn.config(text="DIAGNOSE NOW", bg=GREEN_PRIMARY, fg=WHITE)
        return True

    def handle_capture_or_retake(self):
        """Toggles between CAPTURE/RETAKE when camera is available, or PICK FROM FILE when no camera is connected."""
        if not self._has_camera():
            self.pick_image_from_file()
            return

        if not self.paused:
            # 1. ACTION: CAPTURE
            if self.latest_frame is not None:
                isolated_leaf, outline_ok, info = LeafOutlineSegmenter.extract_leaf(self.latest_frame)

                self.paused = True
                self.canvas.itemconfig(self.guide, state="hidden")

                if outline_ok and isolated_leaf is not None:
                    self.captured_frame = isolated_leaf
                    self._show_image(self.captured_frame)
                    self.canvas.itemconfig(self.live_badge, text="LEAF ROI ISOLATED", fill=GREEN_ACCENT)

                    score, rating, q_msg, q_color = LeafQualityAI.assess(self.captured_frame, self.sharpness_min)
                    self.quality_lbl.config(text=f"Leaf ROI Isolated | {q_msg}", fg=q_color)
                    self.banner_frame.config(bg=GREEN_PRIMARY)
                    self.banner.config(text="LEAF OUTLINE ISOLATED — READY TO DIAGNOSE", bg=GREEN_PRIMARY, fg=WHITE)
                    self.disease_lbl.config(text="Leaf region focused cleanly. Tap DIAGNOSE NOW.")
                else:
                    self.captured_frame = self.latest_frame
                    self._show_image(self.captured_frame)
                    self.canvas.itemconfig(self.live_badge, text="CAPTURED (FULL FRAME)", fill=AMBER_WARN)

                    score, rating, q_msg, q_color = LeafQualityAI.assess(self.captured_frame, self.sharpness_min)
                    self.quality_lbl.config(text=f"Full Frame Image | {q_msg}", fg=q_color)
                    self.banner_frame.config(bg=CARD)
                    self.banner.config(text="IMAGE CAPTURED (FULL FRAME) — READY TO DIAGNOSE", bg=CARD, fg=WHITE)
                    self.disease_lbl.config(text="Complete image captured. Tap DIAGNOSE NOW.")

                # Always move ahead: swap Capture to RETAKE and Diagnose to DIAGNOSE NOW
                self.capture_btn.config(text="RETAKE LEAF", bg=AMBER_WARN, fg=WHITE)
                self.diagnose_btn.config(text="DIAGNOSE NOW", bg=GREEN_PRIMARY, fg=WHITE)
            else:
                self.quality_lbl.config(text="Camera not ready. Tap PICK FROM FILE or check USB webcam.", fg=RED_ALERT)
        else:
            # 2. ACTION: RETAKE (Unfreeze)
            self.paused = False
            self.captured_frame = None
            self.last_probs = None
            self.last_raw_out = None
            self.canvas.itemconfig(self.guide, state="normal")
            self._reset_panel()
            self._update_stats_bar()

    def handle_diagnose(self):
        """Runs MobileNetV4 inference on the captured (or file-loaded) frame."""
        if not self._has_camera() and self.captured_frame is None:
            if not self.pick_image_from_file():
                return

        if self.captured_frame is None and self.latest_frame is not None:
            # If user directly pressed DIAGNOSE while live, attempt outline capture or fallback
            isolated_leaf, outline_ok, info = LeafOutlineSegmenter.extract_leaf(self.latest_frame)
            self.paused = True
            if outline_ok and isolated_leaf is not None:
                self.captured_frame = isolated_leaf
                self.canvas.itemconfig(self.live_badge, text="LEAF ROI ISOLATED", fill=GREEN_ACCENT)
            else:
                self.captured_frame = self.latest_frame
                self.canvas.itemconfig(self.live_badge, text="CAPTURED (FULL FRAME)", fill=AMBER_WARN)

            self._show_image(self.captured_frame)
            self.canvas.itemconfig(self.guide, state="hidden")
            score, rating, q_msg, q_color = LeafQualityAI.assess(self.captured_frame, self.sharpness_min)
            self.quality_lbl.config(text=q_msg, fg=q_color)
            self.capture_btn.config(text="RETAKE LEAF" if self._has_camera() else "PICK FROM FILE", bg=AMBER_WARN, fg=WHITE)
            self.diagnose_btn.config(text="DIAGNOSE NOW", bg=GREEN_PRIMARY, fg=WHITE)

        target_img = self.captured_frame if self.captured_frame is not None else self.latest_frame
        if target_img is None:
            if self._has_camera():
                self.disease_lbl.config(text="No leaf image captured! Please aim at leaf and tap CAPTURE.")
            else:
                self.disease_lbl.config(text="No image selected! Tap PICK FROM FILE to load a leaf image.")
            return

        if self.classifier:
            res = self.classifier.predict(target_img)
            if len(res) == 3:
                probs, ms, raw_out = res
            else:
                probs, ms = res
                raw_out = None
            self.last_probs = probs
            self.last_raw_out = raw_out
            self.latency_ms = ms
            self._render_diagnosis(probs, raw_out)
            self._update_stats_bar()

    def _render_diagnosis(self, probs, raw_out=None):
        labels = self.classifier.labels
        n = len(labels)
        raw_probs = list(probs)
        adj = list(probs)

        # Unfiltered raw metrics for Out-Of-Distribution (OOD) validation
        raw_sorted = sorted(raw_probs, reverse=True)
        raw_top1 = raw_sorted[0]
        raw_top2 = raw_sorted[1] if len(raw_sorted) > 1 else 0.0
        raw_margin = raw_top1 - raw_top2
        max_logit = float(np.max(raw_out)) if raw_out is not None else 10.0

        # Plant filtering when a target crop is explicitly selected
        plant_tot = 1.0
        if self.selected_plant:
            plant_keep = [self.crops[i] == self.selected_plant for i in range(n)]
            plant_tot = sum(p for p, m in zip(raw_probs, plant_keep) if m)
            keep = [self.crops[i] == self.selected_plant or not self.crops[i] for i in range(n)]
            tot = sum(p for p, m in zip(adj, keep) if m)
            if tot > 0:
                adj = [p / tot if m else 0.0 for p, m in zip(adj, keep)]

        adj_sorted = sorted(adj, reverse=True)
        active_margin = adj_sorted[0] - (adj_sorted[1] if len(adj_sorted) > 1 else 0.0)

        best = max(range(n), key=lambda i: adj[i])
        conf = adj[best]
        crop, cond, healthy = self.parsed[best]

        # 1. OUT-OF-DISTRIBUTION (OOD) / UNKNOWN PLANT DETECTION:
        # Rejects non-target flora / background when Other_Plant_or_Background wins,
        # when raw neural logit energy is too weak, or when selected crop has negligible probability.
        is_negative_class = ("other" in cond.lower()) or ("background" in cond.lower())
        is_unknown_plant = (
            is_negative_class
            or (max_logit < self.ood_logit)
            or (self.selected_plant is not None and plant_tot < 0.12)
        )

        # 2. LOW CONFIDENCE / AMBIGUITY GATE:
        # Triggers 'LOW CONFIDENCE — PLEASE RETAKE' when confidence is below threshold
        # or top-1 vs top-2 margin is too narrow.
        is_low_confidence = (conf < self.threshold) or (active_margin < self.ood_margin)

        if is_unknown_plant:
            status = "UNKNOWN PLANT / OUT OF SCOPE"
            color = AMBER_WARN
            plant_txt = "Plant: Unrecognized (Outside Catalog)"
            disease_txt = "Specimen outside supported scope (Apple, Mango, Potato, Tomato)"
            steps = OOD_STEPS
            num_color = AMBER_WARN
            btn_txt = "UNKNOWN LEAF"
            btn_color = AMBER_WARN
        elif is_low_confidence:
            status = "LOW CONFIDENCE — PLEASE RETAKE"
            color = AMBER_WARN
            if self.selected_plant:
                plant_txt = f"Selected: {self.selected_plant.upper()}"
            else:
                plant_txt = "Mode: Auto-Detect (Beta Production)"
            disease_txt = "Low Confidence — Cannot Safely Identify"
            steps = UNSURE_STEPS
            num_color = AMBER_WARN
            btn_txt = "LOW CONFIDENCE"
            btn_color = AMBER_WARN
        elif healthy:
            status = "HEALTHY LEAF — NO DISEASE"
            color = GREEN_PRIMARY
            auto_suffix = " (Auto-Detected)" if self.selected_plant is None else ""
            plant_txt = f"Plant: {crop}{auto_suffix}" if crop else ("Auto-Detect (Beta Production)" if self.selected_plant is None else "")
            disease_txt = "No Disease Detected (Healthy Foliage)"
            steps = get_recommendation(crop, cond)
            num_color = GREEN_PRIMARY
            btn_txt = "HEALTHY CROP"
            btn_color = GREEN_PRIMARY
        else:
            status = f"{cond.upper()} DETECTED"
            color = RED_ALERT
            auto_suffix = " (Auto-Detected)" if self.selected_plant is None else ""
            plant_txt = f"Plant: {crop}{auto_suffix}" if crop else ("Auto-Detect (Beta Production)" if self.selected_plant is None else "")
            disease_txt = cond
            steps = get_recommendation(crop, cond)
            num_color = RED_ALERT
            btn_txt = "DISEASE FOUND"
            btn_color = RED_ALERT

        # Update Banner & Texts
        self.banner_frame.config(bg=color)
        self.banner.config(text=status, bg=color, fg=WHITE)
        self.plant_lbl.config(text=plant_txt)
        self.disease_lbl.config(text=disease_txt)
        self.cam_border.config(bg=color)
        self.diagnose_btn.config(text=btn_txt, bg=btn_color, fg=WHITE)

        # Update Confidence Bar (if unknown plant, display the rejection message)
        if is_unknown_plant:
            self._draw_bar(raw_top1, color, f"Uncertain Match: {raw_top1 * 100:.1f}% (Rejected as Unknown)")
        else:
            self._draw_bar(conf, color)

        # Update Steps
        for row, _, _ in self.step_rows:
            row.pack_forget()
        for (row, num, txt), step in zip(self.step_rows, steps):
            num.config(bg=num_color)
            txt.config(text=step)
            row.pack(fill="x", pady=(0, self.px(5)))

    def _draw_bar(self, frac, color, text=None):
        self.bar.delete("all")
        if frac > 0:
            self.bar.create_rectangle(0, 0, int(self.BAR_W * frac), self.BAR_H, fill=color, width=0)
        lbl_text = f"Confidence: {frac * 100:.1f}%" if text is None else text
        self.bar.create_text(
            self.BAR_W // 2, self.BAR_H // 2, fill=TEXT,
            font=self.f(9, True), text=lbl_text
        )

    def _update_stats_bar(self):
        mode_text = self.classifier.mode if self.classifier else "Initializing..."
        if self.classifier and self.classifier.error_reason:
            mode_text = f"DEMO ({self.classifier.error_reason})"
        lat = f"{self.latency_ms:.0f} ms" if self.latency_ms > 0 else "-- ms"
        cam = self.camera.kind if self.camera else "none"
        py_ver = f"Py {platform.python_version()}"
        self.stats_lbl.config(text=f"v{APP_VERSION} | AI: {mode_text} | Latency: {lat} | Camera: {cam} | {py_ver}")

    def close(self):
        self.running = False
        try:
            self._sync_sliders_to_attributes()
            self._save_current_settings()
        except Exception:
            pass
        for job in self.root.tk.call("after", "info"):
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        try:
            if self.camera:
                self.camera.close()
        finally:
            self.root.destroy()


# =============================================================================
# 8. MAIN ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = AgriLensApp(root)
    root.mainloop()
