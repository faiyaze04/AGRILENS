# AGRILENS 5.0.0 – EXPISCOR 2026 exhibition kit

For the exhibition Raspberry Pi 5 that currently runs AGRILENS 4.9.4. Nothing here uses the internet or GitHub. 4.9.4 is not overwritten.

## On the Pi (keyboard or SSH, as the kiosk user)

```bash
# 0. copy the kit from the USB drive to the SD card (never run AGRILENS from the USB drive itself)
cp -a /media/$USER/<drive>/AGRILENS_EXPISCOR2026_kit ~/AGRILENS_exhibition_kit
cd ~/AGRILENS_exhibition_kit && sha256sum -c --quiet KIT_SHA256SUMS && echo KIT OK

# 1. full backup of the current installation (4.9.4), then copy the backup folder to the USB drive
bash pi_backup_current.sh

# 2. install 5.0.0 beside it (~/AGRILENS_5.0.0); 4.9.4 and the boot setting stay as they are
bash pi_install_side_by_side.sh

# 3. benchmark both versions with the kiosk stopped
bash ~/AGRILENS_5.0.0/exhibition/pi_benchmark.sh

# 4. rehearse the rollback once
cd ~/AGRILENS_5.0.0 && python3 main.py          # try it, then close it (Escape)
bash ~/AGRILENS_5.0.0/exhibition/pi_restore_previous.sh && sudo reboot    # must come back as 4.9.4

# 5. exhibition mode: 5.0.0 through the launcher (offline, logged, restarts itself)
bash ~/AGRILENS_5.0.0/exhibition/exhibition_launcher.sh --autostart      # then reboot once to confirm
```

Then work through `EXHIBITION_TEST_CHECKLIST.md`.

## During the exhibition

- Keep Wi-Fi off. Do not press **☁ OTA UPDATE** in Admin.
- The Admin console has no password and contains **✕ CLOSE APPLICATION**. If a visitor closes the kiosk, the launcher restarts it within a few seconds; gate settings return to the calibrated values at every start.
- Camera unplugged → the kiosk switches to File Mode. After plugging it back: ADMIN → 📷 CAMERA CONTROL PANEL → 🔍 DETECT WEBCAM (or wait for the screensaver and touch the screen).
- To stop the kiosk on purpose: `touch ~/.agrilens_stop`, then close it.
- Logs: `~/AGRILENS_logs/` (newest file). Send it with any problem report.

## If 5.0.0 misbehaves on the day

```bash
bash ~/AGRILENS_5.0.0/exhibition/pi_restore_previous.sh && sudo reboot
```

This returns to 4.9.4 with its own settings in about a minute. The backup (`~/AGRILENS_backups/`) and the USB copy stay available.
