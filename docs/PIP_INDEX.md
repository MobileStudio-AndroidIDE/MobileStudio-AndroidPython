# MobileStudio Android pip index (Android ARM64 · CPython 3.13)

이 저장소는 MobileStudio의 Android ARM64 CPython 3.13 런타임용 pip wheel 인덱스를
제공합니다. 기기에서 pip가 GitHub Release에서 wheel을 자동으로 내려받습니다.

## 설치 방법 (기기)

### 자동 설정 (권장) — `pip install <pkg>` 만으로 내 릴리즈에서 다운로드

기기를 연결한 뒤 호스트에서 한 번 실행:

```bash
bash scripts/device_setup_pip.sh
```

이 한 번의 설정으로:
- `$PYDIR/pip.conf` 생성 (index-url = 본 인덱스, PyPI 폴백, CA 인증서 자동)
- `$PYDIR/bin/pip` 래퍼 생성 (`PIP_CONFIG_FILE` 자동 지정)

이후 기기에서는 그냥:

```bash
pip install opencv-python-headless   # GitHub Release에서 자동 다운로드
pip install scipy numba onnxruntime tflite-runtime
```

### 수동 설정 (일회성)

```bash
PY=/data/local/tmp/python-android
export LD_LIBRARY_PATH="$PY/lib:$PY/lib/python3.13/site-packages/chaquopy/lib"

# 인덱스 지정 (GitHub raw + Release asset)
$PY/bin/python3.13 -m pip install \
  --cert "$PY/lib/python3.13/site-packages/certifi/cacert.pem" \
  --index-url https://raw.githubusercontent.com/MobileStudio-AndroidIDE/MobileStudio-AndroidPython/main/simple/ \
  numpy pandas matplotlib
```

- 패키지 이름 주의: OpenCV는 `opencv-python-headless` 입니다 (`opencv` 아님).
- `--index-url`: PEP 503 simple index (`simple/` 디렉터리, raw.githubusercontent로 서빙)
- wheel 바이너리 자체는 GitHub Release `android-arm64-py313-v1` 에셋에서 다운로드됩니다.
- 네이티브 패키지(numpy 등)가 OpenBLAS/libcxx 등을 필요로 하므로
  `LD_LIBRARY_PATH`에 `site-packages/chaquopy/lib`를 포함해야 합니다.

## 인덱스 구성

| 소스 | 설명 |
|------|------|
| PyPI `py3-none-any` | 순수 Python 패키지 (rich, sympy, httpx …) |
| Chaquopy 빌드 | Chaquopy 프로젝트가 NDK로 빌드한 Android ARM64 wheel을
  `android_24` → `android_28` 태그로 재작성해 재배포 |
| 직접 빌드 (NDK r28) | propcache, msgpack, uvloop(+libuv), orjson, pydantic-core,
  rpds-py, safetensors, tokenizers (Rust), h5py(+HDF5) |
| 지원 안 함 | scipy, scikit-learn, scikit-image, numba, onnx, onnxruntime,
  tflite-runtime (Fortran/LLVM/Bazel 툴체인 필요, 아래 참고) |

wheel 해시/URL 목록은 `wheelhouse/MANIFEST.json`, 패키지별 페이지는
`simple/<package>/index.html`에 있습니다.

## 바닥부터 다시 만들기

```bash
python3 scripts/build_wheelhouse.py fetch      # Chaquopy + PyPI 수집/재태깅
bash scripts/build_rust_wheels.sh              # Rust 확장 (orjson 등)
python3 scripts/build_wheelhouse.py index      # simple/ 인덱스 생성
gh release create android-arm64-py313-v1 wheelhouse/*.whl --title ... --notes ...
```

## Chaquopy 재태깅

Chaquopy wheel(`android_21`/`android_24` 태그)은 본 런타임의
`sysconfig.get_platform() == android-28-arm64_v8a` 와 맞지 않아 pip가 거부합니다.
`wheel tags --platform-tag android_28_arm64_v8a` 로 재작성하며, 바이너리는 API 28
기기에서 그대로 동작합니다(하위 API 호환).

## 아직 포팅되지 않은 패키지

없음 — 요청 60개(중복 제외 58종) 전체 제공 ✅

비고:
- scipy 1.18은 Fortran-free 경로로 빌드되어 `scipy.odr` 모듈만 제외됩니다.
- onnxruntime은 CPU Execution Provider이며 XNNPACK delegate가 포함되어 있습니다.
- tflite-runtime은 TF 2.20 CMake 라우트로 빌드되었습니다(Bazel 미사용).
- numba/llvmlite는 LLVM 22.1.3 정적 크로스빌드 기반입니다.

### numpy 2 생태계

scipy/sklearn/skimage/opencv/h5py/ml_dtypes/onnx는 numpy 2.x 헤더로 빌드되어
`pip install` 시 numpy 2.5.4(인덱스 최신)와 함께 설치됩니다. Chaquopy 기반
numpy 1.26.2 휠도 병행 제공되지만, 위 패키지들과 함께 쓰려면 numpy 2.5.4를
유지하세요. pandas 2.3.3 / matplotlib 3.8.4 / contourpy 1.4.0 / pycocotools
2.0.11 은 numpy 2용으로 재빌드된 버전입니다.
