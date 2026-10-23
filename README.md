# MobileStudio-AndroidPython

Android ARM64 (aarch64/arm64-v8a) Python 3.13 package ecosystem for MobileStudio.

## Project Goal

Build and distribute 50+ Python packages for Android ARM64, with pip-compatible installation via GitHub Releases. MobileStudio uses this repository as its package distribution source.

## Architecture

```
MobileStudio-AndroidPython/
├── recipes/              # Package build recipes (recipe.yaml + build.sh)
├── build/                # Cross-compilation helpers
├── compatibility/        # Python version & package status metadata
├── scripts/              # build-all, test-qemu, test-device, publish-release
├── tools/                # android_bundle.py (app embedding)
├── client/android/       # PyBridge.java (NDK bridge)
├── dist/                 # Built wheels (gitignored)
├── build-work/           # Build intermediates (gitignored)
└── docs/
```

## Quick Start

### Prerequisites

- Android NDK r28+ (installed at `$HOME/Android/Sdk/ndk/28.2.13676358`)
- Android SDK with cmdline-tools
- Python 3.12+ on host (for build scripts)
- GitHub CLI (`gh`) authenticated (for releases)

### Phase 1: Build Python 3.13 for Android ARM64

```bash
export ANDROID_HOME=$HOME/Android/Sdk
bash build-android-python.sh
```

This cross-compiles CPython 3.13 for `aarch64-linux-android28` using NDK r28c.
Output: `$HOME/AndroidPython/bin/python3.13` (ARM64 ELF binary).

### Phase 2: Build Packages

```bash
bash scripts/build-all.sh
```

Builds all recipes in `recipes/` and outputs wheels to `dist/`.

### Phase 3: Test

**QEMU (user-mode emulation):**
```bash
bash scripts/test-qemu.sh
```

**Real Android device:**
```bash
bash scripts/test-device.sh
```

### Phase 4: Publish

```bash
bash scripts/generate-checksums.sh
bash scripts/publish-release.sh --tag v0.1.0
```

## Package Status

See `compatibility/package-status.json` for the current build status of all 56 candidate packages.

| Category | Count |
|----------|-------|
| Pure Python | 31 |
| Native (C/C++ extension) | 25 |
| Unsupported | 3 (uvloop, numba, torch) |

## pip wheel index (Android ARM64 · CPython 3.13)

**실제 설치는 pip 인덱스로 합니다.** 자세한 내용은 [`docs/PIP_INDEX.md`](docs/PIP_INDEX.md).

```bash
$PY/bin/python3.13 -m pip install \
  --cert "$PY/lib/python3.13/site-packages/certifi/cacert.pem" \
  --index-url https://raw.githubusercontent.com/MobileStudio-AndroidIDE/MobileStudio-AndroidPython/main/simple/ \
  numpy pandas matplotlib
```

- 100+ wheel이 GitHub Release `android-arm64-py313-v1`에 업로드되어 있습니다.
- 소스: PyPI 순수 wheel / Chaquopy 재태깅(android_24→28) / NDK r28 직접 빌드 /
  Rust(maturin) 빌드.
- `simple/`은 PEP 503 simple index이며 `wheelhouse/MANIFEST.json`에 SHA-256이 기록됩니다.

## Embedding in Android Apps

See `docs/android_embed.md` for bundling the Python runtime into an APK via `jniLibs` + `assets/python/` and the `PyBridge.java` NDJSON bridge.

## License

Apache-2.0. See `LICENSE`. Individual package licenses are their own responsibility.

## Release Index

Published wheels are available via GitHub Releases with SHA-256 checksums:

```
releases/
├── v0.1.0/
│   ├── index.json
│   ├── checksums.sha256
│   └── wheels/
```

MobileStudio's installer reads `index.json` for version/ABI compatibility metadata before downloading.
