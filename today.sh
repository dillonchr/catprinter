#!/bin/bash
set -e

BTMAC="GB02"

node ~/git/gdq-printer/gdq.js | python test.py
python print.py -d "${BTMAC}" test.png
echo ok
