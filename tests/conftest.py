"""
Shared fixtures. The tests exercise the application file selected by AGRILENS_APP_PATH
(default: the frozen legacy AGRILENS_RaspberryPi/main.py) and never modify it.

Environment variables (all optional):
  AGRILENS_APP_PATH      path to the application file under test
  AGRILENS_SAMPLES_DIR   folder with the 24 sample images (default: <app dir>/diagnosis_samples)
"""
import os
import sys

import pytest

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import app_harness as H  # noqa: E402

BASELINE_DIR = os.path.join(ROOT, "tests", "baseline")


@pytest.fixture(scope="session")
def app():
    return H.load_app()


@pytest.fixture(scope="session")
def ort():
    return pytest.importorskip("onnxruntime")


@pytest.fixture(scope="session")
def classifier(app, ort):
    clf = app.Classifier(app.MODEL_PATH, app.LABELS_PATH)
    assert clf.session is not None, "Classifier fell back to DEMO mode: %s" % clf.error_reason
    return clf


@pytest.fixture(scope="session")
def labels(app):
    with open(app.LABELS_PATH, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip()]


@pytest.fixture(scope="session")
def samples():
    found = H.sample_images()
    assert found, "no sample images found; set AGRILENS_SAMPLES_DIR"
    return found


@pytest.fixture(scope="session")
def golden():
    import json
    with open(os.path.join(BASELINE_DIR, "golden_predictions.json"), encoding="utf-8") as f:
        return json.load(f)
