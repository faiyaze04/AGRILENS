@echo off
title AGRILENS - Publish OTA Update to GitHub and Raspberry Pi
cd /d "%~dp0"
echo ============================================================
echo   AGRILENS - Over-The-Air (OTA) Publisher (PC to GitHub/RPi)
echo ============================================================
echo.
git config user.name "faiyaze04"
git config user.email "35885868+faiyaze04@users.noreply.github.com"

echo [1/2] Syncing MobileV4\main.py to AGRILENS_RaspberryPi\main.py...
copy /Y "MobileV4\main.py" "AGRILENS_RaspberryPi\main.py" >nul

echo [2/2] Pushing latest build to GitHub (origin/main)...
git add -A
git commit -m "OTA Release Update" 2>nul
git push origin main

echo.
echo ============================================================
echo   Done! Your Raspberry Pi can now pull this update via:
echo     - On Reboot:   Updates immediately on Raspberry Pi boot
echo     - Touchscreen: Tap [ADMIN] then [OTA UPDATE (INTERNET)]
echo     - Terminal:    bash ~/AGRILENS_RaspberryPi/ota_update.sh
echo ============================================================
pause
