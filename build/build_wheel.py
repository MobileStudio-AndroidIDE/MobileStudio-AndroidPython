#!/usr/bin/env python3
"""Build Python wheels for Android ARM64.

This script builds native Python packages into Android-compatible wheels
using the cross-compiled Python 3.13 runtime and NDK toolchain.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from cross_compile import AndroidNDK, AndroidPython, load_recipe, run


def build_wheel(recipe_path: Path, ndk: AndroidNDK, apython: AndroidPython,
                workdir: Path) -> Path:
    """Build a wheel from a recipe. Returns the wheel path."""
    recipe = load_recipe(recipe_path)
    pkg = recipe["package"]
    build_cfg = recipe["build"]

    name = pkg["name"]
    version = pkg["version"]
    pkg_type = pkg.get("type", "pure-python")

    # Create build directory
    build_dir = workdir / f"{name}-{version}-build"
    build_dir.mkdir(parents=True, exist_ok=True)

    # Download source if URL provided
    source = recipe.get("source", {})
    source_url = source.get("url")
    source_sha256 = source.get("sha256")

    if source_url:
        src_archive = workdir / f"{name}-{version}.tar.gz"
        if not src_archive.exists():
            import urllib.request
            print(f"Downloading {source_url}")
            urllib.request.urlretrieve(source_url, src_archive)

        # Verify checksum
        if source_sha256:
            import hashlib
            h = hashlib.sha256()
            with open(src_archive, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            if h.hexdigest() != source_sha256:
                print(f"Checksum mismatch for {source_url}", file=sys.stderr)
                sys.exit(1)

        # Extract
        src_dir = build_dir / "source"
        src_dir.mkdir(exist_ok=True)
        subprocess.run(["tar", "-xzf", str(src_archive), "-C", str(src_dir),
                       "--strip-components=1"], check=True)
    else:
        src_dir = build_dir / "source"
        src_dir.mkdir(exist_ok=True)

    # Build
    env = ndk.env()
    env["ANDROID_PYTHON_ROOT"] = str(apython.root)
    env["ANDROID_PYTHON"] = str(apython.python)
    env["PYTHONPATH"] = str(apython.lib)

    pkg_type = recipe["package"].get("type", "pure-python")

    if pkg_type == "pure-python":
        # Pure Python: just copy or use setup.py bdist_wheel
        setup_py = src_dir / "setup.py"
        if setup_py.exists():
            run([str(apython.python), "setup.py", "bdist_wheel",
                 "--dist-dir", str(workdir / "dist")],
                env=env, cwd=src_dir)
        else:
            # No setup.py - just create wheel from package files
            raise NotImplementedError(
                f"Pure Python package {name} without setup.py not yet supported"
            )
    else:
        # Native extension: use pip wheel or setup.py
        run([str(apython.python), "-m", "pip", "wheel", ".",
             "--no-deps", "--no-build-isolation",
             "-w", str(workdir / "dist")],
            env=env, cwd=src_dir)

    # Find the wheel
    dist_dir = workdir / "dist"
    wheels = list(dist_dir.glob("*.whl"))
    if not wheels:
        print("No wheel produced", file=sys.stderr)
        sys.exit(1)

    wheel = wheels[0]
    print(f"Built wheel: {wheel} ({wheel.stat().st_size} bytes)")
    return wheel


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build Android Python wheels")
    parser.add_argument("recipe", type=Path, help="Path to recipe.yaml")
    parser.add_argument("--ndk", type=Path, required=True, help="NDK path")
    parser.add_argument("--android-python", type=Path, required=True,
                        help="Android Python root")
    parser.add_argument("--api-level", type=int, default=28)
    parser.add_argument("--workdir", type=Path, default=Path("./build-work"),
                        help="Working directory")

    args = parser.parse_args()

    ndk = AndroidNDK(args.ndk, api_level=args.api_level)
    missing = ndk.verify()
    if missing:
        print(f"Missing NDK tools: {missing}", file=sys.stderr)
        sys.exit(1)

    apython = AndroidPython(args.android_python)
    missing = apython.verify()
    if missing:
        print(f"Missing Android Python files: {missing}", file=sys.stderr)
        sys.exit(1)

    workdir = args.workdir
    workdir.mkdir(parents=True, exist_ok=True)

    wheel = build_wheel(args.recipe, ndk, apython, workdir)
    print(f"\nSuccess: {wheel}")


if __name__ == "__main__":
    main()
