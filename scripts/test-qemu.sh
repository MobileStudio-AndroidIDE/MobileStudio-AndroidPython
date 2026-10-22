#!/bin/bash
set -euo pipefail

# MobileStudio Android Python - QEMU Test Script
# Tests wheels in QEMU ARM64 user-mode emulation
# NOTE: Requires qemu-aarch64 or qemu-aarch64-static installed

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DISTDIR="${DISTDIR:-$REPO_ROOT/dist}"

QEMU_BIN="${QEMU_BIN:-qemu-aarch64}"
ANDROID_PYTHON="${ANDROID_PYTHON:-$HOME/AndroidPython}"

echo "============================================"
echo "MobileStudio Android Python - QEMU Test"
echo "QEMU: $QEMU_BIN"
echo "Android Python: $ANDROID_PYTHON"
echo "============================================"

# Check QEMU availability
if ! command -v "$QEMU_BIN" >/dev/null 2>&1; then
    echo "ERROR: $QEMU_BIN not found"
    echo "Install with: sudo apt install qemu-user-static"
    exit 1
fi

# Check Android Python
if [ ! -x "$ANDROID_PYTHON/bin/python3.13" ]; then
    echo "ERROR: Android Python not found at $ANDROID_PYTHON/bin/python3.13"
    exit 1
fi

# Test each wheel
FAILED=0
PASSED=0

for wheel in "$DISTDIR"/*.whl; do
    [ -f "$wheel" ] || continue
    pkg_name=$(basename "$wheel")
    echo ""
    echo "Testing: $pkg_name"

    # Install wheel into Android Python site-packages using QEMU
    TMPINSTALL=$(mktemp -d)
    "$QEMU_BIN" "$ANDROID_PYTHON/bin/python3.13" -m pip install \
        --target="$TMPINSTALL" --no-deps "$wheel" 2>&1 | tail -5

    if [ $? -eq 0 ]; then
        echo "  Install: OK"
        PASSED=$((PASSED + 1))
    else
        echo "  Install: FAILED"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Run import test
    TEST_CMD="import $pkg_name; print('import OK')"
    "$QEMU_BIN" "$ANDROID_PYTHON/bin/python3.13" \
        -c "$TEST_CMD" 2>&1 | tail -3

    if [ $? -eq 0 ]; then
        echo "  Import: OK"
    else
        echo "  Import: FAILED"
        FAILED=$((FAILED + 1))
    fi

    rm -rf "$TMPINSTALL"
done

echo ""
echo "============================================"
echo "QEMU Test Complete"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "============================================"

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
