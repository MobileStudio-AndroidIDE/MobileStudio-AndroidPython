#!/usr/bin/env python3
"""Add a DT_NEEDED entry to every shared object inside a wheel.

Android's dynamic linker does not expose the interpreter's Python C API
symbols to dlopen'ed extensions, so every extension module must link
``libpython3.13.so`` explicitly.  Pure-Rust wheels built in abi3 mode omit
that dependency; this tool patches them in place and rewrites RECORD.

    python3 scripts/add_needed.py wheelhouse/foo.whl libpython3.13.so
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path


def b64sha(data: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("wheel", type=Path)
    ap.add_argument("needed", default="libpython3.13.so", nargs="?")
    ap.add_argument("--patchelf", default="patchelf")
    args = ap.parse_args()

    entries: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(args.wheel) as zf:
        for info in zf.infolist():
            data = zf.read(info.filename)
            if info.filename.endswith(".so"):
                with tempfile.NamedTemporaryFile(suffix=".so") as tmp:
                    tmp.write(data)
                    tmp.flush()
                    subprocess.run(
                        [args.patchelf, "--add-needed", args.needed, tmp.name],
                        check=True,
                    )
                    data = Path(tmp.name).read_bytes()
                print(f"patched {info.filename}")
            entries.append((info.filename, data))

    record_name = next((n for n, _ in entries if n.endswith(".dist-info/RECORD")), None)
    if record_name is None:
        raise SystemExit("no RECORD in wheel")

    lines = []
    for name, data in entries:
        if name == record_name:
            continue
        lines.append(f"{name},sha256={b64sha(data)},{len(data)}")
    lines.append(f"{record_name},,")

    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries:
            if name == record_name:
                data = ("\n".join(lines) + "\n").encode()
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zf.writestr(zi, data)

    args.wheel.write_bytes(out.getvalue())
    print(f"rewrote {args.wheel}")


if __name__ == "__main__":
    main()
