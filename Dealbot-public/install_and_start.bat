@echo off
setlocal
title Install and Start DealBot V6
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher not found. Install Python 3.11 or newer from python.org and enable Add Python to PATH.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" py -3 -m venv .venv
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
if not exist ".env" python migrate_from_v5.py
python self_test.py
if errorlevel 1 (
  echo Self-test failed. Read the error above.
  pause
  exit /b 1
)
python app.py
pause
