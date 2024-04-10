#!/bin/bash
echo "Installing/upgrading packages..."
pip install --no-warn-script-location -r requirements.txt --upgrade
python3 sse.py &
python3 bot.py
