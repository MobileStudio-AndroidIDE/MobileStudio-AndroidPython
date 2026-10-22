#!/bin/bash
set -euo pipefail

# MobileStudio Android Python - Build All Script
# Builds all packages in recipes/ directory for Android ARM64

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NDK_HOME="${ANDROID_NDK_HOME:-$HOME/Android/Sdk/ndk/28.2.13676358}"
ANDROID_PYTHON="${ANDROID_PYTHON:-$HOME/AndroidPython}"
API_LEVEL="${ANDROID_API:-28}"
WORKDIR="${WORKDIR:-$REPO_ROOT/build-work}"
DISTDIR="${DISTDIR:-$REPO_ROOT/dist}"

export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"

mkdir -p "$WORKDIR" "$DISTDIR"

echo "============================================"
echo "MobileStudio Android Python - Build All"
echo "NDK: $NDK_HOME"
echo "Android Python: $ANDROID_PYTHON"
echo "API Level: $API_LEVEL"
echo "Workdir: $WORKDIR"
echo "Distdir: $DISTDIR"
echo "============================================"

# Verify NDK
if [ ! -d "$NDK_HOME" ]; then
    echo "ERROR: NDK not found at $NDK_HOME"
    exit 1
fi

# Verify Android Python runtime
if [ ! -x "$ANDROID_PYTHON/bin/python3.13" ]; then
    echo "ERROR: Android Python not found at $ANDROID_PYTHON/bin/python3.13"
    echo "Run build-android-python.sh first"
    exit 1
fi

# Build each recipe
RECIPES_DIR="$REPO_ROOT/recipes"
FAILED=0
BUILT=0

for recipe_dir in "$RECIPES_DIR"/*/; do
    recipe_yaml="$recipe_dir/recipe.yaml"
    if [ ! -f "$recipe_yaml" ]; then
        echo "SKIP: $recipe_dir (no recipe.yaml)"
        continue
    fi

    pkg_name=$(basename "$recipe_dir")
    echo ""
    echo "============================================"
    echo "Building: $pkg_name"
    echo "============================================"

    if python3 "$SCRIPT_DIR/../build/build_wheel.py" \
        "$recipe_yaml" \
        --ndk "$NDK_HOME" \
        --android-python "$ANDROID_PYTHON" \
        --api-level "$API_LEVEL" \
        --workdir "$WORKDIR/$pkg_name"; then
        echo "BUILT: $pkg_name"
        BUILT=$((BUILT + 1))
        # Copy wheel to dist
        cp "$WORKDIR/$pkg_name"/dist/*.whl "$DISTDIR/" 2>/dev/null || true
    else
        echo "FAILED: $pkg_name"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "============================================"
echo "Build Complete"
echo "Built: $BUILT"
echo "Failed: $FAILED"
echo "Wheels in: $DISTDIR"
echo "============================================"

if [ "$FAILED" -gt 0 ]; then
    exit 1
fi
