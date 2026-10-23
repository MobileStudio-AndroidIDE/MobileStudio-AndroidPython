#!/usr/bin/env python3
"""Pack a pre-built package tree into an Android ARM64 wheel.

Used by the hand-rolled native builds (propcache, msgpack, uvloop, ...)
whose upstream build systems assume a glibc host.

Example:
    python3 scripts/make_wheel.py \
        --name propcache --version 0.5.4 \
        --tree build/native/propcache/stage \
        --out wheelhouse \
        --summary "Fast property caching" \
        --requires "typing-extensions; python_version < '3.11'"

The tree must contain the importable package directories at its root.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import sys
import zipfile
from pathlib import Path

TAG = "cp313-cp313-android_28_arm64_v8a"
WHEEL_FILE = "WHEEL"
METADATA_FILE = "METADATA"
RECORD_FILE = "RECORD"


def urlsafe_b64_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def record_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    digest = urlsafe_b64_nopad(h.digest())
    return f"sha256={digest}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--tree", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--summary", default="")
    parser.add_argument("--requires", action="append", default=[])
    parser.add_argument("--tag", default=TAG)
    parser.add_argument("--purelib", action="store_true")
    args = parser.parse_args()

    tree: Path = args.tree
    if not tree.is_dir():
        raise SystemExit(f"tree not found: {tree}")

    dist = args.name.replace("-", "_").replace(".", "_")
    info_dir = f"{dist}-{args.version}.dist-info"
    wheel_name = f"{dist}-{args.version}-{args.tag}.whl"
    out_path = args.out / wheel_name
    args.out.mkdir(parents=True, exist_ok=True)

    metadata = [
        "Metadata-Version: 2.1",
        f"Name: {args.name}",
        f"Version: {args.version}",
    ]
    if args.summary:
        metadata.append(f"Summary: {args.summary}")
    metadata.extend(f"Requires-Dist: {req}" for req in args.requires)
    metadata.append("")

    wheel_meta = [
        "Wheel-Version: 1.0",
        "Generator: mobilestudio-android-wheelhouse",
        "Root-Is-Purelib: true" if args.purelib else "Root-Is-Purelib: false",
        f"Tag: {args.tag}",
        "",
    ]

    entries: list[tuple[str, bytes]] = []
    for path in sorted(tree.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(tree).as_posix()
        entries.append((rel, path.read_bytes()))

    entries.append((f"{info_dir}/METADATA", ("\n".join(metadata) + "\n").encode()))
    entries.append((f"{info_dir}/WHEEL", ("\n".join(wheel_meta) + "\n").encode()))

    record_lines = []
    for name, data in entries:
        digest = urlsafe_b64_nopad(hashlib.sha256(data).digest())
        record_lines.append(f"{name},sha256={digest},{len(data)}")
    record_lines.append(f"{info_dir}/RECORD,,")
    entries.append((f"{info_dir}/RECORD", ("\n".join(record_lines) + "\n").encode()))

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)

    print(out_path)


if __name__ == "__main__":
    main()
