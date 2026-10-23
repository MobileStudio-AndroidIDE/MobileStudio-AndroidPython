# MobileStudio 앱에 Python 통합하기

앱(`com.aide.mobilestudio`)에서 번들된 CPython 3.13 + 58개 패키지를 사용하는 방법.

## 통합된 파일

| 위치 | 내용 |
|------|------|
| `app/src/main/java/com/aide/mobilestudio/python/PyBridge.java` | NDJSON 없이 동기 호출하는 Java 브리지 |
| `app/src/main/assets/mobilestudio-python.zip` | stdlib + 순수 site-packages + manifest (95 MB) |
| `app/src/main/jniLibs/arm64-v8a/libpyexec.so` | CPython 실행 파일 (PIE) |
| `app/src/main/jniLibs/arm64-v8a/libpython3.13.so` | CPython 런타임 |
| `app/src/main/jniLibs/arm64-v8a/libms*.so` | 448개 네이티브 확장 모듈 |
| `app/src/main/jniLibs/arm64-v8a/lib{openblas,gfortran,omp,freetype,...}.so` | 의존 라이브러리 |

## 왜 이렇게 하는가 (targetSdk 34 제약)

Android 10+ (targetSdk 29+)는 **앱 쓰기 가능 영역에서 exec/dlopen을 금지**합니다(W^X).
따라서:

1. 모든 `.so`는 APK 내부(`jniLibs`)에 있어야 하고 → 설치 시 `nativeLibraryDir`로 추출
   (`useLegacyPackaging = true` 필요 — 이미 앱에 설정됨)
2. 순수 Python 파일만 assets zip으로 `filesDir`에 풀어서 사용
3. `ms_ext_hook.py`가 import 시점에 `jniLibs`의 확장 모듈을 찾아 로드

## 사용법

```java
import com.aide.mobilestudio.python.PyBridge;

// 1) 코드 실행 (첫 호출 시 자동으로 zip 해제)
PyBridge.Result r = PyBridge.run(this,
    "import numpy as np; print(np.arange(9).reshape(3,3).sum())");
if (r.ok()) {
    Log.i("PY", r.stdout);   // 36
} else {
    Log.e("PY", r.stderr);
}

// 2) pip 사용 — 첫 호출이 pip.conf를 자동 생성하고
//    MobileStudio GitHub 릴리즈 인덱스에서 다운로드한다.
PyBridge.Result p = PyBridge.pip(this, "install", "requests");
// 순수 Python 패키지는 자유롭게 설치 가능.
// 네이티브 패키지는 이미 전부 번들되어 있으므로 설치 불필요.
```

## 백그라운드 실행 권장

```java
new Thread(() -> {
    try {
        PyBridge.Result r = PyBridge.run(getApplicationContext(),
            "import cv2, numpy as np; print(cv2.__version__)");
        runOnUiThread(() -> tv.setText(r.stdout));
    } catch (Exception e) { ... }
}).start();
```

## 내부 동작

1. `ensureReady()` — `filesDir/ms-python`에 assets zip 해제 (버전 마커로 1회만)
2. `exec()` — `nativeLibraryDir/libpyexec.so`를 `ProcessBuilder`로 실행.
   `+x` 비트가 없으면 `/system/bin/linker64` 경유로 재시도.
3. 환경 변수:
   - `PYTHONHOME=<filesDir>/ms-python`
   - `PYTHONPATH=<...>/site-packages`
   - `MS_NATIVE_LIB_DIR` / `MOBILESTUDIO_NATIVE_LIB_DIR` = `nativeLibraryDir`
   - `LD_LIBRARY_PATH=nativeLibraryDir`
   - `PIP_CONFIG_FILE=<root>/pip.conf`
4. `sitecustomize.py`가 pip 인덱스 자동 설정 + `ms_ext_hook` 설치.

## 번들 재생성

패키지를 추가/업데이트하면:

```bash
# AndroidPython 저장소에서
python3 tools/build_app_bundle.py
cp dist/app-bundle/assets/mobilestudio-python.zip  <앱>/app/src/main/assets/
cp dist/app-bundle/jniLibs/arm64-v8a/*.so          <앱>/app/src/main/jniLibs/arm64-v8a/
# libc++_shared.so는 앱 기존 파일 유지 (심볼 동일 확인됨)
cp dist/app-bundle/PyBridge.java                   <앱>/app/src/main/java/com/aide/mobilestudio/python/
```

앱의 `PyBridge.BUNDLE_VERSION`을 올리면 기기에서 재해제됩니다.

## 검증 상태 (2026-10-23, SM-S926N / Android 14)

앱 컨텍스트(`run-as com.aide.mobilestudio`, 실제 앱 UID)에서
`nativeLibraryDir`의 `libpyexec.so` 실행 + assets 번들 해제 환경으로
다음 전 항목 import/기능 테스트 통과 (`ALL-SMOKE-OK`):

| 패키지 | 버전 | 동작 확인 |
|--------|------|-----------|
| numpy | 2.5.4 | 행렬 합 36 |
| cv2 (opencv-python-headless) | 4.11.0 | cvtColor |
| scipy | 1.18.1 | linalg.inv |
| pandas | 2.3.3 | DataFrame sum |
| scikit-learn | 1.9.1 | LinearRegression fit |
| matplotlib | 3.8.4 | Agg plot |
| onnx | 1.23.2 | make_model |
| onnxruntime | 1.31.0 | CPUExecutionProvider |
| tflite-runtime | 2.20.0 | Interpreter |
| tokenizers | 0.23.3 | import |
| safetensors | 0.8.0 | import |
| numba | 0.68.0 | @njit 컴파일 실행 (jit(10)=45) |
| pydantic | 2.14.1 | BaseModel 검증 |

APK: 디버그 빌드 403 MB (`app-debug.apk`), 설치 후 정상 기동 확인.

## 문제 해결

| 증상 | 원인/해결 |
|------|-----------|
| `ModuleNotFoundError` (네이티브) | `MS_NATIVE_LIB_DIR`가 설정됐는지, manifest에 모듈이 있는지 확인 |
| `dlopen failed: library ... not found` | 의존 `.so`가 jniLibs에 있는지 확인 |
| `libpyexec.so: cannot execute` | PyBridge가 자동으로 link64 폴백 — 로그 확인 |
| pip이 PyPI에서 설치 | `pip.conf` 확인 (`only-binary`, index-url) |
