"""
Exhibition kit scripts (deployment/exhibition/*.sh), run with bash against a fake kiosk home folder:
backup of a 4.9.4 installation -> side-by-side 5.0.0 installation -> simulated 5.0.0 use -> restore, which must give back the
4.9.4 folder and every per-user file byte for byte. Also the launcher's crash-restart limit, normal exit and health log.
Raspberry Pi specifics (vcgencmd, systemd, pkill) are absent here and are not exercised.
"""
import hashlib
import io
import os
import shutil
import subprocess
import sys
import zipfile

import pytest

from conftest import ROOT

KIT_SRC = os.path.join(ROOT, "deployment", "exhibition")
PKG = os.path.join(ROOT, "AGRILENS_RaspberryPi")
LEGACY = os.path.join(ROOT, "tests", "regression", "baseline", "legacy_4.9.4")
PROD_MODEL = os.path.join(ROOT, "models", "production", "agrilens-24class-4.9.4", "agrilens.onnx")
# The EXPISCOR 2026 kit is built for release 5.0.0 only (folder names, checklist, release-id check in pi_install_side_by_side.sh).
# Since 5.1.0 the working package is newer, so the kit is tested with the published 5.0.0 package (GitHub main at 5.0.0).
RELEASE_5_0_0_COMMIT = "9017320564592154fc7bc32f07244e23a9ff0a8c"


def _extract_5_0_0_package(dest):
    r = subprocess.run(["git", "-C", ROOT, "archive", "--format=zip", RELEASE_5_0_0_COMMIT, "AGRILENS_RaspberryPi"], capture_output=True)
    if r.returncode != 0:
        pytest.skip("5.0.0 release commit not available: " + r.stderr.decode(errors="replace").strip())
    with zipfile.ZipFile(io.BytesIO(r.stdout)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            rel = info.filename.split("/", 1)[1]
            out = os.path.join(dest, *rel.split("/"))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(z.read(info))


def _bash():
    for c in (shutil.which("bash"), r"C:\Program Files\Git\bin\bash.exe", "/bin/bash"):
        if c and os.path.exists(c):
            return c
    return None


pytestmark = pytest.mark.skipif(_bash() is None, reason="bash not available")


def posix(p):
    if os.name != "nt":
        return str(p)
    return subprocess.run([_bash(), "-c", 'cygpath -u "$0"', str(p)], capture_output=True, text=True).stdout.strip()


def tree_hashes(d):
    out = {}
    for dp, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(dp, f)
            out[os.path.relpath(p, d)] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out


def run(script, home, *args, env_extra=None, timeout=120):
    env = dict(os.environ, HOME=posix(home))
    env.update(env_extra or {})
    return subprocess.run([_bash(), posix(script)] + list(args), capture_output=True, text=True, env=env, timeout=timeout)


@pytest.fixture()
def kiosk(tmp_path):
    home = tmp_path / "home"
    old = home / "AGRILENS_RaspberryPi"
    (old / "logos").mkdir(parents=True)
    for f in ("main.py", "ota_update.sh", "labels.txt"):
        shutil.copy(os.path.join(LEGACY, f), old / f)
    shutil.copy(PROD_MODEL, old / "agrilens.onnx")
    for f in ("agrilens_logo.jpg", "gundecha_logo.png"):
        shutil.copy(os.path.join(ROOT, "application", "logos", f), old / "logos" / f)
    (old / "kiosk_config.json").write_text('{"ood_logit": 6.0}\n')
    (home / ".agrilens_kiosk_config.json").write_text('{"ood_logit": 6.0, "language": "HI"}\n')
    (home / ".config" / "autostart").mkdir(parents=True)
    (home / ".config" / "autostart" / "agrilens.desktop").write_text("[Desktop Entry]\nExec=old 4.9.4\n")
    kit = tmp_path / "kit"
    shutil.copytree(KIT_SRC, kit)
    _extract_5_0_0_package(str(kit / "AGRILENS_5.0.0"))
    return home, old, kit


def user_files(home):
    return {f: (home / f).read_bytes() for f in (".agrilens_kiosk_config.json", ".config/autostart/agrilens.desktop") if (home / f).exists()}


def test_backup_install_restore_round_trip(kiosk):
    home, old, kit = kiosk
    before_old, before_user = tree_hashes(old), user_files(home)
    r = run(kit / "pi_install_side_by_side.sh", home)
    assert r.returncode != 0 and "no backup found" in r.stdout          # refuses without a backup
    r = run(kit / "pi_backup_current.sh", home)
    assert r.returncode == 0 and "[backup] OK" in r.stdout, r.stdout + r.stderr
    r = run(kit / "pi_install_side_by_side.sh", home)
    assert r.returncode == 0 and "installed at" in r.stdout, r.stdout + r.stderr
    new = home / "AGRILENS_5.0.0"
    assert tree_hashes(old) == before_old                                 # existing installation untouched
    assert (new / "exhibition" / "exhibition_launcher.sh").exists() and (home / ".agrilens_ota_hold").exists()
    assert hashlib.sha256((new / "agrilens.onnx").read_bytes()).hexdigest() == hashlib.sha256((kiosk[2] / "AGRILENS_5.0.0" / "agrilens.onnx").read_bytes()).hexdigest()
    r = run(kit / "pi_install_side_by_side.sh", home)
    assert r.returncode != 0 and "already exists" in r.stdout             # never overwrites
    # simulate running 5.0.0: it rewrites the boot entry and the shared settings; a mistake also changes the old folder
    (home / ".agrilens_kiosk_config.json").write_text('{"ood_logit": 2.1, "calibration_model_sha256": "776d"}\n')
    (home / ".config" / "autostart" / "agrilens.desktop").write_text("[Desktop Entry]\nExec=new 5.0.0\n")
    (old / "kiosk_config.json").write_text('{"changed": true}\n')
    r = run(new / "exhibition" / "pi_restore_previous.sh", home)
    assert r.returncode == 0 and "[restore] done" in r.stdout, r.stdout + r.stderr
    assert tree_hashes(old) == before_old
    assert user_files(home) == before_user
    assert not (home / ".agrilens_ota_hold").exists()                    # did not exist before 5.0.0
    assert (new / "main.py").exists()                                     # 5.0.0 left in place


def test_install_refuses_a_tampered_package(kiosk):
    home, old, kit = kiosk
    assert run(kit / "pi_backup_current.sh", home).returncode == 0
    with open(kit / "AGRILENS_5.0.0" / "labels.txt", "a") as f:
        f.write("Extra_class\n")
    r = run(kit / "pi_install_side_by_side.sh", home)
    assert r.returncode != 0 and "do not match SHA256SUMS" in r.stdout
    assert not (home / "AGRILENS_5.0.0").exists()


def _fake_app(tmp_path, body):
    d = tmp_path / "fakeapp"
    d.mkdir()
    (d / "main.py").write_text('APP_VERSION = "5.0.0"\nimport sys, time\n' + body + "\n")
    (d / "agrilens.onnx").write_bytes(b"x")
    return d


def _launcher_env(tmp_path, app_dir, every="1"):
    logs = tmp_path / "logs"
    return logs, {"AGRILENS_APP_DIR": posix(app_dir), "AGRILENS_LOG_DIR": posix(logs), "AGRILENS_HEALTH_SECONDS": every, "AGRILENS_PYTHON": posix(sys.executable)}


def _log_text(logs):
    files = sorted(os.listdir(logs))
    return open(os.path.join(logs, files[-1]), encoding="utf-8", errors="replace").read()


def test_launcher_stops_after_repeated_crashes(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    app = _fake_app(tmp_path, 'print("crash"); sys.exit(3)')
    logs, env = _launcher_env(tmp_path, app)
    env["AGRILENS_RESTART_DELAY"] = "1"
    r = run(os.path.join(KIT_SRC, "exhibition_launcher.sh"), home, env_extra=env, timeout=120)
    text = _log_text(logs)
    assert r.returncode == 1 and text.count("starting kiosk") == 6 and "more than 5 crashes" in text, text
    assert (home / ".agrilens_ota_hold").exists()


def test_launcher_restarts_a_closed_kiosk_until_stop_file_and_resets_gates(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agrilens_kiosk_config.json").write_text('{"ood_logit": 3.5, "confidence_threshold": 0.7, "calibration_model_sha256": "abc", "language": "HI"}')
    # 1st run: a visitor taps CLOSE APPLICATION (exit 0) -> restarted; 2nd run: the operator has created ~/.agrilens_stop
    body = ('import os, pathlib\nc = pathlib.Path("count.txt"); n = int(c.read_text()) + 1 if c.exists() else 1; c.write_text(str(n))\n'
            'time.sleep(2.5); print("run", n)\n'
            'if n >= 2: pathlib.Path(os.environ["HOME_WIN"], ".agrilens_stop").write_text("stop")\nsys.exit(0)')
    app = _fake_app(tmp_path, body)
    logs, env = _launcher_env(tmp_path, app)
    env.update({"AGRILENS_RESTART_DELAY": "1", "HOME_WIN": str(home)})
    r = run(os.path.join(KIT_SRC, "exhibition_launcher.sh"), home, env_extra=env, timeout=90)
    text = _log_text(logs)
    assert r.returncode == 0 and text.count("starting kiosk") == 2 and "closed normally" in text and "stop file present" in text, text
    assert "health temp=" in text and "run 2" in text
    import json
    cfg = json.loads((home / ".agrilens_kiosk_config.json").read_text())
    assert cfg == {"language": "HI"} and not (home / ".agrilens_stop").exists()
