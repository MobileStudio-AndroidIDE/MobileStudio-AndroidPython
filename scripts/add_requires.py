#!/usr/bin/env python3
"""Append Requires-Dist entries to a wheel's METADATA (and fix RECORD).

    python3 scripts/add_requires.py wheelhouse/numpy-...whl \
        "chaquopy-openblas>=0.2.20" "chaquopy-libcxx>=180000"
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import zipfile
from pathlib import Path


def b64sha(data: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wheel", type=Path)
    ap.add_argument("requires", nargs="+")
    args = ap.parse_args()

    entries: list[tuple[str, bytes]] = []
    metadata_name = None
    with zipfile.ZipFile(args.wheel) as zf:
        for info in zf.infolist():
            data = zf.read(info.filename)
            if info.filename.endswith(".dist-info/METADATA"):
                metadata_name = info.filename
            entries.append((info.filename, data))

    if metadata_name is None:
        raise SystemExit("no METADATA found")

    out_entries: list[tuple[str, bytes]] = []
    for name, data in entries:
        if name == metadata_name:
            text = data.decode("utf-8")
            head, _, body = text.partition("\n\n")
            lines = [l for l in head.splitlines()]
            for req in args.requires:
                if not any(l.startswith(f"Requires-Dist: {req.split(';')[0].split('>')[0].split('<')[0].split('==')[0].strip()}")
                           for l in lines):
                    lines.append(f"Requires-Dist: {req}")
            data = ("\n".join(lines) + "\n\n" + body).encode("utf-8")
        out_entries.append((name, data))

    record_name = next(n for n, _ in out_entries if n.endswith(".dist-info/RECORD"))
    lines = []
    for name, data in out_entries:
        if name == record_name:
            continue
        lines.append(f"{name},sha256={b64sha(data)},{len(data)}")
    lines.append(f"{record_name},,")

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in out_entries:
            if name == record_name:
                data = ("\n".join(lines) + "\n").encode()
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, data)

    args.wheel.write_bytes(out.getvalue())
    print(f"patched {args.wheel}: {', '.join(args.requires)}")


if __name__ == "__main__":
    main()
