# Installing AGRILENS 5.0.0

## A. Kiosks already running 4.9.4 (normal path, after publication)

No action on the device. On its next boot (or when **ADMIN → ☁ OTA UPDATE (INTERNET)** is tapped) the kiosk downloads release `AGRILENS-5.0.0` from GitHub `main`, verifies the model SHA-256 and restarts. Check afterwards:

- The tooltip on the AGRILENS brand label (top bar) shows `v5.0.0 (AGRILENS-5.0.0)`, model `AGRILENS-MULTICROP 1.0.0` and dataset `AGL-MULTICROP-MD 1.0.0`.
- The start-up console line (terminal or `journalctl`) reads `AGRILENS 5.0.0: model ONNX AGRILENS-MULTICROP 1.0.0; rejection gates from calibration of AGRILENS-MULTICROP 1.0.0: ...`.
- `sha256sum ~/AGRILENS_RaspberryPi/agrilens.onnx` equals `model_sha256` in `RELEASE_MANIFEST.json`.

Thresholds that an operator saved under 4.9.4 are ignored by 5.0.0 (they were not saved for this model). Re-saving in the Admin Console stores new values tagged with the model's SHA-256.

## B. New Raspberry Pi 5

Raspberry Pi OS (64-bit, Bookworm or later), network connection.

```bash
git clone https://github.com/faiyaze04/AGRILENS.git
cp -r AGRILENS/AGRILENS_RaspberryPi ~/AGRILENS_RaspberryPi
cd ~/AGRILENS_RaspberryPi
sha256sum -c SHA256SUMS            # every line must say OK
chmod +x setup_rpi.sh run_agrilens.sh ota_update.sh setup_remote_ota.sh rollback.sh
./setup_rpi.sh                     # apt + pip dependencies, then setup_remote_ota.sh (Pi Connect, SSH, agrilens-ota.service)
python3 test_deps.py
./run_agrilens.sh
```

Detailed device guide (Thonny, autostart, camera panel, troubleshooting): `HOW_TO_RUN_ON_RASPBERRY_PI.md` in the same folder.

## C. Windows / Linux PC

```bash
pip install -r application/requirements.txt
python AGRILENS_RaspberryPi/main.py
```

Windows with Python 3.13: `tools/development/run_agrilens_windows_py313.bat`.

## D. Offline installation from a release archive

Copy the `AGRILENS_RaspberryPi` folder from the approved release commit (tag `AGRILENS-5.0.0`) to `~/AGRILENS_RaspberryPi` by USB drive, run `sha256sum -c SHA256SUMS`, then continue with step B from `./setup_rpi.sh`. To keep an offline kiosk from updating when it later connects, create `~/.agrilens_ota_hold`.

## Rollback

See `documentation/technical/ROLLBACK.md`.
