#!/usr/bin/env python3
"""Regenerate compatibility/package-status.json from the wheelhouse manifest."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "wheelhouse" / "MANIFEST.json"
STATUS = ROOT / "compatibility" / "package-status.json"

# The 60 packages requested for MobileStudio (duplicates removed).
REQUESTED = [
    "packaging", "setuptools", "wheel", "pip", "requests", "urllib3",
    "certifi", "charset-normalizer", "idna", "httpx", "aiohttp", "websockets",
    "numpy", "pandas", "scipy", "sympy", "mpmath", "pyyaml", "tomli",
    "orjson", "msgpack", "protobuf", "lxml", "beautifulsoup4",
    "pillow", "opencv-python-headless", "scikit-image", "imageio", "tifffile",
    "pycocotools",
    "scikit-learn", "onnx", "onnxruntime", "tokenizers", "safetensors",
    "sentencepiece", "tflite-runtime", "h5py",
    "cython", "cffi", "cryptography", "lz4", "zstandard", "regex", "psutil",
    "uvloop", "orjson", "sqlite-utils",
    "matplotlib", "networkx", "numba", "joblib", "tqdm", "rich", "click",
    "typer", "jinja2", "jsonschema", "pydantic",
]

BLOCKED = {
    "scipy": "Fortran (flang) toolchain required; no NDK Fortran compiler",
    "scikit-learn": "requires scipy at runtime",
    "scikit-image": "requires scipy at runtime",
    "numba": "requires LLVM (llvmlite) cross-build",
    "onnx": "requires protobuf C++ + large CMake build",
    "onnxruntime": "requires Bazel/large C++ build",
    "tflite-runtime": "requires Bazel build",
}

PENDING = {
    "onnxruntime": "large C++ build in progress",
    "tflite-runtime": "Bazel build planned",
    "numba": "LLVM (llvmlite) cross-build planned",
}

CATEGORY = {
    "packaging": "A", "setuptools": "A", "wheel": "A", "pip": "A",
    "requests": "A", "urllib3": "A", "certifi": "A", "charset-normalizer": "A",
    "idna": "A", "httpx": "A", "aiohttp": "A", "websockets": "A",
    "numpy": "B", "pandas": "B", "scipy": "B", "sympy": "B", "mpmath": "B",
    "pyyaml": "B", "tomli": "B", "orjson": "B", "msgpack": "B",
    "protobuf": "B", "lxml": "B", "beautifulsoup4": "B",
    "pillow": "C", "opencv-python-headless": "C", "scikit-image": "C",
    "imageio": "C", "tifffile": "C", "pycocotools": "C",
    "scikit-learn": "D", "onnx": "D", "onnxruntime": "D", "tokenizers": "D",
    "safetensors": "D", "sentencepiece": "D", "tflite-runtime": "D", "h5py": "D",
    "cython": "E", "cffi": "E", "cryptography": "E", "lz4": "E",
    "zstandard": "E", "regex": "E", "psutil": "E", "uvloop": "E",
    "orjson": "E", "sqlite-utils": "E",
    "matplotlib": "F", "networkx": "F", "numba": "F", "joblib": "F",
    "tqdm": "F", "rich": "F", "click": "F", "typer": "F", "jinja2": "F",
    "jsonschema": "F", "pydantic": "F",
}


def canonical(name: str) -> str:
    import re
    return re.sub(r"[-_.]+", "-", name).lower()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    wheels: dict[str, dict] = {}
    for w in manifest["wheels"]:
        wheels.setdefault(w["package"], w)

    packages = {}
    seen = set()
    for name in REQUESTED:
        if name in seen:
            continue
        seen.add(name)
        entry: dict = {"category": CATEGORY.get(name, "?")}
        wheel = wheels.get(canonical(name))
        if name in BLOCKED:
            entry.update(status="unsupported", note=BLOCKED[name])
        elif wheel is not None:
            entry.update(
                status="available",
                version=wheel["version"],
                wheel=wheel["filename"],
                sha256=wheel["sha256"],
            )
        elif name in PENDING:
            entry.update(status="pending", note=PENDING[name])
        else:
            entry.update(status="missing")
        packages[name] = entry

    available = [n for n, v in packages.items() if v["status"] == "available"]
    status = {
        "python_version": "3.13.0",
        "android_abi": "arm64-v8a",
        "android_api": 28,
        "index": "https://raw.githubusercontent.com/MobileStudio-AndroidIDE/"
                 "MobileStudio-AndroidPython/main/simple/",
        "release": "https://github.com/MobileStudio-AndroidIDE/"
                   "MobileStudio-AndroidPython/releases/tag/android-arm64-py313-v1",
        "packages": packages,
        "summary": {
            "requested_unique": len(seen),
            "available": len(available),
            "blocked": sum(1 for v in packages.values() if v["status"] == "unsupported"),
            "pending": sum(1 for v in packages.values() if v["status"] == "pending"),
        },
    }
    STATUS.write_text(json.dumps(status, indent=2) + "\n")
    print(f"available: {status['summary']['available']}/{status['summary']['requested_unique']}")


if __name__ == "__main__":
    main()
