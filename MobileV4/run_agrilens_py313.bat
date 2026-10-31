@echo off
title AGRILENS - Python 3.13 Launcher
cd /d "%~dp0"
echo Starting AGRILENS with Python 3.13...
py -3.13 main.py
if errorlevel 1 (
    echo.
    echo Application exited or encountered an issue.
    pause
)
