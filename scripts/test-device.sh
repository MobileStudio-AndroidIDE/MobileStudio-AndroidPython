#!/bin/bash
set -euo pipefail

# MobileStudio Android Python - Device Test Script
# Tests wheels on an actual Android device via adb

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DISTDIR="${DISTDIR:-$REPO_ROOT/dist}"

ANDROID_PYTHON_REMOTE="/data/local/tmp/python-android"

echo "============================================"
echo "MobileStudio Android Python - Device Test"
echo "Remote Python: $ANDROID_PYTHON_REMOTE"
echo "============================================"

# Check adb
if ! command -v adb >/dev/null 2>&1; then
    echo "ERROR: adb not found"
    exit 1
fi

# Check device
DEVICE_COUNT=$(adb devices 2>/dev/null | grep -c "device$" || true)
if [ "$DEVICE_COUNT" -eq 0 ]; then
    echo "ERROR: No Android device connected"
    echo "Run: adb devices"
    exit 1
fi

echo "Device(s) connected: $DEVICE_COUNT"

# Push Android Python to device (if not already there)
echo ""
echo "Pushing Python runtime to device..."
adb push "$ANDROID_PYTHON/bin/python3.13" "$ANDROID_PYTHON_REMOTE/bin/" 2>/dev/null || true
adb push "$ANDROID_PYTHON/lib" "$ANDROID_PYTHON_REMOTE/" 2>/dev/null || true

# Test each wheel
FAILED=0
PASSED=0

for wheel in "$DISTDIR"/*.whl; do
    [ -f "$wheel" ] || continue
    pkg_name=$(basename "$wheel" .whl | sed 's/_/-/g' | cut -d- -f1)
    echo ""
    echo "Testing: $(basename "$wheel")"

    # Push wheel to device
    REMOTE_WHEEL="/data/local/tmp/$(basename "$wheel")"
    adb push "$wheel" "$REMOTE_WHEEL"

    # Install on device
    adb shell "$ANDROID_PYTHON_REMOTE/bin/python3.13" \
        -m pip install --target="/data/local/tmp/pkgs" --no-deps "$REMOTE_WHEEL" 2>&1 | tail -5

    if [ $? -eq 0 ]; then
        echo "  Install: OK"
        PASSED=$((PASSED + 1))
    else
        echo "  Install: FAILED"
        FAILED=$((FAILED + 1))
        adb shell rm -f "$REMOTE_WHEEL"
        continue
    fi

    # Run import test on device
    adb shell "$ANDROID_PYTHON_REMOTE/bin/python3.13" \
        -c "import $pkg_name; print('import OK', $pkg_name.__version__ if hasattr($pkg_name, '__version__') else '')" 2>&1 | tail -3

    adb shell rm -f "$REMOTE_WHEEL"
done

echo ""
echo "============================================"
echo "Device Test Complete"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "============================================"

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
