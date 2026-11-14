#!/bin/bash
set -e
echo "=================================================="
echo " AGRILENS Raspberry Pi 5 Setup"
echo "=================================================="
sudo apt update
sudo apt install -y python3-tk python3-pil python3-pil.imagetk python3-opencv python3-numpy python3-pip v4l-utils
python3 -m pip uninstall -y pillow 2>/dev/null || true
pip3 install onnxruntime --break-system-packages
echo "=================================================="
echo " Setup Complete! Run: ./run_agrilens.sh"
echo "=================================================="

