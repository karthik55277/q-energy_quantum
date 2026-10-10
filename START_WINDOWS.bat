@echo off
title Q-Energy
cd /d %~dp0
echo Installing what Q-Energy needs (first time takes a minute)...
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
  echo.
  echo Python was not found or the install failed.
  echo Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add Python to PATH".
  pause
  exit /b
)
echo Starting Q-Energy. Your browser will open at http://localhost:5000
python app.py
pause
