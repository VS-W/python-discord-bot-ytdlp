#!/bin/bash
echo "Installing/upgrading packages..."
pip install --quiet --no-warn-script-location -r requirements.txt --upgrade
python3 -m bot.py
