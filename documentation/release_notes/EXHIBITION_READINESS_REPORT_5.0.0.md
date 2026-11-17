# AGRILENS 5.0.0 – EXPISCOR 2026 exhibition readiness report

Date 2026-11-17. Release accepted for the exhibition with the C2 deviation (`C2_DEVIATION_EXHIBITION_ACCEPTANCE.md`). Commit `243fbf5` and model `multicrop1_R2_s42` (`776d08ac…0332b`) are unchanged; thresholds unchanged (confidence 0.40, margin 0.12, logit 2.10). No retraining, no GitHub publication, no OTA.

**Bottom line: conditional GO.** Everything that can be checked without the exhibition hardware passes. The Raspberry Pi 5, C270 and touchscreen tests have not been run yet: no Pi is reachable from this workstation. They are prepared as a kit and a checklist that take about 1–2 hours on the Pi. The final Go depends on them.

## 1. Installation and configuration status

| Item | Status |
|---|---|
| Exhibition kit | `D:\AGRILENS_Training\release_5.0.0\exhibition\AGRILENS_EXPISCOR2026_kit.zip` (10.9 MB, SHA-256 `cad50603…3bea`, 50 files with `KIT_SHA256SUMS`). Built by `deployment/exhibition/build_exhibition_kit.py` |
| Contents | the 5.0.0 package (38 files, verified), backup / side-by-side install / benchmark / restore scripts, exhibition launcher, benchmark tool, checklist, README |
| Install method | 5.0.0 goes to `~/AGRILENS_5.0.0`; `~/AGRILENS_RaspberryPi` (4.9.4) is never modified. The install refuses without a verified backup, refuses a tampered package, refuses to overwrite, and refuses to run from a USB drive |
| Automatic updates | `~/.agrilens_ota_hold` is set; the launcher does not call `ota_update.sh`. GitHub `main` still serves 4.9.4; 5.0.0 would block that as a downgrade anyway |
| Gate settings | the launcher removes Admin-saved gate values at every start, so the calibrated values always apply |
| On the Pi | **Not installed yet** (no Pi access) |

Two hazards found in the existing code are handled by the procedure, without changing the app:
- **USB start.** If AGRILENS is started directly from a USB drive (`/media`, `/mnt`), it copies itself over `~/AGRILENS_RaspberryPi`. The kit is copied to the SD card first, and the install script refuses to run from a USB drive.
- **Shared settings file.** 5.0.0 writes its own thresholds into `~/.agrilens_kiosk_config.json`, which 4.9.4 also reads. 4.9.4 would then run with 5.0.0 thresholds. The backup saves that file, and the restore puts it back byte for byte.

## 2. Raspberry Pi 5 performance

**Pending.** Run `pi_benchmark.sh` (100 timed diagnoses per version plus a 10-minute 5.0.0 soak, kiosk stopped). Go limits are in the checklist: median ≤ 1.5 s, P95 ≤ 3 s, peak memory ≤ 1 GB, memory drift ≤ 20 MB per 10 min, temperature ≤ 80 °C with no throttling. The launcher logs temperature, throttling and kiosk memory every minute during the exhibition.

Desktop reference only (AMD laptop, Windows 11; **not Pi figures**):

| Measure | 5.0.0 |
|---|---|
| Diagnosis, six-view path, 1,200 runs | median 25 ms, P95 256 ms, max 387 ms |
| Same as 4.9.4 model | 22.5 ms vs 21.6 ms median (24 samples × 50) |
| Process memory during the 1,200 runs | 183–191 MB, no growth (peak 350 MB during model load) |

## 3. Camera and touchscreen

| Test | Result |
|---|---|
| Logitech C270 live capture | **Pending (Pi)**. No C270 is attached to this PC |
| Camera code on this PC's built-in webcam | detected in 11.7 s; 140 of 140 frames in 5 s; closed and re-detected in 2.5 s; 30 of 30 frames after re-detection |
| Camera unplugged | covered by the existing tests (fake camera): after more than 30 failed reads the kiosk drops the camera and switches to File Mode. **It does not reconnect by itself.** Recovery: ADMIN → 📷 CAMERA CONTROL PANEL → 🔍 DETECT WEBCAM, or touch the screen after the 3-minute screensaver. Real unplug and replug: Pending (Pi) |
| Image upload (File Mode), all crops | 24 of 24 sample images (all 4 crops, all 24 classes) give the correct crop and condition, with or without the crop locked in the selector, and show HEALTHY or DISEASE result screens |
| Hindi / English | all 24 classes have Hindi crop and condition names and Hindi recommendations (3–4 steps, same count as English); the Hindi result screen renders Devanagari for every sample |
| Touchscreen navigation | **Pending (Pi)** |
| Cautionary messages | blank black / white / grey, table colour, sky colour, noise, colour gradient and a printed text card all give "UNKNOWN PLANT / OUT OF SCOPE". **The AGRILENS logo was read as a healthy leaf and the Gundecha crest as Apple Rust** (see limitations) |

## 4. Offline operation and recovery

| Test (desktop, real Tk application, network blocked) | Result |
|---|---|
| Start without internet | starts; start-up line confirms model 1.0.0 and the calibrated gates; no error, no traceback; ran 87 s until a person closed it with the on-screen button |
| Start again after a forced kill (simulated crash / power cut) | starts normally |
| Start with a half-written settings file (simulated power cut during a save) | prints a notice, uses defaults, writes a valid settings file again |
| Launcher, kiosk crashes repeatedly | restarts it; stops after more than 5 crashes in 10 minutes and logs why |
| Launcher, kiosk closed from Admin (exit code 0) | restarts it; stops only when `~/.agrilens_stop` exists |
| Logs | one file per launcher start in `~/AGRILENS_logs/`, holding the app output plus a version / model / network / camera header and minute-by-minute health lines; newest 30 kept |
| Backup → install → simulated 5.0.0 use → restore (bash, fake kiosk home) | 4.9.4 folder and all per-user files restored byte for byte; also run from the built ZIP |
| Offline, power cut and crash recovery on the Pi | **Pending (Pi)**: checklist items 2.11, 2.14, 2.15 |

Automated tests: 149 passed (145 before plus 4 new kit tests), 0 failed, 0 skipped. `ruff` passes.

## 5. Known limitations (say these, do not hide them)

- **Accuracy claims:** none. The app shows no accuracy figure, and the result panel always shows the advisory "Consult your local extension officer before applying chemical treatments" (in Hindi when Hindi is selected). Do not quote test percentages at the exhibition.
- **Mango Die Back** is often mistaken for Powdery Mildew or Gall Midge (recall 0.46 in the frozen test).
- **Mango Gall Midge** is a provisional class with few test images, and other Mango conditions are sometimes called Gall Midge.
- The C2 criterion failed (Mango macro-F1 0.849 against 0.85); this is accepted for the exhibition only.
- **Green or leaf-like pictures can be diagnosed:** the AGRILENS logo was called healthy and the Gundecha crest Apple Rust. Keep posters and logos out of the camera view. 33% of background-only images were accepted in the frozen test. Mango Turning Brown leaves are given a diagnosis (it is not a supported class).
- Tomato Yellow Leaf Curl Virus shows general advice instead of specific steps. The recommendations come from 4.9.4 and have not been reviewed by an agronomist.
- The camera does not reconnect by itself after an unplug (use DETECT WEBCAM).
- The Admin console has no password: visitors can change sliders or close the app. The launcher restarts the app and restores the gates at the next start; slider changes made during a session last until then. Keep the kiosk supervised.
- Apple, Potato and Tomato were trained mostly on laboratory photographs. Real leaves under hall lighting may score lower than the samples.
- Raspberry Pi, C270 and touchscreen behaviour is unverified until the checklist is done.

## 6. Recovery and rollback

| Situation | Action | Time |
|---|---|---|
| Kiosk closed or crashed | the launcher restarts it automatically | ~5 s |
| Camera unplugged | plug in; ADMIN → 📷 CAMERA CONTROL PANEL → 🔍 DETECT WEBCAM | < 1 min |
| Kiosk frozen | `pkill -f AGRILENS_5.0.0/main.py` (launcher restarts it) or power-cycle | ~1 min |
| 5.0.0 unusable | `bash ~/AGRILENS_5.0.0/exhibition/pi_restore_previous.sh && sudo reboot` → back to 4.9.4 with its settings | ~1–2 min |
| SD card or folder damaged | restore from `~/AGRILENS_backups/v4.9.4_<time>/` (or its USB copy): `app_folder.tar.gz` + `home_files/` | ~5 min |

The rollback should be rehearsed once on the Pi before the exhibition (checklist step 0.4).

## 7. Go / No-Go for EXPISCOR 2026

| Area | Status |
|---|---|
| Application and model (software) | **Go** (24/24 samples, cautionary screens, offline start, crash and corrupt-settings recovery, 149 tests) |
| Installation and rollback procedure | **Go** (tested on a simulated kiosk home); Pi rehearsal pending |
| Raspberry Pi 5 performance | **Pending** |
| C270 live capture, unplug and replug | **Pending** |
| Touchscreen usability | **Pending** |
| Offline, crash and power-cut recovery on the Pi | **Pending** |

**Recommendation: conditional GO.** Use 5.0.0 at EXPISCOR 2026 once checklist steps 0.1–0.5, the performance limits in section 1, and tests 2.1–2.4, 2.6–2.8, 2.11, 2.12, 2.14 and 2.15 pass on the exhibition Pi. If any of these fails and cannot be fixed by setup (focus, lighting, placement), restore 4.9.4 and exhibit that. If the checklist cannot be completed before the event, exhibit 4.9.4 with 5.0.0 installed beside it, ready to switch.
