#!/bin/bash
# AGRILENS - return the kiosk to the installation saved by pi_backup_current.sh (normally 4.9.4).
#   bash pi_restore_previous.sh            uses the newest backup (~/AGRILENS_backups/LATEST_BACKUP)
#   bash pi_restore_previous.sh <backup folder>
# Stops the 5.0.0 kiosk and launcher; restores the previous application folder if anything in it changed; restores the per-user files
# (settings, boot autostart, OTA hold) exactly as they were; leaves ~/AGRILENS_5.0.0 in place (delete it yourself later).
# Nothing is deleted: files replaced by the restore are moved to <backup>/replaced_at_restore_<time>/.
# Environment overrides (for testing): AGRILENS_OLD_DIR, AGRILENS_NEW_DIR, AGRILENS_BACKUP_ROOT
set -u
OLD="${AGRILENS_OLD_DIR:-$HOME/AGRILENS_RaspberryPi}"
NEW="${AGRILENS_NEW_DIR:-$HOME/AGRILENS_5.0.0}"
ROOT="${AGRILENS_BACKUP_ROOT:-$HOME/AGRILENS_backups}"
BK="${1:-$(cat "$ROOT/LATEST_BACKUP" 2>/dev/null)}"
fail() { echo "ERROR: $*"; exit 1; }
[ -n "$BK" ] && [ -f "$BK/BACKUP_SHA256SUMS" ] || fail "backup not found ($BK)"
(cd "$BK" && sha256sum -c --quiet BACKUP_SHA256SUMS) || fail "backup $BK does not verify; restore it by hand from app_folder.tar.gz"
ASIDE="$BK/replaced_at_restore_$(date +%Y%m%d_%H%M%S)"; mkdir -p "$ASIDE"
echo "[restore] from $BK"

# 1. stop the 5.0.0 kiosk and the exhibition launcher
pkill -f "exhibition_launcher.sh" 2>/dev/null
pkill -f "$NEW/main.py" 2>/dev/null; pkill -f "AGRILENS_5.0.0.*main.py" 2>/dev/null
pkill -f "$OLD/main.py" 2>/dev/null
sleep 2

# 2. application folder: verify, restore from the archive only if it changed
if [ -d "$OLD" ] && (cd "$OLD" && sha256sum -c --quiet "$BK/app_folder.sha256" >/dev/null 2>&1); then
  echo "[restore] $OLD unchanged since the backup"
else
  echo "[restore] $OLD differs from the backup or is missing -> restoring it from app_folder.tar.gz"
  [ -d "$OLD" ] && mv "$OLD" "$ASIDE/$(basename "$OLD")"
  tar -C "$(dirname "$OLD")" -xzf "$BK/app_folder.tar.gz" || fail "unpack failed"
  (cd "$OLD" && sha256sum -c --quiet "$BK/app_folder.sha256") || fail "restored folder does not verify"
fi

# 3. per-user files exactly as at backup time
while read -r f; do
  [ -z "$f" ] && continue
  if [ -e "$HOME/$f" ] && ! cmp -s "$HOME/$f" "$BK/home_files/$f"; then mkdir -p "$ASIDE/home_files/$(dirname "$f")"; mv "$HOME/$f" "$ASIDE/home_files/$f"; fi
  mkdir -p "$HOME/$(dirname "$f")"; cp -a "$BK/home_files/$f" "$HOME/$f"
done < "$BK/home_files_present.list"
while read -r f; do   # files that did not exist before 5.0.0 (for example the OTA hold) are moved aside
  [ -z "$f" ] && continue
  if [ -e "$HOME/$f" ]; then mkdir -p "$ASIDE/home_files/$(dirname "$f")"; mv "$HOME/$f" "$ASIDE/home_files/$f"; fi
done < "$BK/home_files_absent.list"

V=$(grep -m1 '^APP_VERSION' "$OLD/main.py" | cut -d'"' -f2)
echo "[restore] done: $OLD (version $V) is the boot application again; settings restored."
echo "[restore] Replaced files kept in $ASIDE. 5.0.0 left at $NEW."
echo "[restore] Start now with: cd \"$OLD\" && python3 main.py   (or reboot)"
echo "[restore] NOTE: 4.9.4 checks GitHub for updates when it starts; GitHub main still serves 4.9.4, so nothing changes."
