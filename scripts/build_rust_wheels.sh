#!/usr/bin/env bash
# Cross-compile Rust-based Python extensions for Android ARM64 / CPython 3.13.
#
# Requires: rustup target aarch64-linux-android, maturin, NDK r28.
# Output:   wheelhouse/*.whl (tagged android_28_arm64_v8a)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${SRC:-/tmp/opencode/src}"
OUT="${OUT:-$ROOT/wheelhouse}"
NDK="${ANDROID_NDK_HOME:-/home/limsemin/Android/Sdk/ndk/28.2.13676358}"
TOOLCHAIN="$NDK/toolchains/llvm/prebuilt/linux-x86_64"
CC="$TOOLCHAIN/bin/aarch64-linux-android28-clang"
AR="$TOOLCHAIN/bin/llvm-ar"
PYROOT="${ANDROID_PYTHON:-/home/limsemin/AndroidPython}"
MATURIN="${MATURIN:-/tmp/opencode/venv/bin/maturin}"

export PYO3_CROSS=1
export PYO3_CROSS_PYTHON_VERSION=3.13
export PYO3_CROSS_LIB_DIR="$PYROOT"
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER="$CC"
export CC_aarch64_linux_android="$CC"
export AR_aarch64_linux_android="$AR"
export CXX_aarch64_linux_android="$TOOLCHAIN/bin/aarch64-linux-android28-clang++"
export ANDROID_API_LEVEL=28
export RUSTFLAGS="-C link-arg=-L$PYROOT/lib"

mkdir -p "$SRC" "$OUT"

build_one() {
    local dist="$1" version="$2"
    local sdist=""
    for candidate in "$SRC/${dist}-${version}.tar.gz" "$SRC/${dist//-/_}-${version}.tar.gz"; do
        if [[ -f "$candidate" ]]; then sdist="$candidate"; break; fi
    done
    if [[ -z "$sdist" ]]; then
        echo "== downloading $dist $version"
        python3 -m pip download --no-binary=:all: --no-deps "$dist==$version" -d "$SRC" >/dev/null
        for candidate in "$SRC/${dist}-${version}.tar.gz" "$SRC/${dist//-/_}-${version}.tar.gz"; do
            if [[ -f "$candidate" ]]; then sdist="$candidate"; break; fi
        done
    fi
    local dir="$SRC/$(tar tzf "$sdist" | head -1 | cut -d/ -f1)"
    rm -rf "$dir"
    tar xzf "$sdist" -C "$SRC"
    echo "== building $dist $version ($dir)"
    (cd "$dir" && "$MATURIN" build --release --target aarch64-linux-android --out dist)
    cp "$dir"/dist/*.whl "$OUT"/
}

build_one pydantic-core 2.50.1
build_one rpds-py 2026.9.1
build_one safetensors 0.8.0
build_one tokenizers 0.23.3

echo "== done"
ls -1 "$OUT" | grep -E 'pydantic_core|rpds_py|safetensors|tokenizers' || true
