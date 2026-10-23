#!/usr/bin/env python3
"""Build the Android ARM64 / CPython 3.13 wheelhouse and PEP 503 index.

Sources
-------
* pure-python wheels from PyPI (``py3-none-any``)
* Android ARM64 wheels published by the Chaquopy project, retagged from
  ``android_21``/``android_24`` to ``android_28`` so that pip on our
  CPython 3.13 build (``sysconfig.get_platform() == android-28-arm64_v8a``)
  accepts them
* wheels built locally with the NDK (``build/wheels``, ``dist``)

Usage
-----
    python3 scripts/build_wheelhouse.py fetch
    python3 scripts/build_wheelhouse.py index
    python3 scripts/build_wheelhouse.py manifest
    python3 scripts/build_wheelhouse.py all
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WHEELHOUSE = ROOT / "wheelhouse"
SIMPLE = ROOT / "simple"
BUILD_WHEELS = ROOT / "build" / "wheels"
DIST = ROOT / "dist"

REPO = "MobileStudio-AndroidIDE/MobileStudio-AndroidPython"
RELEASE_TAG = "android-arm64-py313-v1"
BASE_URL = f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}"

CHAQUO = "https://chaquo.com/pypi-13.1"

# (distribution name on chaquo.com, wheel filename)
CHAQUOPY_WHEELS = [
    ("numpy", "numpy-1.26.2-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("pandas", "pandas-2.1.3-1-cp313-cp313-android_24_arm64_v8a.whl"),
    ("pillow", "pillow-11.0.0-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("matplotlib", "matplotlib-3.8.4-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("cryptography", "cryptography-42.0.8-1-cp313-cp313-android_24_arm64_v8a.whl"),
    ("lxml", "lxml-5.3.0-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("pyyaml", "pyyaml-6.0.3-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("psutil", "psutil-7.1.3-1-cp313-cp313-android_24_arm64_v8a.whl"),
    ("regex", "regex-2024.9.11-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("lz4", "lz4-4.3.3-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("zstandard", "zstandard-0.23.0-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("cffi", "cffi-1.17.1-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("pycocotools", "pycocotools-2.0.8-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("aiohttp", "aiohttp-3.10.10-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("markupsafe", "markupsafe-3.0.3-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("contourpy", "contourpy-1.0.7-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("kiwisolver", "kiwisolver-1.4.7-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("multidict", "multidict-6.1.0-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("frozenlist", "frozenlist-1.4.1-0-cp313-cp313-android_24_arm64_v8a.whl"),
    ("yarl", "yarl-1.16.0-0-cp313-cp313-android_24_arm64_v8a.whl"),
    # native libraries used by the wheels above
    ("chaquopy-openblas", "chaquopy_openblas-0.2.20-5-py3-none-android_21_arm64_v8a.whl"),
    ("chaquopy-libgfortran", "chaquopy_libgfortran-4.9-0-py3-none-android_21_arm64_v8a.whl"),
    ("chaquopy-libcxx", "chaquopy_libcxx-180000-0-py3-none-android_24_arm64_v8a.whl"),
    ("chaquopy-freetype", "chaquopy_freetype-2.9.1-2-py3-none-android_21_arm64_v8a.whl"),
    ("chaquopy-libjpeg", "chaquopy_libjpeg-1.5.3-1-py3-none-android_21_arm64_v8a.whl"),
    ("chaquopy-libpng", "chaquopy_libpng-1.6.34-1-py3-none-android_21_arm64_v8a.whl"),
    ("chaquopy-libyaml", "chaquopy_libyaml-0.2.5-0-py3-none-android_24_arm64_v8a.whl"),
    ("chaquopy-libxml2", "chaquopy_libxml2-2.9.8-2-py3-none-android_21_arm64_v8a.whl"),
    ("chaquopy-libxslt", "chaquopy_libxslt-1.1.32-2-py3-none-android_21_arm64_v8a.whl"),
    ("chaquopy-libffi", "chaquopy_libffi-3.3-3-py3-none-android_24_arm64_v8a.whl"),
]

# Pure-python distributions hosted in the same index so that installing the
# native packages above is fully self-contained (no PyPI access required).
PURE_PACKAGES = [
    # A. tooling / network
    "pip",
    "packaging",
    "setuptools",
    "wheel",
    "requests",
    "urllib3",
    "certifi",
    "charset-normalizer",
    "idna",
    "httpx",
    "httpcore",
    "h11",
    "anyio",
    "sniffio",
    "websockets",
    "aiohappyeyeballs",
    "aiosignal",
    "attrs",
    "shellingham",
    "annotated-doc",
    "annotated-types",
    "typing-extensions",
    "typing-inspection",
    # B. data / serialisation
    "sympy",
    "mpmath",
    "tomli",
    "protobuf",
    "cython",
    "beautifulsoup4",
    "soupsieve",
    "python-dateutil",
    "six",
    "pytz",
    "tzdata",
    "cycler",
    "fonttools",
    "pyparsing",
    "pycparser",
    # C. imaging helpers
    "imageio",
    "tifffile",
    "lazy-loader",
    # F. science / utilities
    "networkx",
    "joblib",
    "tqdm",
    "rich",
    "markdown-it-py",
    "mdurl",
    "pygments",
    "click",
    "typer",
    "jinja2",
    "jsonschema",
    "jsonschema-specifications",
    "referencing",
    "rpds-py",
    "sqlite-utils",
    "sqlite-fts4",
    "click-default-group",
    "tabulate",
    "pluggy",
    "pydantic",
    "threadpoolctl",
    "huggingface-hub==0.25.2",
]

LIBS = [
    "chaquopy-openblas",
    "chaquopy-libgfortran",
    "chaquopy-libcxx",
    "chaquopy-freetype",
    "chaquopy-libjpeg",
    "chaquopy-libpng",
    "chaquopy-libyaml",
    "chaquopy-libxml2",
    "chaquopy-libxslt",
    "chaquopy-libffi",
]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def retag(path: Path) -> Path:
    """Rewrite an android_21/android_24 wheel tag to android_28."""
    if "android_28_arm64_v8a" in path.name:
        return path
    subprocess.run(
        [sys.executable, "-m", "wheel", "tags", "--platform-tag", "android_28_arm64_v8a", str(path)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    new_name = re.sub(r"android_(21|24)_arm64_v8a", "android_28_arm64_v8a", path.name)
    new_path = path.with_name(new_name)
    if new_path != path and new_path.exists():
        path.unlink()
    return new_path


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        # Chaquopy/HTTP servers return an HTML error page with 200 in some
        # cases; make sure we really got a zip file.
        try:
            with zipfile.ZipFile(dest):
                return dest
        except zipfile.BadZipFile:
            dest.unlink()
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as fh:
        shutil.copyfileobj(resp, fh)
    tmp.replace(dest)
    return dest


def fetch_chaquopy() -> None:
    WHEELHOUSE.mkdir(exist_ok=True)
    for dist, filename in CHAQUOPY_WHEELS:
        dest = WHEELHOUSE / filename
        print(f"[chaquopy] {filename}")
        download(f"{CHAQUO}/{dist}/{filename}", dest)
        retag(dest)


def fetch_pure() -> None:
    WHEELHOUSE.mkdir(exist_ok=True)
    for name in PURE_PACKAGES:
        print(f"[pypi]     {name}")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--only-binary=:all:",
                "--no-deps",
                "--dest",
                str(WHEELHOUSE),
                "--python-version",
                "3.13",
                "--implementation",
                "py",
                "--abi",
                "none",
                "--platform",
                "any",
                name,
            ],
            check=False,
        )


def collect_local() -> None:
    WHEELHOUSE.mkdir(exist_ok=True)
    for src in (BUILD_WHEELS, DIST):
        if not src.is_dir():
            continue
        for wheel in sorted(src.glob("*.whl")):
            target = WHEELHOUSE / wheel.name
            if not target.exists():
                shutil.copy2(wheel, target)
                print(f"[local]    {wheel.name}")


# --------------------------------------------------------------------------
# index + manifest
# --------------------------------------------------------------------------
WHEEL_RE = re.compile(
    r"^(?P<name>[^-]+)-(?P<version>[^-]+)(?:-(?P<build>[^-]+))?"
    r"-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<platform>[^-]+)\.whl$"
)


def wheel_info(path: Path) -> tuple[str, str] | None:
    m = WHEEL_RE.match(path.name)
    if not m:
        return None
    return canonical(m.group("name")), m.group("version")


def build_index() -> None:
    wheels = sorted(WHEELHOUSE.glob("*.whl"))
    if not wheels:
        raise SystemExit("wheelhouse is empty; run `fetch` first")

    by_package: dict[str, list[Path]] = {}
    manifest = []
    for wheel in wheels:
        info = wheel_info(wheel)
        if info is None:
            print(f"[skip]     unparsable filename: {wheel.name}", file=sys.stderr)
            continue
        name, version = info
        by_package.setdefault(name, []).append(wheel)
        manifest.append(
            {
                "package": name,
                "version": version,
                "filename": wheel.name,
                "sha256": sha256(wheel),
                "size": wheel.stat().st_size,
                "url": f"{BASE_URL}/{wheel.name}",
            }
        )

    if SIMPLE.exists():
        shutil.rmtree(SIMPLE)
    (SIMPLE).mkdir(parents=True)

    rows = []
    for name in sorted(by_package):
        pkg_dir = SIMPLE / name
        pkg_dir.mkdir(parents=True)
        links = []
        for wheel in sorted(by_package[name]):
            digest = sha256(wheel)
            links.append(
                f'<a href="{BASE_URL}/{html.escape(wheel.name)}#sha256={digest}">'
                f"{html.escape(wheel.name)}</a><br>"
            )
        (pkg_dir / "index.html").write_text(
            "<!DOCTYPE html><html><head><meta name=\"pypi:repository-version\" content=\"1.0\">"
            f"<title>Links for {html.escape(name)}</title></head><body>"
            f"<h1>Links for {html.escape(name)}</h1>" + "\n".join(links) + "</body></html>\n",
            encoding="utf-8",
        )
        rows.append(f'<a href="{name}/">{html.escape(name)}</a><br>')

    (SIMPLE / "index.html").write_text(
        "<!DOCTYPE html><html><head><meta name=\"pypi:repository-version\" content=\"1.0\">"
        "<title>MobileStudio Android ARM64 wheels</title></head><body>"
        "<h1>MobileStudio Android ARM64 wheels (CPython 3.13)</h1>" + "\n".join(rows) + "</body></html>\n",
        encoding="utf-8",
    )

    (ROOT / "wheelhouse" / "MANIFEST.json").write_text(
        json.dumps(
            {
                "python": "3.13",
                "abi": "arm64-v8a",
                "android_api": 28,
                "repository": REPO,
                "release": RELEASE_TAG,
                "base_url": BASE_URL,
                "wheels": sorted(manifest, key=lambda w: w["filename"]),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"indexed {len(manifest)} wheels in {len(by_package)} packages -> {SIMPLE}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["fetch", "fetch-chaquopy", "fetch-pure", "local", "index", "manifest", "all"],
    )
    args = parser.parse_args()

    if args.command in ("fetch", "fetch-chaquopy", "all"):
        fetch_chaquopy()
    if args.command in ("fetch", "fetch-pure", "all"):
        fetch_pure()
    if args.command in ("local", "all"):
        collect_local()
    if args.command in ("index", "all"):
        build_index()
    if args.command == "manifest":
        build_index()


if __name__ == "__main__":
    main()
