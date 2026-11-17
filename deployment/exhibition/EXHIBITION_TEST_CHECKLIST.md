# AGRILENS 5.0.0 exhibition test checklist (Raspberry Pi 5 + Logitech C270 + Waveshare 7" touch)

Fill in on the exhibition Pi. Record **Pass / Fail / Not done** and a short note. A test counts only if it was performed on the Pi.

Kit folder on the Pi: `~/AGRILENS_exhibition_kit` (copied from USB; never run AGRILENS from the USB drive itself).

## 0. Backup and installation (in this order)

| # | Step | Command / action | Expected | Result |
|---|---|---|---|---|
| 0.1 | Back up current installation | `bash ~/AGRILENS_exhibition_kit/pi_backup_current.sh` | ends with `[backup] OK`; copy the backup folder to a USB drive | |
| 0.2 | Install 5.0.0 beside it | `bash ~/AGRILENS_exhibition_kit/pi_install_side_by_side.sh` | `installed at ~/AGRILENS_5.0.0`; `~/AGRILENS_RaspberryPi` untouched | |
| 0.3 | Benchmark (kiosk stopped) | `bash ~/AGRILENS_5.0.0/exhibition/pi_benchmark.sh` | both JSON files `valid_for_pi5_reporting: true` | |
| 0.4 | Rollback rehearsal | start 5.0.0 once (`cd ~/AGRILENS_5.0.0 && python3 main.py`, then Escape), then `bash ~/AGRILENS_5.0.0/exhibition/pi_restore_previous.sh`, reboot | Pi boots into 4.9.4 with its old settings | |
| 0.5 | Switch to 5.0.0 for the exhibition | `bash ~/AGRILENS_5.0.0/exhibition/exhibition_launcher.sh --autostart`, then reboot | Pi boots into 5.0.0; log in `~/AGRILENS_logs/` | |

## 1. Performance (from 0.3)

| Measure | Go limit (exhibition) | 5.0.0 | 4.9.4 |
|---|---|---|---|
| Median diagnosis time | ≤ 1.5 s | | |
| P95 diagnosis time | ≤ 3 s | | |
| Peak memory (RSS) | ≤ 1 GB | | |
| Memory trend during soak | ≤ 20 MB per 10 min | | |
| Max CPU temperature during soak | ≤ 80 °C, no throttling flags | | |

## 2. Functional tests with the C270 and the touchscreen

| # | Test | Expected | Result |
|---|---|---|---|
| 2.1 | Cold start (power on) | logo splash, then Live Mode within 60 s; launcher log shows `starting kiosk` and the line `rejection gates from calibration of AGRILENS-MULTICROP 1.0.0` | |
| 2.2 | Live camera | C270 picture, focus meter moves; set focus ring once | |
| 2.3 | Capture and diagnose a real leaf | CAPTURE LEAF → adjust box → DIAGNOSE NOW → result screen within a few seconds | |
| 2.4 | File Mode, all 24 samples | MODE ▾ → FILE MODE → each sample in `diagnosis_samples/` gives the matching crop and condition (desktop: 24/24) | |
| 2.5 | Crop selector | SELECT CROP → each of APPLE, MANGO, POTATO, TOMATO and AUTO | |
| 2.6 | Cautionary results | plain table / hand / blank paper / phone screen with text → "UNKNOWN PLANT / OUT OF SCOPE" or "LOW CONFIDENCE — PLEASE RETAKE", never a disease | |
| 2.7 | Touch navigation | every button reachable with a finger; crop handles draggable; double-tap selects full image; no mouse or keyboard needed | |
| 2.8 | Hindi / English | 🌐 toggle switches instructions, buttons, crop and disease names and the 4 recommendation steps; choice survives a restart | |
| 2.9 | Admin | ADMIN opens; sliders show confidence 40%, margin 12%, logit 2.10; RESET DEFAULTS returns to these; close Admin | |
| 2.10 | Screensaver | after 3 min idle the logo screensaver appears and the camera turns off; a touch brings back Live Mode | |
| 2.11 | Offline | Wi-Fi off (and cable unplugged), reboot: kiosk starts and diagnoses normally; no error dialog | |
| 2.12 | Camera unplug | unplug C270 during Live Mode → kiosk switches to File Mode, keeps running | |
| 2.13 | Camera re-plug | plug back in, then either ADMIN → 📷 CAMERA CONTROL PANEL → 🔍 DETECT WEBCAM, or wait for the screensaver and touch | Live Mode returns. (The kiosk does not reconnect by itself.) | |
| 2.14 | Crash recovery | `pkill -9 -f AGRILENS_5.0.0/main.py` | launcher restarts the kiosk within ~5 s; log shows `exited with code` and `restarting` | |
| 2.15 | Power cut | pull the power while the kiosk runs, power on | kiosk starts again with its settings | |
| 2.16 | Soak | leave running ≥ 2 h with occasional diagnoses | no freeze; health lines in the log every minute; temperature and memory stable | |
| 2.17 | Logs | open the newest `~/AGRILENS_logs/agrilens_*.log` | shows version, model, camera, network, health lines, any errors | |

## 3. Go / No-Go

Go for EXPISCOR 2026 when 0.1–0.5, section 1 and tests 2.1–2.4, 2.6–2.8, 2.11, 2.12, 2.14 and 2.15 pass. Any other failure: record it and decide whether the presenter can work around it. If 5.0.0 fails on the day, run `pi_restore_previous.sh` and reboot (about 1 minute).
