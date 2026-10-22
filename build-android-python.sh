#!/bin/bash
set -euo pipefail

# Android Python 3.13 ARM64 교차 빌드 (NDK r28 + CPython 소스)
# 이 스크립트는 백그라운드에서 오래 실행됩니다.

cd /home/limsemin/Projects/MobileStudio-AndroidPython/cpython-3.13

export ANDROID_HOME=/home/limsemin/Android/Sdk
export ANDROID_NDK_HOME="$ANDROID_HOME/ndk/28.2.13676358"
export PATH="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin:$PATH"
export ANDROID_ABI=arm64-v8a
export ANDROID_API=28
export HOST_TRIPLE=aarch64-linux-android

echo "=== NDK 환경 확인 ==="
which aarch64-linux-android28-clang || { echo "clang 없음"; exit 1; }
aarch64-linux-android28-clang --version | head -1

echo "=== 1단계: configure-build (호스트 Python) ==="
python3 Android/android.py configure-build

echo "=== 2단계: make-build ==="
python3 Android/android.py make-build

echo "=== 3단계: configure-host (Android ARM64) ==="
python3 Android/android.py configure-host "$HOST_TRIPLE" -- \
    CC=aarch64-linux-android${ANDROID_API}-clang \
    CXX=aarch64-linux-android${ANDROID_API}-clang++ \
    AR=aarch64-linux-android-ar \
    RANLIB=aarch64-linux-android-ranlib \
    STRIP=aarch64-linux-android-strip \
    --host="$HOST_TRIPLE" \
    --prefix=/data/local/tmp/python-android \
    --disable-shared \
    --without-ensurepip \
    --with-build-python=./cross-build/build/python \
    --enable-optimizations

echo "=== 4단계: make-host ==="
python3 Android/android.py make-host "$HOST_TRIPLE"

echo "=== 빌드 완료 ==="
ls -la cross-build/"$HOST_TRIPLE"/python 2>/dev/null || echo "python 바이너리 미확인"
