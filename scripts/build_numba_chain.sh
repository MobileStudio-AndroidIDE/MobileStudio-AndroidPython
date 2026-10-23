#!/usr/bin/env bash
# Build llvmlite (0.50.0) and numba (0.68.0) for Android ARM64 CPython 3.13.
# Requires: install-llvm-android (LLVM 22 static libs, from build-llvm install).
set -euo pipefail

SRC="${SRC:-/tmp/opencode/src}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${OUT:-$ROOT/wheelhouse}"
NDK="${ANDROID_NDK_HOME:-/home/limsemin/Android/Sdk/ndk/28.2.13676358}"
TC="$NDK/toolchains/llvm/prebuilt/linux-x86_64"
PYSRC=/home/limsemin/Projects/MobileStudio-AndroidPython/cpython-3.13
PYLIB=/home/limsemin/AndroidPython/lib
LLVM_INST="$SRC/install-llvm-android"
JOBS="${JOBS:-3}"

# ---- 1. llvmlite -----------------------------------------------------------
rm -rf "$SRC/build-llvmlite"
cmake -S "$SRC/llvmlite-0.50.0/ffi" -B "$SRC/build-llvmlite" -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-28 \
  -DCMAKE_BUILD_TYPE=Release \
  -DLLVM_DIR="$LLVM_INST/lib/cmake/llvm" \
  -DCMAKE_CXX_FLAGS="-I$PYSRC/Include -I$PYSRC/cross-build/aarch64-linux-android/build"
cmake --build "$SRC/build-llvmlite" -j"$JOBS"
find "$SRC/build-llvmlite" -name 'libllvmlite*so' | head -2

rm -rf "$SRC/llvmlite-0.50.0/stage" && mkdir -p "$SRC/llvmlite-0.50.0/stage/llvmlite"
cp "$SRC"/build-llvmlite/libllvmlite*.so "$SRC/llvmlite-0.50.0/stage/llvmlite/libllvmlite.so"
cp "$SRC"/llvmlite-0.50.0/llvmlite/*.py "$SRC/llvmlite-0.50.0/stage/llvmlite/" 2>/dev/null || true
for sub in binding tests; do
  mkdir -p "$SRC/llvmlite-0.50.0/stage/llvmlite/$sub"
  cp "$SRC"/llvmlite-0.50.0/llvmlite/$sub/*.py "$SRC/llvmlite-0.50.0/stage/llvmlite/$sub/" 2>/dev/null || true
done
cp "$SRC"/llvmlite-0.50.0/LICENSE "$SRC"/llvmlite-0.50.0/stage/llvmlite/ 2>/dev/null || true

python3 "$ROOT/scripts/make_wheel.py" --name llvmlite --version 0.50.0 \
  --tree "$SRC/llvmlite-0.50.0/stage" --out "$OUT" \
  --summary "LLVM binding for numba (Android ARM64, LLVM 22 static)" \
  --requires "numpy"

# ---- 2. numba --------------------------------------------------------------
# fake llvmlite python package so numba's setup can read the version
SITE=/tmp/opencode/src/py313-venv/lib/python3.13/site-packages
mkdir -p "$SITE/llvmlite"
printf '__version__ = "0.50.0"\n' > "$SITE/llvmlite/__init__.py"

cd "$SRC/numba-0.68.0"
export TC="$TC"
export CC="$TC/bin/aarch64-linux-android28-clang"
export CXX="$TC/bin/aarch64-linux-android28-clang++"
export AR="$TC/bin/llvm-ar"
export CFLAGS="-fPIC -O2 -I$PYSRC/Include -I$PYSRC/cross-build/aarch64-linux-android/build"
export CPPFLAGS="$CFLAGS"
export CXXFLAGS="$CFLAGS"
export LDFLAGS="-L/tmp/opencode/src/ndk-libs -L$PYLIB -lpython3.13 -lm"
export LDSHARED="$CC -shared"
/tmp/opencode/venv/bin/python setup.py build_ext --inplace --parallel "$JOBS" \
  > "$SRC/numba-build.log" 2>&1 || { tail -20 "$SRC/numba-build.log"; exit 1; }

rm -rf stage && mkdir -p stage
cp -r numba stage/numba
find stage -name '*.so' | while read -r so; do
  base=$(basename "$so" .so)
  new=${base%.cpython-312-x86_64-linux-gnu}.cpython-313-aarch64-linux-android
  mv "$so" "$(dirname "$so")/${new}.so"
done
cp LICENSE stage/numba/ 2>/dev/null || true
python3 "$ROOT/scripts/make_wheel.py" --name numba --version 0.68.0 \
  --tree stage --out "$OUT" \
  --summary "Numba JIT (Android ARM64, llvmlite/LLVM 22)" \
  --requires "llvmlite==0.50.0" --requires "numpy>=1.22"
echo NUMBA-CHAIN-OK
