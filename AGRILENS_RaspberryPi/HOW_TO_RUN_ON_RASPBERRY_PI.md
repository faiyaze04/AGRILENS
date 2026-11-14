# How to Run AGRILENS on Raspberry Pi (Thonny IDE Guide)

This folder contains all the standalone files needed to run the **AGRILENS AI Plant Health Kiosk** on a Raspberry Pi without needing the training datasets or development notebooks.

---

## 📁 What is in this Folder:
- `main.py` — The main Tkinter Kiosk application (`1024x600` Waveshare Touch LCD).
- `agrilens.onnx` — The standalone 15-epoch MobileNetV4 ONNX model (all weights embedded in this single file).
- `labels.txt` — 24 crop disease & healthy classes across 4 species (`Apple`, `Mango`, `Potato`, `Tomato`).
- `kiosk_config.json` — Calibration configuration (confidence, margins, sharpness, camera settings).
- `assets/gundecha_logo.png` — Gundecha Education Academy logo.
- `requirements.txt` — Python package dependencies.
- `setup_rpi.sh` — One-click dependency installation script for Raspberry Pi OS.
- `test_deps.py` — Quick diagnostic script to verify all libraries in 2 seconds.
- `run_agrilens.sh` — Quick launcher script for Raspberry Pi.

---

## 🚀 Step 1: Copy this Folder to your Raspberry Pi
You can transfer the entire `AGRILENS_RaspberryPi` folder to your Raspberry Pi via:
1. **USB Pen Drive**: Plug USB drive into PC, copy `AGRILENS_RaspberryPi` onto it, then plug into Raspberry Pi and copy to `/home/pi/` (or `/home/<username>/`).
2. **SCP / SFTP / FileZilla**: Transfer over local network to `/home/pi/AGRILENS_RaspberryPi`.
3. **VNC File Transfer**: Drag-and-drop into Raspberry Pi desktop.

---

## 🛠️ Step 2: Install Required Libraries on Raspberry Pi

Open a Terminal on your Raspberry Pi, navigate into this folder, and run the setup script:

```bash
cd ~/AGRILENS_RaspberryPi
chmod +x setup_rpi.sh run_agrilens.sh
./setup_rpi.sh
```

### Alternatively, install manually via Terminal:
```bash
sudo apt update
sudo apt install -y python3-tk python3-pil python3-pil.imagetk python3-opencv python3-numpy python3-pip
# If you previously ran 'pip install pillow', uninstall it so the system Tkinter-enabled Pillow is used:
python3 -m pip uninstall -y pillow 2>/dev/null || true
pip3 install onnxruntime --break-system-packages
```

> [!NOTE]
> **Pillow / ImageTk on Raspberry Pi OS**:
> Always use `sudo apt install python3-pil python3-pil.imagetk`. Do not use `pip install pillow` on Raspberry Pi, because standard PyPI Linux wheels omit the `_imagingtk` C extension needed by Tkinter. If already installed via pip, running `python3 -m pip uninstall -y pillow` restores the working system package.

---

## ▶️ Step 3: Run with Thonny

1. Open **Thonny** on Raspberry Pi.
2. Go to **File** → **Open...**
3. Navigate to `AGRILENS_RaspberryPi` and select `main.py`.
4. Click the green **Run current script** button (or press `F5`).
5. The full-screen AGRILENS Kiosk interface will start up:
   - It will automatically detect your USB webcam.
   - It will load the MobileNetV4 ONNX model in `~24ms`.
   - Touch/click **CAPTURE LEAF** then **DIAGNOSE NOW** to identify crop diseases.

---

## 💡 Tips & Troubleshooting

- **Admin Mode PIN**: The admin panel PIN is `AGRILENS`. You can use it to calibrate focus sharpness, confidence thresholds, and test webcams.
- **Webcam permission**: If the webcam doesn't open, ensure your user is in the `video` group:
  ```bash
  sudo usermod -a -G video $USER
  ```
- **Direct Terminal Launch**:
  ```bash
  python3 main.py
  # or
  ./run_agrilens.sh
  ```
