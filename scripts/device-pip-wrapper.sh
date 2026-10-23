#!/system/bin/sh
# pip wrapper for MobileStudio Android Python.
# Auto-uses the MobileStudio GitHub wheel index (client/android/pip.conf).
PYDIR=/data/local/tmp/python-android
export PIP_CONFIG_FILE="$PYDIR/pip.conf"
exec "$PYDIR/bin/python3.13" -m pip "$@"
