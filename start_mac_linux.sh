#!/usr/bin/env bash
# Q-Energy: install what it needs, then open http://localhost:5000
cd "$(dirname "$0")"
echo "Installing what Q-Energy needs (first time takes a minute)..."
python3 -m pip install --quiet -r requirements.txt || { echo "Install failed. Do you have Python 3.10+?"; exit 1; }
echo "Starting Q-Energy. Your browser will open at http://localhost:5000"
python3 app.py
