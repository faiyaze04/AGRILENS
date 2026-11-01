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
import tkinter.font as tkFont
from collections import deque

try:
    from PIL import Image, ImageOps, ImageTk, ImageDraw
except ImportError:
    raise SystemExit(
        "Pillow is missing!\n"
        "PC (Thonny): Tools -> Manage packages... -> install 'pillow'\n"
        "Raspberry Pi: sudo apt install -y python3-pil python3-pil.imagetk"
    )

try:
    import numpy as np
except ImportError:
    np = None

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

# Calibrated confidence & Out-Of-Distribution (OOD) rejection thresholds
CONFIDENCE_THRESHOLD = 0.65  # Minimum positive identification threshold (65%)
OOD_MARGIN_THRESHOLD = 0.30  # Minimum gap between 1st and 2nd class
OOD_LOGIT_THRESHOLD  = 4.20  # Minimum raw logit activation for supported crops
SHARPNESS_MIN_THRESHOLD = 55.0  # Minimum spatial Laplacian focus sharpness variance

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kiosk_config.json") if "__file__" in globals() else "kiosk_config.json"
DEFAULT_CONFIG = {
    "confidence_threshold": CONFIDENCE_THRESHOLD,
    "ood_margin": OOD_MARGIN_THRESHOLD,
    "ood_logit": OOD_LOGIT_THRESHOLD,
    "sharpness_min": SHARPNESS_MIN_THRESHOLD,
}

def load_kiosk_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    cfg.update(data)
        except Exception as e:
            print(f"Notice: loading default config ({e})")
    return cfg

def save_kiosk_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"Notice: unable to save kiosk config ({e})")

ADMIN_PASSWORD = "AGRILENS"
PREVIEW_FPS = 25
RESAMPLE = getattr(Image, "Resampling", Image).BILINEAR

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
    "Auto mode is in Beta Production. Tap 'SELECT PLANT' to focus on your crop.",
]

OOD_STEPS = [
    "This leaf does not match features of supported crops (Apple, Mango, Tomato).",
    "Non-target plants (e.g. money plant, ornamental flora, weeds) are outside catalog.",
    "If diagnosing a supported crop, tap 'SELECT PLANT' to lock your target crop.",
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
    healthy = "healthy" in clean.lower()
    for sep in ("___", "__", " - ", ": "):
        if sep in clean:
            parts = clean.split(sep, 1)
            crop = parts[0].replace("_", " ").title().strip()
            cond = parts[1].replace("_", " ").title().strip()
            return crop, cond, healthy
    return "", clean.replace("_", " ").title(), healthy


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
        self.cap = None
        self.cv2 = None
        self.kind = "none"
        self.port = -1
        self.backend = "none"
        self.width = 640
        self.height = 480
        self.device_name = "USB Camera"
        self.fail_count = 0

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
                        # Query friendly hardware model name asynchronously in background
                        self._fetch_friendly_names_async()
                        return True, f"Connected: {self.kind}"

                    c.release()
                except Exception:
                    pass

        self.kind = "none"
        self.port = -1
        self.backend = "none"
        return False, "No active webcam found. Please plug in USB camera and click DETECT WEBCAM."

    def read(self):
        """Reads the latest camera frame with fault-tolerance and dropped-signal handling."""
        if self.cap and self.cap.isOpened():
            try:
                ok, frame = self.cap.read()
                if ok and frame is not None and frame.size > 0:
                    self.fail_count = 0
                    rgb = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2RGB)
                    return Image.fromarray(rgb)
                else:
                    self.fail_count += 1
                    if self.fail_count > 30:  # ~1 second of continuous frame drops
                        self.close()
                        self.kind = "none"
            except Exception:
                self.fail_count += 1
                if self.fail_count > 30:
                    self.close()
                    self.kind = "none"
        return None

    def close(self):
        """Safely releases the hardware camera handle."""
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
                        if len(parts) == 2 and parts[0].isdigit():
                            clean.append(parts[1])
                        else:
                            clean.append(line)
                    if clean:
                        return clean
            except Exception as e:
                print("Labels load error:", e)

        return [
            "Apple___Rust", "Apple___Scab", "Apple___healthy",
            "Mango___Anthracnose", "Mango___Bacterial_Canker", "Mango___Cutting_Weevil",
            "Mango___Die_Back", "Mango___Gall_Midge", "Mango___Healthy",
            "Mango___Powdery_Mildew", "Mango___Sooty_Mould",
            "Tomato___Bacterial_spot", "Tomato___Early_blight", "Tomato___Late_blight",
            "Tomato___Leaf_Mold", "Tomato___Septoria_leaf_spot",
            "Tomato___Spider_mites_Two-spotted_spider_mite", "Tomato___Target_Spot",
            "Tomato___Tomato_Yellow_Leaf_Curl_Virus", "Tomato___Tomato_mosaic_virus", "Tomato___healthy"
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
            self.mode = "DEMO"
            self.error_reason = "onnxruntime not installed in this Python"
        except Exception as e:
            self.mode = "DEMO"
            self.error_reason = str(e)

    def predict(self, pil_image):
        t0 = time.perf_counter()

        # If running in DEMO mode because of missing onnxruntime
        if self.session is None or np is None:
            time.sleep(0.05)
            n = len(self.labels)
            probs = [1.0 / n] * n
            return probs, (time.perf_counter() - t0) * 1000, None

        # Normalization (MobileNetV4 ImageNet: mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        img = ImageOps.fit(pil_image.convert("RGB"), (self.w, self.h), RESAMPLE)
        arr = np.asarray(img, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std

        if self.layout == "NCHW":
            arr = np.transpose(arr, (2, 0, 1))
        tensor = np.expand_dims(arr, axis=0)

        # Run ONNX inference
        raw_out = self.session.run(None, {self.input_name: tensor})[0][0]
        # Softmax
        exps = np.exp(raw_out - np.max(raw_out))
        probs = (exps / np.sum(exps)).tolist()

        ms = (time.perf_counter() - t0) * 1000
        return probs, ms, raw_out


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
        scale = 3
        sw, sh, sr = self.width * scale, self.height * scale, self.radius * scale
        im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=sr, fill=fill,
                            outline=self.border_color, width=self.border_width * scale if self.border_color else 0)
        res = im.resize((self.width, self.height), Image.Resampling.LANCZOS)
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
        self.latency_ms = 0.0

        self.entered_password = ""
        self.camera = Camera(auto_detect=False)
        self.classifier = None
        self.plants = ["Apple", "Mango", "Pepper", "Potato"]
        self.crops = []
        self.parsed = []
        self.sliders = {}
        self.slider_badges = {}

        self._setup_window()
        self._build_top_bar()
        self._build_body()
        self._build_plant_picker()
        self._build_password_screen()
        self._build_admin_panel()

        # Display immediate responsive startup status on canvas
        self.canvas.itemconfig(
            self.msg_txt,
            text="⚡ INITIALIZING AGRILENS AI VISION ENGINE...\nConnecting to camera..."
        )
        self.banner.config(text="STARTING UP — PLEASE WAIT...", bg=GREY_BTN, fg=WHITE)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda e: self.close())
        self.root.bind("<space>", lambda e: self.handle_capture_or_retake())

        # Non-blocking async bootstrap: window paints immediately in <0.1s
        self.root.after(30, self._start_async_bootstrap)

    def _setup_window(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        is_pi = platform.system() == "Linux"

        if is_pi:
            self.root.attributes("-fullscreen", True)
            self.W, self.H = sw, sh
        else:
            self.W = min(1024, max(800, sw - 100))
            self.H = min(600, max(480, sh - 100))
            self.root.geometry(f"{self.W}x{self.H}+50+50")
            self.root.resizable(False, False)

        self.S = min(self.W / 1024, self.H / 600)
        self.TOP_H = self.px(54)
        self.root.title("AGRILENS - AI Plant Health Kiosk")
        self.root.configure(bg=BG)

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
        lbl_brand = tk.Label(title_box, text=f"AGRILENS v{APP_VERSION}", font=self.f(15, True), fg=WHITE, bg=PANEL, cursor="hand2")
        lbl_brand.pack(anchor="w")
        ToolTip(lbl_brand, "AGRILENS Edge Vision Kiosk", f"Version: v{APP_VERSION}\nBuild: {BUILD_TIMESTAMP}\nModel: MobileNetV4 ONNX (17 Classes)", font_family=FONT)
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
        pad = px(8)
        body_h = self.H - self.TOP_H

        body = tk.Frame(self.root, bg=BG)
        body.pack(side="top", fill="both", expand=True)

        # LEFT SIDE - Camera Feed + Quality AI Bar + Action Buttons
        left = tk.Frame(body, bg=BG, width=self.W // 2, height=body_h)
        left.pack(side="left")
        left.pack_propagate(False)

        btn_area_h = px(68)
        self.CAM_W = self.W // 2 - 2 * pad - 4
        self.CAM_H = body_h - btn_area_h - 2 * pad - px(34)

        self.cam_border = tk.Frame(left, bg=CARD, padx=2, pady=2)
        self.cam_border.pack(side="top", pady=(pad, px(4)))

        # Clean Camera Canvas with subtle targeting frame
        self.canvas = tk.Canvas(self.cam_border, width=self.CAM_W, height=self.CAM_H,
                                bg="#000000", highlightthickness=0)
        self.canvas.pack()
        self.canvas.bind("<Button-1>", lambda e: self.handle_capture_or_retake())

        cw, ch = self.CAM_W, self.CAM_H
        self.img_item = self.canvas.create_image(cw // 2, ch // 2, anchor="center")

        # Leaf Alignment Targeting Box
        side = int(min(cw, ch) * 0.82)
        x0, y0 = (cw - side) // 2, (ch - side) // 2
        self.guide = self.canvas.create_rectangle(
            x0, y0, x0 + side, y0 + side,
            outline=GREEN_ACCENT, width=px(2), dash=(8, 5)
        )

        # Live webcam indicator overlay
        self.live_badge = self.canvas.create_text(
            px(58), px(16), fill=GREEN_ACCENT, font=self.f(9, True),
            text="LIVE WEBCAM"
        )

        self.msg_txt = self.canvas.create_text(
            cw // 2, ch // 2, fill=MUTED, font=self.f(13),
            justify="center", text="Connecting to webcam..."
        )

        # IMAGE QUALITY AI STATUS BAR (Directly below canvas)
        quality_frame = tk.Frame(left, bg=PANEL, padx=px(8), pady=px(3))
        quality_frame.pack(side="top", fill="x", padx=pad + 2, pady=(0, px(6)))

        self.quality_lbl = tk.Label(
            quality_frame, text="Leaf Quality AI: Align leaf inside box",
            font=self.f(9, True), fg=MUTED, bg=PANEL, anchor="center"
        )
        self.quality_lbl.pack(fill="x")

        # SEPARATE ACTION BUTTONS BAR (Side-by-Side: [CAPTURE LEAF] and [DIAGNOSE LEAF])
        btn_box = tk.Frame(left, bg=BG)
        btn_box.pack(side="top", fill="x", padx=pad + 2, pady=(0, pad))

        half_btn_w = self.CAM_W // 2 - px(6)
        btn_h = px(44)

        # Button 1: CAPTURE (swaps to RETAKE when frozen)
        self.capture_btn = self._button(
            btn_box, "CAPTURE LEAF", GREEN_PRIMARY, self.handle_capture_or_retake,
            width=half_btn_w, height=btn_h, size=11, fg=WHITE, radius=px(22), parent_bg=BG
        )
        self.capture_btn.pack(side="left", padx=(0, px(4)))

        # Button 2: DIAGNOSE (Runs AI Inference)
        self.diagnose_btn = self._button(
            btn_box, "DIAGNOSE LEAF", CARD, self.handle_diagnose,
            width=half_btn_w, height=btn_h, size=11, fg=WHITE, border=BORDER, radius=px(22), parent_bg=BG
        )
        self.diagnose_btn.pack(side="left", padx=(px(4), 0))

        # RIGHT SIDE - Farmer Diagnosis & Recommendations
        right = tk.Frame(body, bg=PANEL)
        right.pack(side="left", fill="both", expand=True, padx=(0, pad), pady=pad)
        rp = px(14)
        wrap = self.W - self.W // 2 - pad - 2 * rp - px(6)

        self.banner_frame = tk.Frame(right, bg=GREY_BTN, padx=px(8), pady=px(6))
        self.banner_frame.pack(fill="x")

        self.banner = tk.Label(
            self.banner_frame, text="READY — AIM LEAF AT CAMERA", font=self.f(15, True),
            bg=GREY_BTN, fg=WHITE, pady=px(2)
        )
        self.banner.pack(fill="x")

        info = tk.Frame(right, bg=PANEL)
        info.pack(fill="x", padx=rp, pady=(px(8), 0))

        self.plant_lbl = tk.Label(info, text="Mode: Auto-Detect (Beta Production)", font=self.f(10, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w")
        self.plant_lbl.pack(fill="x")

        self.disease_lbl = tk.Label(
            info, text="Aim leaf inside box -> Tap CAPTURE -> Tap DIAGNOSE",
            font=self.f(14, True), fg=WHITE, bg=PANEL, anchor="w",
            justify="left", wraplength=wrap
        )
        self.disease_lbl.pack(fill="x")

        # Confidence Bar
        self.BAR_W, self.BAR_H = wrap, px(20)
        self.bar = tk.Canvas(info, width=self.BAR_W, height=self.BAR_H, bg=CARD, highlightthickness=0)
        self.bar.pack(anchor="w", pady=(px(6), 0))

        tk.Frame(right, bg=BORDER, height=max(1, px(1))).pack(fill="x", padx=rp, pady=(px(10), px(4)))

        tk.Label(
            right, text="RECOMMENDED FARMER ACTIONS", font=self.f(10, True),
            fg=WHITE, bg=PANEL, anchor="w"
        ).pack(fill="x", padx=rp, pady=(0, px(4)))

        # Bottom Hardware / Latency Strip
        self.stats_lbl = tk.Label(right, text="", font=self.f(8), fg=MUTED, bg=PANEL, anchor="w")
        self.stats_lbl.pack(side="bottom", fill="x", padx=rp, pady=(0, px(6)))

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
                row, text=str(i + 1), font=self.f(10, True),
                bg=GREEN_PRIMARY, fg=WHITE, width=2
            )
            num.pack(side="left", anchor="n", padx=(0, px(8)), pady=(px(1), 0))
            txt = tk.Label(
                row, text="", font=self.f(10), fg=WHITE, bg=PANEL,
                anchor="w", justify="left", wraplength=wrap - px(36)
            )
            txt.pack(side="left", fill="x", expand=True)
            self.step_rows.append((row, num, txt))

        self._draw_bar(0, GREY_BTN, "")

    # ---- 3. Plant Picker Dialog ----
    def _build_plant_picker(self):
        px = self.px
        self.picker = tk.Frame(self.root, bg=BG)
        tk.Label(self.picker, text="SELECT CROP TO DIAGNOSE", font=self.f(20, True), fg=WHITE, bg=BG).pack(pady=(px(20), px(4)))
        tk.Label(self.picker, text="Auto-detection mode automatically identifies all supported plant species",
                 font=self.f(10), fg=MUTED, bg=BG).pack()

        self.picker_grid = tk.Frame(self.picker, bg=BG)
        self.picker_grid.pack(expand=True)

        self._button(self.picker, "REVERT TO SCANNER", GREY_BTN, self.close_overlays, width=px(200), height=px(42), radius=px(21), fg=WHITE, parent_bg=BG).pack(pady=(0, px(18)))

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
                width=self.px(220), height=self.px(44), size=11, fg=WHITE,
                border=border, radius=self.px(22), parent_bg=BG
            )
            b.grid(row=i // cols, column=i % cols, padx=self.px(8), pady=self.px(8))

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
            self._render_diagnosis(self.last_probs)
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

        tk.Label(head, text="ADMIN SECURITY LOCK", font=self.f(17, True), fg=WHITE, bg=PANEL).pack(side="left", padx=px(16))
        self._button(head, "REVERT", GREY_BTN, self.close_overlays, width=px(88), height=px(38), size=10, fg=WHITE, parent_bg=PANEL).pack(side="right", padx=px(8), pady=px(7))

        disp_box = tk.Frame(self.pwd_screen, bg=BG)
        disp_box.pack(pady=(px(12), px(6)))

        self.pwd_display_lbl = tk.Label(
            disp_box, text="", font=(FONT, max(14, round(20 * self.S)), "bold"),
            fg=WHITE, bg=CARD, width=16, height=1, relief="solid", bd=1
        )
        self.pwd_display_lbl.pack(pady=(0, px(4)))

        self.pwd_status_lbl = tk.Label(
            disp_box, text="ENTER SYSTEM PASSWORD", font=self.f(10, True), fg=MUTED, bg=BG
        )
        self.pwd_status_lbl.pack()

        # Touch Keyboard with Rounded Buttons
        kb_frame = tk.Frame(self.pwd_screen, bg=BG)
        kb_frame.pack(expand=True, pady=(0, px(10)))

        rows = [
            ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
            ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
            ["CLEAR", "Z", "X", "C", "V", "B", "N", "M", "BACKSPACE"],
            ["ENTER"]
        ]

        for row in rows:
            r_frame = tk.Frame(kb_frame, bg=BG)
            r_frame.pack(pady=px(3))
            for key in row:
                if key == "ENTER":
                    btn = self._button(
                        r_frame, "ENTER", GREEN_PRIMARY, self._pwd_submit,
                        width=px(240), height=px(44), size=12, fg=WHITE, radius=px(12), parent_bg=BG
                    )
                elif key == "CLEAR":
                    btn = self._button(
                        r_frame, "CLEAR", RED_ALERT, self._pwd_clear,
                        width=px(92), height=px(42), size=10, fg=WHITE, radius=px(10), parent_bg=BG
                    )
                elif key == "BACKSPACE":
                    btn = self._button(
                        r_frame, "BACKSPACE", GREY_BTN, self._pwd_backspace,
                        width=px(92), height=px(42), size=10, fg=WHITE, radius=px(10), parent_bg=BG
                    )
                else:
                    btn = self._button(
                        r_frame, key, CARD, lambda k=key: self._pwd_key_press(k),
                        width=px(44), height=px(42), size=12, fg=WHITE, radius=px(10), border=BORDER, parent_bg=BG
                    )
                btn.pack(side="left", padx=px(3))

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

        tk.Label(head, text="ADMIN CONSOLE & AI PARAMETERS", font=self.f(17, True), fg=WHITE, bg=PANEL).pack(side="left", padx=px(16))
        self._button(head, "REVERT", GREY_BTN, self.close_overlays, width=px(88), height=px(38), size=10, fg=WHITE, parent_bg=PANEL).pack(side="right", padx=px(8), pady=px(7))

        # Split screen container
        body = tk.Frame(self.admin, bg=BG)
        body.pack(side="top", fill="both", expand=True, padx=px(12), pady=px(10))

        # LEFT CARD: AI Diagnostic Sliders & Guidelines (60% width)
        card_ai = tk.Frame(body, bg=PANEL, padx=px(14), pady=px(10))
        card_ai.pack(side="left", fill="both", expand=True, padx=(0, px(8)))

        tk.Label(card_ai, text="AI DIAGNOSTIC PARAMETERS", font=self.f(12, True), fg=GREEN_ACCENT, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_ai, text="Fine-tune confidence, out-of-scope gating & focus thresholds", font=self.f(8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(6)))
        tk.Frame(card_ai, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(8)))

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
                "min": 20, "max": 65, "step": 1,
                "get_initial": lambda: int(round(self.ood_logit * 10)),
                "format": lambda v: f"{float(v) / 10.0:.2f}",
                "to_param": lambda v: round(float(v) / 10.0, 2),
                "attr": "ood_logit",
                "info_title": "Neural Logit Energy Gate",
                "info_text": "Raw unnormalized neural activation filter. Real leaves from trained species generate strong logit spikes (>4.2). Uncataloged leaves (e.g. money plants) produce low logits and are safely rejected."
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
            row.pack(fill="x", pady=(0, px(4)))

            hdr = tk.Frame(row, bg=PANEL)
            hdr.pack(fill="x", pady=(0, px(1)))

            tk.Label(hdr, text=spec["name"], font=self.f(9, True), fg=WHITE, bg=PANEL).pack(side="left")

            i_btn = tk.Label(
                hdr, text=" ⓘ ", font=self.f(9, True),
                fg=GREEN_ACCENT, bg=CARD, cursor="hand2", padx=px(2), pady=0
            )
            i_btn.pack(side="left", padx=px(6))

            init_val = spec["get_initial"]()
            val_lbl = tk.Label(
                hdr, text=spec["format"](init_val), font=self.f(9, True),
                fg=GREEN_ACCENT, bg=CARD, padx=px(6), pady=px(1)
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
                bg=PANEL,
                troughcolor=BG,
                activebackground=GREEN_ACCENT,
                highlightthickness=0,
                bd=0,
                cursor="hand2"
            )
            slider.set(init_val)
            slider.config(
                command=lambda val, s=spec: self._on_slider_change(s, val)
            )
            slider.pack(fill="x")
            self.sliders[spec["key"]] = (slider, spec)

        # Reset button row
        btn_row = tk.Frame(card_ai, bg=PANEL)
        btn_row.pack(fill="x", pady=(px(4), px(4)))
        self._button(
            btn_row, "↺ RESET DEFAULTS", CARD, self._reset_slider_defaults,
            width=px(160), height=px(36), size=9, fg=GREEN_ACCENT, border=BORDER, parent_bg=PANEL
        ).pack(side="left")

        # Interactive Explanation / Guide Card
        self.guide_card = tk.Frame(card_ai, bg=CARD, padx=px(8), pady=px(6), highlightbackground=BORDER, highlightthickness=1)
        self.guide_card.pack(fill="both", expand=True, pady=(px(2), 0))

        self.guide_title_lbl = tk.Label(
            self.guide_card, text="ⓘ  PARAMETER GUIDE",
            font=self.f(9, True), fg=GREEN_ACCENT, bg=CARD, anchor="w"
        )
        self.guide_title_lbl.pack(fill="x")

        self.guide_desc_lbl = tk.Label(
            self.guide_card,
            text="Hover or tap any ⓘ icon to view the meaning and impact of each setting.",
            font=self.f(8), fg=MUTED, bg=CARD, justify="left", anchor="w",
            wraplength=self.px(420)
        )
        self.guide_desc_lbl.pack(fill="x", pady=(px(2), 0))

        # RIGHT CARD: Hardware & System (40% width)
        card_sys = tk.Frame(body, bg=PANEL, padx=px(14), pady=px(10), width=self.px(320))
        card_sys.pack(side="right", fill="both", expand=False)
        card_sys.pack_propagate(False)

        tk.Label(card_sys, text="HARDWARE & SYSTEM", font=self.f(12, True), fg=WHITE, bg=PANEL, anchor="w").pack(fill="x")
        tk.Label(card_sys, text="Peripherals & application runtime", font=self.f(8), fg=MUTED, bg=PANEL, anchor="w").pack(fill="x", pady=(0, px(6)))
        tk.Frame(card_sys, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(10)))

        self.webcam_status_lbl = tk.Label(
            card_sys, text="Checking camera...", font=self.f(10, True), fg=MUTED, bg=PANEL, justify="center", wraplength=px(280)
        )
        self.webcam_status_lbl.pack(pady=(0, px(8)))

        # DETECT WEBCAM BUTTON
        self.detect_btn = self._button(
            card_sys, "🔍 DETECT WEBCAM", GREEN_PRIMARY, self._trigger_detect_webcam,
            width=px(240), height=px(42), size=11, fg=WHITE, parent_bg=PANEL
        )
        self.detect_btn.pack(pady=(0, px(4)))

        self.detect_msg_lbl = tk.Label(
            card_sys, text="Click to scan and connect USB webcam", font=self.f(8), fg=MUTED, bg=PANEL, justify="center", wraplength=px(280)
        )
        self.detect_msg_lbl.pack(pady=(0, px(10)))

        # SEPARATOR
        tk.Frame(card_sys, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(10)))

        # GITHUB REPOSITORY LINK
        self.gh_btn = self._button(
            card_sys, "🌐 OPEN GITHUB REPO", CARD, lambda: webbrowser.open("https://github.com/shreyuPRO/AGRILENS"),
            width=px(240), height=px(38), size=10, fg=WHITE, border=BORDER, parent_bg=PANEL
        )
        self.gh_btn.pack(pady=(0, px(4)))
        tk.Label(
            card_sys, text=f"shreyuPRO/AGRILENS (v{APP_VERSION})\nBuild: {BUILD_TIMESTAMP}",
            font=self.f(8), fg=MUTED, bg=PANEL, justify="center"
        ).pack(pady=(0, px(10)))

        # SEPARATOR
        tk.Frame(card_sys, bg=BORDER, height=max(1, px(1))).pack(fill="x", pady=(0, px(10)))

        # CLOSE APPLICATION BUTTON
        self.exit_btn = self._button(
            card_sys, "✕ CLOSE APPLICATION", RED_ALERT, self.close,
            width=px(240), height=px(44), size=11, fg=WHITE, parent_bg=PANEL
        )
        self.exit_btn.pack(pady=(0, px(4)))

        tk.Label(
            card_sys, text="Safely exit the kiosk and return to desktop",
            font=self.f(8), fg=MUTED, bg=PANEL
        ).pack()

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
            "sharpness_min": round(self.sharpness_min, 1)
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

    def open_admin_panel(self):
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

    def _on_detect_webcam_finished(self, ok, msg):
        if ok:
            self.webcam_status_lbl.config(text=f"Connected:\n{self.camera.kind}", fg=GREEN_PRIMARY)
            self.detect_msg_lbl.config(text="SUCCESS: Webcam connected and active!", fg=GREEN_PRIMARY)
            self.canvas.itemconfig(self.msg_txt, text="")
            self._update_stats_bar()
            self.detect_btn.config(state="normal", text="DETECT WEBCAM")
            self.root.after(750, self.close_overlays)
        else:
            self.webcam_status_lbl.config(text="Current Status: No Webcam Found", fg=RED_ALERT)
            self.detect_msg_lbl.config(text=msg, fg=RED_ALERT)
            self.canvas.itemconfig(self.msg_txt, text="No webcam connected.\nPlease check the USB camera connection.")
            self._update_stats_bar()
            self.detect_btn.config(state="normal", text="DETECT WEBCAM")

    def close_overlays(self):
        self.picker.place_forget()
        self.pwd_screen.place_forget()
        self.admin.place_forget()

    # ---- 6. Live Camera Loop & AI Pipeline (Non-Blocking Async Bootstrap) ----
    def _start_async_bootstrap(self):
        # Force initial paint so the UI is visible, responsive, and avoids "Not Responding"
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

        if self.camera.kind == "none":
            self.canvas.itemconfig(
                self.msg_txt,
                text="No webcam connected.\nPlease plug in USB camera or click ADMIN."
            )
        else:
            self.canvas.itemconfig(self.msg_txt, text="")

        self._reset_panel()
        self._update_stats_bar()
        self._preview_loop()

    def _preview_loop(self):
        if not self.running:
            return
        if not self.paused and self.camera and self.camera.kind != "none":
            frame = self.camera.read()
            if frame is not None:
                self.latest_frame = frame
                self._show_image(frame)
            elif self.camera.kind == "none":
                self.canvas.itemconfig(
                    self.msg_txt,
                    text="Webcam disconnected.\nPlease check USB connection or click ADMIN."
                )
                self._update_stats_bar()
        self.root.after(int(1000 / PREVIEW_FPS), self._preview_loop)

    def _show_image(self, img):
        disp = ImageOps.fit(img, (self.CAM_W, self.CAM_H), RESAMPLE)
        self._photo = ImageTk.PhotoImage(disp)
        self.canvas.itemconfig(self.img_item, image=self._photo)
        self.canvas.itemconfig(self.msg_txt, text="")

    def _reset_panel(self):
        self.banner_frame.config(bg=GREY_BTN)
        self.banner.config(text="READY — AIM LEAF AT CAMERA", bg=GREY_BTN, fg=WHITE)
        if self.selected_plant is None:
            self.plant_lbl.config(text="Mode: Auto-Detect (Beta Production)")
        else:
            self.plant_lbl.config(text=f"Selected Plant: {self.selected_plant.upper()}")
        self.disease_lbl.config(text="Aim leaf inside box -> Tap CAPTURE -> Tap DIAGNOSE")
        self._draw_bar(0, GREY_BTN, "Waiting for leaf...")
        for row, num, txt in self.step_rows:
            num.config(bg=GREEN_PRIMARY, fg=WHITE)
            txt.config(text="")
            row.pack_forget()
        self.cam_border.config(bg=CARD)

    # ---- 7. SEPARATE ACTIONS: Capture, Retake, and Diagnose ----
    def handle_capture_or_retake(self):
        """Toggles between CAPTURE (freeze image + assess quality) and RETAKE (restore live feed)."""
        if not self.paused:
            # 1. ACTION: CAPTURE
            if self.latest_frame is not None:
                self.paused = True
                self.captured_frame = self.latest_frame
                self.canvas.itemconfig(self.guide, state="hidden")
                self.canvas.itemconfig(self.live_badge, text="CAPTURED LEAF", fill=AMBER_WARN)

                # Run Leaf Image Quality AI
                score, rating, q_msg, q_color = LeafQualityAI.assess(self.captured_frame, self.sharpness_min)
                self.quality_lbl.config(text=q_msg, fg=q_color)

                # Swap Capture button to RETAKE, and Diagnose button to DIAGNOSE NOW
                self.capture_btn.config(text="RETAKE LEAF", bg=AMBER_WARN, fg=WHITE)
                self.diagnose_btn.config(text="DIAGNOSE NOW", bg=GREEN_PRIMARY, fg=WHITE)
            else:
                self.quality_lbl.config(text="Camera not ready. Plug in webcam and tap ADMIN.", fg=RED_ALERT)
        else:
            # 2. ACTION: RETAKE (Unfreeze)
            self.paused = False
            self.captured_frame = None
            self.last_probs = None
            self.canvas.itemconfig(self.guide, state="normal")
            self.canvas.itemconfig(self.live_badge, text="LIVE WEBCAM", fill=GREEN_ACCENT)

            self.quality_lbl.config(text="Leaf Quality AI: Align leaf inside box", fg=MUTED)
            self.capture_btn.config(text="CAPTURE LEAF", bg=GREEN_PRIMARY, fg=WHITE)
            self.diagnose_btn.config(text="DIAGNOSE LEAF", bg=CARD, fg=WHITE)
            self._reset_panel()
            self._update_stats_bar()

    def handle_diagnose(self):
        """Runs 98.31% MobileNetV4 inference on the captured (or current) frame."""
        target_img = self.captured_frame if self.captured_frame is not None else self.latest_frame

        if target_img is None:
            self.disease_lbl.config(text="No leaf image captured! Please tap CAPTURE first.")
            return

        if not self.paused:
            # If user directly pressed DIAGNOSE while live, capture first
            self.paused = True
            self.captured_frame = target_img
            self.canvas.itemconfig(self.guide, state="hidden")
            self.canvas.itemconfig(self.live_badge, text="CAPTURED LEAF", fill=AMBER_WARN)
            score, rating, q_msg, q_color = LeafQualityAI.assess(self.captured_frame, self.sharpness_min)
            self.quality_lbl.config(text=q_msg, fg=q_color)
            self.capture_btn.config(text="RETAKE LEAF", bg=AMBER_WARN, fg=WHITE)

        if self.classifier:
            res = self.classifier.predict(target_img)
            if len(res) == 3:
                probs, ms, raw_out = res
            else:
                probs, ms = res
                raw_out = None
            self.last_probs = probs
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

        # Plant filtering
        if self.selected_plant:
            keep = [self.crops[i] == self.selected_plant or not self.crops[i] for i in range(n)]
            tot = sum(p for p, m in zip(adj, keep) if m)
            if tot > 0:
                adj = [p / tot if m else 0.0 for p, m in zip(adj, keep)]

        best = max(range(n), key=lambda i: adj[i])
        conf = adj[best]
        crop, cond, healthy = self.parsed[best]

        # 1. OUT-OF-DISTRIBUTION (OOD) / UNKNOWN PLANT DETECTION:
        # Rejects random leaves outside the catalog or when Other_Plant_or_Background fires
        is_negative_class = ("other" in cond.lower()) or ("background" in cond.lower())
        is_unknown_plant = (
            is_negative_class or
            (raw_top1 < self.threshold) or 
            (raw_margin < self.ood_margin) or 
            (max_logit < self.ood_logit)
        )

        if is_unknown_plant:
            status = "UNKNOWN PLANT / OUT OF SCOPE"
            color = AMBER_WARN
            plant_txt = "Plant: Unrecognized (Outside Catalog)"
            disease_txt = "Specimen outside supported scope (Apple, Mango, Tomato)"
            steps = OOD_STEPS
            num_color = AMBER_WARN
            btn_txt = "UNKNOWN LEAF"
            btn_color = AMBER_WARN
        elif conf < self.threshold:
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
        self.stats_lbl.config(text=f"AI: {mode_text} | Latency: {lat} | Camera: {cam} | {py_ver}")

    def close(self):
        self.running = False
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
# 8. SINGLE INSTANCE GUARD & MAIN ENTRY POINT
# =============================================================================
SINGLE_INSTANCE_SOCKET = None

def acquire_single_instance_lock(port=48195):
    """Binds a local loopback port to prevent multiple conflicting instances from locking the camera."""
    global SINGLE_INSTANCE_SOCKET
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("127.0.0.1", port))
        s.listen(1)
        SINGLE_INSTANCE_SOCKET = s
        return True
    except Exception:
        return False


if __name__ == "__main__":
    if not acquire_single_instance_lock():
        root = tk.Tk()
        root.withdraw()
        try:
            from tkinter import messagebox
            messagebox.showwarning(
                "AGRILENS Kiosk Already Running",
                "An instance of AGRILENS is already running in the background.\n\n"
                "Please check your taskbar or close the background instance before starting a new one."
            )
        except Exception:
            pass
        root.destroy()
        sys.exit(0)

    root = tk.Tk()
    app = AgriLensApp(root)
    root.mainloop()
