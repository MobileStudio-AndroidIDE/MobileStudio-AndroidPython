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
| onnxruntime | 대형 C++ 빌드 (onnx·protobuf 31은 이미 포팅됨, 전제 준비 완료) |
| tflite-runtime | Bazel + TensorFlow 모노레포 빌드 필요 |
| numba | LLVM 크로스빌드(llvmlite) 필요 |

protobuf는 순수 Python 구현(`PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python`)으로
동작하며, onnx는 NDK C++ protobuf 31.1로 직접 빌드되어 있습니다.

### numpy 2 생태계

scipy/sklearn/skimage/opencv/h5py/ml_dtypes/onnx는 numpy 2.x 헤더로 빌드되어
`pip install` 시 numpy 2.5.4(인덱스 최신)와 함께 설치됩니다. Chaquopy 기반
numpy 1.26.2 휠도 병행 제공되지만, 위 패키지들과 함께 쓰려면 numpy 2.5.4를
유지하세요. pandas 2.3.3 / matplotlib 3.8.4 / contourpy 1.4.0 / pycocotools
2.0.11 은 numpy 2용으로 재빌드된 버전입니다.
