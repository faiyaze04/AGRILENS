#!/usr/bin/env python3
"""Build the EXPISCOR 2026 exhibition kit (copied to the Pi by USB drive; nothing is published).
  python deployment/exhibition/build_exhibition_kit.py --out <dir>
Output: <dir>/AGRILENS_EXPISCOR2026_kit/ and <dir>/AGRILENS_EXPISCOR2026_kit.zip
  AGRILENS_5.0.0/                 the release package (byte copy of AGRILENS_RaspberryPi/, verified against its SHA256SUMS)
  pi_backup_current.sh, pi_install_side_by_side.sh, pi_benchmark.sh, pi_restore_previous.sh, exhibition_launcher.sh
  benchmark_pi5.py, collect_pi_environment.sh, EXHIBITION_TEST_CHECKLIST.md, README_KIT.md, KIT_SHA256SUMS"""
import argparse, hashlib, os, shutil, zipfile
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.join(R, "deployment", "exhibition"); PKG = os.path.join(R, "AGRILENS_RaspberryPi")
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
for ln in open(os.path.join(PKG, "SHA256SUMS"), encoding="utf-8"):
    h, p = ln.rstrip("\n").split("  ", 1); assert sha(os.path.join(PKG, p)) == h, p
kit = os.path.join(a.out, "AGRILENS_EXPISCOR2026_kit")
if os.path.exists(kit): shutil.rmtree(kit)
shutil.copytree(PKG, os.path.join(kit, "AGRILENS_5.0.0"))
files = ["pi_backup_current.sh", "pi_install_side_by_side.sh", "pi_benchmark.sh", "pi_restore_previous.sh", "exhibition_launcher.sh", "EXHIBITION_TEST_CHECKLIST.md", "README_KIT.md"]
for f in files:
    b = open(os.path.join(HERE, f), "rb").read()
    assert not (f.endswith(".sh") and b"\r" in b), f"{f} has CR line endings"
    open(os.path.join(kit, f), "wb").write(b)
for f in ("benchmark_pi5.py", "collect_pi_environment.sh"):
    open(os.path.join(kit, f), "wb").write(open(os.path.join(R, "tools", "validation", f), "rb").read().replace(b"\r\n", b"\n"))
sums = []
for dp, _, fs in os.walk(kit):
    for f in fs:
        p = os.path.join(dp, f); rel = os.path.relpath(p, kit).replace(os.sep, "/")
        if rel != "KIT_SHA256SUMS": sums.append(f"{sha(p)}  {rel}\n")
open(os.path.join(kit, "KIT_SHA256SUMS"), "w", newline="\n").write("".join(sorted(sums, key=lambda s: s.split("  ", 1)[1])))
z = kit + ".zip"
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    for dp, _, fs in os.walk(kit):
        for f in fs:
            p = os.path.join(dp, f); info = zipfile.ZipInfo.from_file(p, os.path.relpath(p, a.out).replace(os.sep, "/"))
            if f.endswith(".sh"): info.external_attr = (0o755 << 16)
            with open(p, "rb") as fh: zf.writestr(info, fh.read(), zipfile.ZIP_DEFLATED)
print(kit, len(sums), "files;", z, os.path.getsize(z), "bytes; zip sha256", sha(z))
