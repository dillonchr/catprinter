#!/bin/bash
set -e

# Navigate to the directory of this script to ensure relative paths work
cd "$(dirname "$0")"

# Allow BTMAC to be overridden by environment variable, default to GB02
BTMAC="${BTMAC:-GB02}"

# Detect python command (python3 or python)
PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
  if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
  fi
fi

$PYTHON_CMD gdq.py | $PYTHON_CMD test.py
$PYTHON_CMD print.py -d "${BTMAC}" test.png
echo ok


