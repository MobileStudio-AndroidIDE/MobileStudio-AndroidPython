# Android ARM64 네이티브 패키지 크로스빌드 플레이북

CPython 3.13 (`android-28-arm64_v8a`) 타깃으로 meson/setuptools 기반 네이티브
패키지를 빌드하는 절차. 모든 빌드는 NDK r28 clang으로 수행된다.

## 1. 공통 인프라

### 1.1 sysconfig shim (`/tmp/opencode/cross-shim/`)

meson의 python 모듈은 크로스 환경에서 타깃 파이썬의 sysconfig를 요구한다.
호스트 CPython 3.13(같은 버전) 위에 `sitecustomize.py`로 Android sysconfig
값을 덮어쓰는 래퍼를 만든다.

* `_sysconfigdata__android_aarch64-linux-android.py`를 로드해
  `sysconfig._CONFIG_VARS`를 교체
* `/data/local/tmp/python-android` → `/home/limsemin/AndroidPython` 치환
* `include/cpython3.13` → `include/python3.13` 경로 보정

검증:

```
cross-shim/python3.13 -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))"
# .cpython-313-aarch64-linux-android.so
```

### 1.2 meson cross file (`/tmp/opencode/cross/android-aarch64.ini`)

```ini
[binaries]
c/cpp/ar/strip = NDK clang
pkg-config = /usr/bin/pkg-config
python = cross-shim/python3.13
numpy-config = cross-bin/numpy-config      # Android numpy 헤더 반환
pybind11-config = cross-bin/pybind11-config
f2py = cross-bin/f2py                      # 호스트 numpy 2.5.4 위임(-v 포함)

[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'aarch64'
endian = 'little'

[properties]
needs_exe_wrapper = true
longdouble_format = 'IEEE_QUAD_LE'         # numpy 요구
```

주의: config-tool(numpy-config, pybind11-config, f2py)은 크로스 빌드에서
PATH가 아니라 **cross file [binaries]** 에서만 찾는다.

### 1.3 pkg-config 스텁

* `python3.pc`, `python-3.13.pc` — CPython 크로스빌드가 설치하는 pc는
  `$(BLDLIBRARY)`/기기 경로를 포함해 망가졌으므로 앞에서 Override
* `openblas.pc` — Chaquopy openblas wheel 압축 해제본 사용
* `freetype.pc` — Chaquopy freetype wheel

### 1.4 링크 규칙

* 모든 확장 모듈은 `-lpython3.13` 명시 링크 (Android 링커는 인터프리터가
  심볼을 export하지 않음)
* `-L<ndk-libs>`(libm/libdl/libc 등 aarch64 .so 심링크) 를
  `-L/usr/lib/x86_64-linux-gnu`보다 앞에 — 호스트 glibc 정적 라이브러리
  오염 방지

## 2. 빌드 레시피

### numpy 2.5.4 (meson-python)
```
pip wheel --no-build-isolation --no-deps \
  --config-settings=setup-args=--cross-file=<cross.ini> numpy-2.5.4/
```
생성 wheel 파일 태그는 cp312-linux_x86_64이므로
`wheel tags --python-tag cp313 --abi-tag cp313 --platform-tag android_28_arm64_v8a`로
재작성 (내부 .so는 이미 Android 접미사).

### scipy 1.18.1
* `meson.options`에서 `_without-fortran` 기본값 true로 변경 (odr 제외)
* `subprojects/duccfft/.../threading.cc`: `pthread_{get,set}affinity_np`를
  `!defined(__ANDROID__)`로 가드
* f2py는 **호스트 코드 제너레이터** → shim venv에 진짜 numpy 2.5.4 설치 후 위임
* 빌드 시간 ~20분, BLAS/LAPACK은 Chaquopy openblas (g77 ABI wrapper 포함)

### scikit-learn 1.9.1
* 빌드 시 `scipy.linalg.cython_blas.pxd` cimport → scipy 1.18 wheel에서
  생성된 pxd를 shim site-packages에 배치
* 런타임은 scipy 1.18의 `cython_blas.<abi>.so` capsule 사용

### pandas 2.3.3 / contourpy 1.4.0 / scikit-image 0.26.0
meson-python → 공통 절차와 동일. pandas는 `versioneer` 필요.

### h5py 3.16.0 (setuptools)
HDF5 1.14.6을 먼저 NDK CMake로 정적 빌드 후
`setup.py build_ext` + `HDF5_DIR`, 감지용 `libhdf5.so.stub`(x86) 트릭.
`.so` 접미사 수동 변경 필요.

### matplotlib 3.8.4 (setuptools)
`certifi` 필요(번들 freetype 2.6.1 다운로드) 또는 Chaquopy freetype.pc.
`setup.py build_ext --inplace` 후 .so 접미사 변경.

## 3. 알려진 함정

| 증상 | 원인 | 해결 |
|------|------|------|
| `Cannot compile Python.h` | pc 파일이 기기 경로 | python3.pc override |
| `Compiler cython cannot compile` | cython 언어 sanity가 호스트 헤더 사용 | python3.pc 제공 |
| `long double` 감지 실패 | cross에서 run() 불가 | `longdouble_format` 속성 |
| f2py too old | venv의 구버전 numpy f2py | numpy 2.x 설치 + 위임 |
| pthread_getaffinity_np | bionic 미지원 | `!defined(__ANDROID__)` 가드 |
| `--fix-cortex-a53-843419` 에러 | x86 정적 lib 혼입 | ndk-libs -L 우선 |
