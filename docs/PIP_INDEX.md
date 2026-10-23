# MobileStudio Android pip index (Android ARM64 · CPython 3.13)

이 저장소는 MobileStudio의 Android ARM64 CPython 3.13 런타임용 pip wheel 인덱스를
제공합니다. 기기에서 pip가 GitHub Release에서 wheel을 자동으로 내려받습니다.

## 설치 방법 (기기)

```bash
PY=/data/local/tmp/python-android
export LD_LIBRARY_PATH="$PY/lib:$PY/lib/python3.13/site-packages/chaquopy/lib"

# 인덱스 지정 (GitHub raw + Release asset)
$PY/bin/python3.13 -m pip install \
  --cert "$PY/lib/python3.13/site-packages/certifi/cacert.pem" \
  --index-url https://raw.githubusercontent.com/MobileStudio-AndroidIDE/MobileStudio-AndroidPython/main/simple/ \
  numpy pandas matplotlib
```

- `--index-url`: PEP 503 simple index (`simple/` 디렉터리, raw.githubusercontent로 서빙)
- wheel 파일은 GitHub Release `android-arm64-py313-v1` 에셋에서 다운로드됩니다.
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

| 패키지 | 이유 |
|--------|------|
| scipy | Fortran(flang) 툴체인 필요 — NDK에 Fortran 컴파일러 없음 |
| scikit-learn | scipy 런타임 의존 |
| scikit-image | scipy 런타임 의존 |
| numba | LLVM(llvmlite) 크로스빌드 필요 |
| onnx / onnxruntime | 대형 C++/Bazel 빌드, protobuf C++ 필요 |
| tflite-runtime | Bazel 빌드 필요 |
| opencv-python-headless | CMake 대형 빌드 (추후 지원 예정) |
| sentencepiece | SWIG 바인딩 + CMake 빌드 필요 (추후 지원 예정) |

protobuf는 순수 Python 구현(`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`)으로
동작합니다.
