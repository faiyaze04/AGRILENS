#!/bin/bash
# AGRILENS - complete backup of the CURRENT kiosk installation (normally 4.9.4) before 5.0.0 is installed beside it.
# Changes nothing on the kiosk except creating the backup folder. Run as the kiosk user (not sudo).
#   bash pi_backup_current.sh
# Environment overrides (for testing): AGRILENS_OLD_DIR (default ~/AGRILENS_RaspberryPi), AGRILENS_BACKUP_ROOT (default ~/AGRILENS_backups)
set -u
APP="${AGRILENS_OLD_DIR:-$HOME/AGRILENS_RaspberryPi}"
ROOT="${AGRILENS_BACKUP_ROOT:-$HOME/AGRILENS_backups}"
STAMP=$(date +%Y%m%d_%H%M%S)
[ -f "$APP/main.py" ] || { echo "ERROR: no AGRILENS installation at $APP"; exit 1; }
VER=$(grep -m1 '^APP_VERSION' "$APP/main.py" | cut -d'"' -f2)
DEST="$ROOT/v${VER}_$STAMP"
mkdir -p "$DEST/home_files" "$DEST/system" || exit 1
echo "[backup] installation $APP (version $VER) -> $DEST"

# 1. The whole application folder: code, model, labels, config, logos, samples, any rollback copies.
tar -C "$(dirname "$APP")" -czf "$DEST/app_folder.tar.gz" "$(basename "$APP")" || { echo "ERROR: tar failed"; exit 1; }
(cd "$APP" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$DEST/app_folder.sha256"

# 2. Per-user files the application reads or writes (shared by every installed version).
: > "$DEST/home_files_present.list"; : > "$DEST/home_files_absent.list"
for f in .agrilens_kiosk_config.json .agrilens_ota_hold .config/autostart/agrilens.desktop .config/wayfire.ini .config/labwc/autostart; do
  if [ -e "$HOME/$f" ]; then
    mkdir -p "$DEST/home_files/$(dirname "$f")"; cp -a "$HOME/$f" "$DEST/home_files/$f"; echo "$f" >> "$DEST/home_files_present.list"
  else
    echo "$f" >> "$DEST/home_files_absent.list"
  fi
done

# 3. System pieces (copied, never changed).
for f in /etc/systemd/system/agrilens-ota.service /etc/systemd/system/agrilens-ota.timer; do
  if [ -e "$f" ]; then cp -a "$f" "$DEST/system/"; fi
done
(systemctl is-enabled agrilens-ota.service 2>&1 || true) > "$DEST/system/agrilens-ota.service.enabled.txt"
(crontab -l 2>&1 || true) > "$DEST/system/crontab.txt"
(python3 -m pip freeze 2>&1 || true) > "$DEST/system/pip_freeze.txt"
(cat /proc/device-tree/model 2>/dev/null; echo; uname -a) > "$DEST/system/device.txt"

cat > "$DEST/BACKUP_INFO.txt" <<EOF
AGRILENS installation backup
created:        $(date -Is 2>/dev/null || date)
host:           $(hostname)
user:           $(whoami)
installation:   $APP
APP_VERSION:    $VER
model sha256:   $(sha256sum "$APP/agrilens.onnx" 2>/dev/null | cut -d' ' -f1)
main.py sha256: $(sha256sum "$APP/main.py" | cut -d' ' -f1)
Restore with:   bash pi_restore_previous.sh "$DEST"
EOF
(cd "$DEST" && find . -type f ! -name BACKUP_SHA256SUMS -print0 | sort -z | xargs -0 sha256sum) > "$DEST/BACKUP_SHA256SUMS"

# 4. Prove the archive can be restored: unpack to a temporary folder and check every file hash.
TMP=$(mktemp -d)
tar -C "$TMP" -xzf "$DEST/app_folder.tar.gz" && (cd "$TMP/$(basename "$APP")" && sha256sum -c --quiet "$DEST/app_folder.sha256")
OK=$?
rm -rf "$TMP"
if [ $OK -ne 0 ]; then echo "ERROR: backup verification FAILED - do not continue"; exit 1; fi
echo "$DEST" > "$ROOT/LATEST_BACKUP"
echo "[backup] verified: $(wc -l < "$DEST/app_folder.sha256") application files, user files: $(tr '\n' ' ' < "$DEST/home_files_present.list")"
echo "[backup] OK -> $DEST"
echo "[backup] Also copy this folder to a USB drive:  cp -a \"$DEST\" /media/\$USER/<drive>/"
