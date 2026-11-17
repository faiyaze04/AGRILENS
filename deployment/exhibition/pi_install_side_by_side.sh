#!/bin/bash
# AGRILENS 5.0.0 - controlled installation BESIDE the existing installation. The existing ~/AGRILENS_RaspberryPi is never modified.
#   bash pi_install_side_by_side.sh            (expects the kit folder layout: ./AGRILENS_5.0.0 next to this script)
# What it does:
#   1. refuses unless a verified backup exists (pi_backup_current.sh);
#   2. verifies every file of the 5.0.0 package against its SHA256SUMS and the release id;
#   3. copies it to ~/AGRILENS_5.0.0 (refuses to overwrite), re-verifies the copy;
#   4. creates ~/.agrilens_ota_hold so the 5.0.0 code never runs an automatic boot update.
# It does NOT start the kiosk and does NOT change what starts at boot. Starting 5.0.0 once (or exhibition_launcher.sh --autostart)
# makes 5.0.0 the boot application; pi_restore_previous.sh undoes that.
# IMPORTANT: copy the kit to the SD card first. Never start AGRILENS directly from a USB drive (/media or /mnt): the application
# then copies itself over ~/AGRILENS_RaspberryPi.
# Environment overrides (for testing): AGRILENS_OLD_DIR, AGRILENS_NEW_DIR, AGRILENS_BACKUP_ROOT
set -u
KIT="$(cd "$(dirname "$0")" && pwd)"
SRC="${1:-$KIT/AGRILENS_5.0.0}"
OLD="${AGRILENS_OLD_DIR:-$HOME/AGRILENS_RaspberryPi}"
NEW="${AGRILENS_NEW_DIR:-$HOME/AGRILENS_5.0.0}"
ROOT="${AGRILENS_BACKUP_ROOT:-$HOME/AGRILENS_backups}"
fail() { echo "ERROR: $*"; exit 1; }

case "$KIT" in /media/*|/mnt/*) fail "the kit is on a removable drive ($KIT). Copy it to the SD card first: cp -a \"$KIT\" ~/AGRILENS_exhibition_kit";; esac
[ "$(cd "$(dirname "$NEW")" 2>/dev/null && pwd)/$(basename "$NEW")" != "$(cd "$OLD" 2>/dev/null && pwd)" ] || fail "target $NEW is the existing installation"

# 1. backup present and intact
[ -f "$ROOT/LATEST_BACKUP" ] || fail "no backup found. Run: bash $KIT/pi_backup_current.sh"
BK="$(cat "$ROOT/LATEST_BACKUP")"
(cd "$BK" && sha256sum -c --quiet BACKUP_SHA256SUMS) || fail "backup $BK does not verify"
echo "[install] backup verified: $BK"

# 2. package integrity and identity
[ -f "$SRC/SHA256SUMS" ] || fail "package not found at $SRC"
(cd "$SRC" && sha256sum -c --quiet SHA256SUMS) || fail "package files do not match SHA256SUMS"
grep -q '"release": "AGRILENS-5.0.0"' "$SRC/RELEASE_MANIFEST.json" || fail "package is not release AGRILENS-5.0.0"
MODEL_SHA=$(sha256sum "$SRC/agrilens.onnx" | cut -d' ' -f1)
grep -q "^MODEL_SHA256 = \"$MODEL_SHA\"" "$SRC/main.py" || fail "main.py does not name the packaged model"
echo "[install] package verified (model $MODEL_SHA)"

# 3. copy beside the existing installation
[ -e "$NEW" ] && fail "$NEW already exists. Remove or rename it first (mv \"$NEW\" \"$NEW.old\")."
cp -a "$SRC" "$NEW" || fail "copy failed"
(cd "$NEW" && sha256sum -c --quiet SHA256SUMS) || fail "installed copy does not verify"
mkdir -p "$NEW/exhibition"
for f in exhibition_launcher.sh pi_benchmark.sh pi_restore_previous.sh pi_backup_current.sh EXHIBITION_TEST_CHECKLIST.md benchmark_pi5.py collect_pi_environment.sh; do
  [ -f "$KIT/$f" ] && cp -a "$KIT/$f" "$NEW/exhibition/"
done
chmod +x "$NEW"/*.sh "$NEW"/exhibition/*.sh 2>/dev/null

# 4. no automatic update from the 5.0.0 code
touch "$HOME/.agrilens_ota_hold"

echo "[install] AGRILENS 5.0.0 installed at $NEW. Existing installation untouched: $OLD"
echo "[install] Boot application unchanged. Next: bash $NEW/exhibition/pi_benchmark.sh, then the checklist in $NEW/exhibition/EXHIBITION_TEST_CHECKLIST.md"
