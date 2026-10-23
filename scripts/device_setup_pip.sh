#!/usr/bin/env bash
# One-shot device setup: install pip.conf + pip wrapper so that a plain
#   pip install <package>
# automatically pulls wheels from the MobileStudio GitHub Release index.
set -euo pipefail

PYDIR=/data/local/tmp/python-android

adb push client/android/pip.conf "$PYDIR/pip.conf" >/dev/null
adb push scripts/device-pip-wrapper.sh "$PYDIR/bin/pip" >/dev/null
adb shell "chmod +x $PYDIR/bin/pip && mkdir -p /data/local/tmp/pip-cache"

echo "== pip config on device =="
adb shell "PIP_CONFIG_FILE=$PYDIR/pip.conf $PYDIR/bin/python3.13 -m pip config list"

echo "== verification: pip install opencv-python-headless (target dir) =="
adb shell "rm -rf /data/local/tmp/verify-cv && mkdir -p /data/local/tmp/verify-cv && \
  PIP_CONFIG_FILE=$PYDIR/pip.conf \
  LD_LIBRARY_PATH=$PYDIR/lib:$PYDIR/lib/python3.13/site-packages/chaquopy/lib \
  $PYDIR/bin/pip install --target /data/local/tmp/verify-cv --no-cache-dir opencv-python-headless 2>&1 | grep -E 'Downloading|Successfully' | head -5"

echo "== import test =="
adb shell "LD_LIBRARY_PATH=$PYDIR/lib:$PYDIR/lib/python3.13/site-packages/chaquopy/lib:/data/local/tmp/verify-cv/chaquopy/lib \
  PYTHONPATH=/data/local/tmp/verify-cv \
  $PYDIR/bin/python3.13 -c 'import cv2, numpy; print(\"cv2\", cv2.__version__, \"numpy\", numpy.__version__)'"
