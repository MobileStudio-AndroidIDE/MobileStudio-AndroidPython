# MobileStudio Android Python 패키지 레시피 (Phase 2~4)

이 디렉터리는 Android ARM64용 Python 패키지 포팅 레시피를 관리합니다.
각 레시피는 패키지 이름 디렉터리로 구성되며, 다음과 같은 파일을 포함합니다:

  - recipe.yaml: 메타데이터 (이름, 버전, 소스 URL, 체크섬, 의존성, 빌드 명령)
  - build.sh: 소스 다운로드 → 구성 → 빌드 → 설치 스크립트
  - test.sh: import 테스트 + 기본 기능 테스트 (Android 기기/QEMU에서 실행)

## 패키지 분류

| 유형 | 예시 | 빌드 방식 |
|---|---|---|
| 순수 Python | packaging, setuptools, wheel, pip, requests, PyYAML | 일반적인 휠 빌드 |
| C/C++ 확장 | numpy, scipy, pillow, pandas, opencv-python-headless | NDK 교차 컴파일 |
| 외부 네이티브 의존 | cryptography, lz4, zstandard, lxml | 외부 라이브러리 사전 빌드 + 링크 |
| Android 미지원 | uvloop, numba, onnxruntime (조사 필요) | 지원 불가 사유 문서화 |

## Phase 2 핵심 패키지 (우선순위)

1. packaging
2. setuptools
3. wheel
4. pip
5. requests
6. PyYAML
7. Pillow

## Phase 3 네이티브 과학 패키지

8. numpy (최우선 — Phase 1 완료 후 즉시)
9. scipy
10. pandas
11. opencv-python-headless

## 레시피 포맷 예시 (recipe.yaml)

```yaml
package:
  name: numpy
  version: "1.26.4"
  source:
    url: "https://files.pythonhosted.org/packages/source/n/numpy/numpy-1.26.4.tar.gz"
    sha256: "..."
  dependencies: []
  build:
    system: setuptools
    host_python: "/path/to/android-python-3.13/bin/python"
    cc: "aarch64-linux-android28-clang"
    cflags: "-O2 -fPIE -fPIC"
    ldflags: "-pie"
  test:
    import: "numpy"
    command: "python -c 'import numpy; x=numpy.arange(5); assert int(x.sum())==10'"
```

## 테스트 최소 기준 (완료 조건)

- NumPy: `np.arange(5).sum() == 10`, `np.ones((2,3)).shape == (2,3)`
- Pillow: `Image.new("RGB",(16,16),(255,0,0))` 생성 및 저장/열기
- OpenCV: `cv2.cvtColor` 그레이스케일 변환, `cv2.__version__` 출력

## 저장소 구조 (기존 MobileStudio 존중)

MobileStudio-AndroidPython/
├── README.md
├── LICENSE (Apache-2.0)
├── pyproject.toml
├── build-android-python.sh      # Phase 1: CPython 3.13 교차 빌드
├── recipes/                     # 패키지별 레시피
│   ├── pure-python/
│   ├── numpy/
│   ├── pillow/
│   ├── scipy/
│   ├── opencv/
│   └── ...
├── build/                       # 빌드 스크립트
│   ├── cross_compile.py
│   ├── build_wheel.py
│   └── audit_artifacts.py
├── compatibility/               # 호환성 메타데이터
│   ├── python-3.13.json
│   └── package-status.json
├── scripts/                     # 자동화
│   ├── build-all.sh
│   ├── test-qemu.sh
│   ├── test-device.sh
│   ├── publish-release.sh
│   └── generate-checksums.sh
├── tools/                       # 도구
│   └── android_bundle.py        # Android 앱 임베딩 번들 조립
├── client/                      # 앱 클라이언트
│   └── android/
│       └── PyBridge.java
├── tests/                       # 테스트
│   ├── unit/
│   ├── import/
│   ├── numerical/
│   ├── native/
│   └── android/
└── docs/
    ├── android_embed.md
    └── knowledge_layers.md
