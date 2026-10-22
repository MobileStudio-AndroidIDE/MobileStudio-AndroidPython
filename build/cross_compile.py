#!/usr/bin/env python3
"""Cross-compilation helper for Android ARM64 Python packages.

This module provides utilities for building Python packages targeting
Android ARM64 (aarch64) using the Android NDK toolchain.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AndroidNDK:
    """Android NDK configuration."""

    ndk_path: Path
    api_level: int = 28
    abi: str = "arm64-v8a"
    host_tag: str = "linux-x86_64"

    @property
    def toolchain_bin(self) -> Path:
        return self.ndk_path / "toolchains" / "llvm" / "prebuilt" / self.host_tag / "bin"

    @property
    def clang(self) -> Path:
        return self.toolchain_bin / f"aarch64-linux-android{self.api_level}-clang"

    @property
    def clangpp(self) -> Path:
        return self.toolchain_bin / f"aarch64-linux-android{self.api_level}-clang++"

    @property
    def ar(self) -> Path:
        return self.toolchain_bin / "llvm-ar"

    @property
    def ranlib(self) -> Path:
        return self.toolchain_bin / "llvm-ranlib"

    @property
    def strip(self) -> Path:
        return self.toolchain_bin / "llvm-strip"

    @property
    def sysroot(self) -> Path:
        return self.toolchain_bin / ".." / ".." / "sysroot"

    def env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Return environment variables for cross-compilation."""
        env = os.environ.copy()
        env["CC"] = str(self.clang)
        env["CXX"] = str(self.clangpp)
        env["AR"] = str(self.ar)
        env["RANLIB"] = str(self.ranlib)
        env["STRIP"] = str(self.strip)
        env["LD"] = str(self.toolchain_bin / "ld")
        env["NM"] = str(self.toolchain_bin / "llvm-nm")
        env["READELF"] = str(self.toolchain_bin / "llvm-readelf")
        env["OBJCOPY"] = str(self.toolchain_bin / "llvm-objcopy")
        env["ARFLAGS"] = "rcs"
        env["CFLAGS"] = (
            f"-O2 -fPIE -fPIC -DANDROID -D__ANDROID_API__={self.api_level} "
            f"-I{self.sysroot / 'usr' / 'include'}"
        )
        env["CXXFLAGS"] = env["CFLAGS"]
        env["LDFLAGS"] = (
            f"-pie -Wl,--build-id=sha1 -Wl,--no-rosegment -Wl,--no-undefined "
            f"-lm -L{self.sysroot / 'usr' / 'lib' / self.abi.replace('_', '-')}"
        )
        env["ANDROID_NDK_HOME"] = str(self.ndk_path)
        env["ANDROID_API"] = str(self.api_level)
        env["ANDROID_ABI"] = self.abi
        if extra:
            env.update(extra)
        return env

    def verify(self) -> list[str]:
        """Verify NDK toolchain is available. Returns list of missing tools."""
        missing = []
        for tool in [self.clang, self.ar, self.ranlib, self.strip]:
            if not tool.exists() or not os.access(tool, os.X_OK):
                missing.append(str(tool))
        return missing


@dataclass
class AndroidPython:
    """Android Python runtime configuration."""

    root: Path
    version: str = "3.13"
    abi: str = "arm64-v8a"
    api_level: int = 28

    @property
    def bin(self) -> Path:
        return self.root / "bin"

    @property
    def python(self) -> Path:
        return self.bin / f"python{self.version}"

    @property
    def pip(self) -> Path:
        return self.bin / f"pip{self.version}"

    @property
    def lib(self) -> Path:
        return self.root / "lib" / f"python{self.version}"

    @property
    def site_packages(self) -> Path:
        return self.lib / "site-packages"

    @property
    def include(self) -> Path:
        return self.root / "include" / f"python{self.version}"

    def verify(self) -> list[str]:
        """Verify Android Python runtime is available."""
        missing = []
        if not self.python.exists():
            missing.append(str(self.python))
        if not self.lib.exists():
            missing.append(str(self.lib))
        return missing


def load_recipe(recipe_path: Path) -> dict[str, Any]:
    """Load a recipe YAML file."""
    try:
        import yaml
    except ImportError:
        print("PyYAML not installed; install with: pip install pyyaml", file=sys.stderr)
        sys.exit(1)
    with open(recipe_path) as f:
        return yaml.safe_load(f)


def run(cmd: list[str], env: dict[str, str] | None = None, cwd: Path | None = None) -> None:
    """Run a command, streaming output."""
    print(f"+ {' '.join(cmd)}")
    result = subprocess.run(
        cmd, env=env or os.environ.copy(),
        cwd=str(cwd) if cwd else None,
        text=True,
    )
    if result.returncode != 0:
        print(f"Command failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)


def main() -> None:
    """Cross-compile helper CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Android ARM64 cross-compilation helper")
    sub = parser.add_subparsers(dest="command", required=True)

    sub_pkg = sub.add_parser("package", help="Build a package from recipe")
    sub_pkg.add_argument("recipe", type=Path, help="Path to recipe.yaml")
    sub_pkg.add_argument("--ndk", type=Path, required=True, help="NDK path")
    sub_pkg.add_argument("--android-python", type=Path, required=True, help="Android Python root")
    sub_pkg.add_argument("--api-level", type=int, default=28)

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

    recipe = load_recipe(args.recipe)
    print(f"Building {recipe['package']['name']} {recipe['package']['version']}")
    print(f"  NDK: {ndk.ndk_path}")
    print(f"  Android Python: {apython.root}")
    print(f"  ABI: {ndk.abi}, API: {ndk.api_level}")


if __name__ == "__main__":
    main()
