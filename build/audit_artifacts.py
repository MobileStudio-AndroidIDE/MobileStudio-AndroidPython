#!/usr/bin/env python3
"""Audit built artifacts for Android compatibility.

Checks wheel tags, shared library dependencies, and ABI compatibility.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ArtifactIssue:
    severity: str  # "error", "warning", "info"
    message: str
    file: str | None = None


@dataclass
class AuditResult:
    wheel: Path
    issues: list[ArtifactIssue] = field(default_factory=list)
    wheel_tag: str | None = None
    abis: list[str] = field(default_factory=list)
    shared_libs: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)


def audit_wheel(wheel_path: Path) -> AuditResult:
    """Audit a single wheel file."""
    result = AuditResult(wheel=wheel_path)

    with zipfile.ZipFile(wheel_path) as zf:
        names = zf.namelist()

        # Parse wheel tag from filename
        # Format: {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl
        fname = wheel_path.name
        parts = fname.replace(".whl", "").split("-")
        if len(parts) >= 5:
            result.wheel_tag = parts[-1]
            result.abis = [parts[-2]]

        # Check for shared libraries
        for name in names:
            if name.endswith(".so"):
                result.shared_libs.append(name)
            if name.endswith(".dist-info/entry_points.txt"):
                content = zf.read(name).decode("utf-8")
                for line in content.splitlines():
                    if line.strip() and not line.startswith("["):
                        result.entry_points.append(line.strip())

        # Check for x86_64 libraries (wrong ABI)
        for name in names:
            if "x86_64" in name or "amd64" in name:
                result.issues.append(ArtifactIssue(
                    severity="error",
                    message=f"x86_64 artifact found in ARM64 wheel: {name}",
                    file=name,
                ))

        # Check for missing android tag
        if result.wheel_tag and "android" not in result.wheel_tag:
            result.issues.append(ArtifactIssue(
                severity="warning",
                message=f"Wheel tag does not contain 'android': {result.wheel_tag}",
                file=wheel_path.name,
            ))

        # Check shared library dependencies with readelf if available
        for so_name in result.shared_libs:
            # Extract to temp and check
            import tempfile
            with tempfile.TemporaryDirectory() as tmpdir:
                zf.extract(so_name, tmpdir)
                so_path = Path(tmpdir) / so_name
                try:
                    result_so = subprocess.run(
                        ["readelf", "-d", str(so_path)],
                        capture_output=True, text=True, timeout=10
                    )
                    if result_so.returncode == 0:
                        for line in result_so.stdout.splitlines():
                            if "NEEDED" in line:
                                lib = line.split("[")[1].split("]")[0]
                                result.issues.append(ArtifactIssue(
                                    severity="info",
                                    message=f"Shared lib dependency: {lib}",
                                    file=so_name,
                                ))
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Audit Android Python wheel artifacts")
    parser.add_argument("wheels", type=Path, nargs="+", help="Wheel files to audit")
    parser.add_argument("--json", type=Path, help="Write JSON report to file")
    parser.add_argument("--fail-on-warning", action="store_true",
                        help="Treat warnings as errors")

    args = parser.parse_args()

    results = []
    for wheel in args.wheels:
        if not wheel.exists():
            print(f"Wheel not found: {wheel}", file=sys.stderr)
            sys.exit(1)
        result = audit_wheel(wheel)
        results.append(result)

    # Print report
    all_passed = True
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"\n{r.wheel.name}: {status}")
        print(f"  Wheel tag: {r.wheel_tag}")
        print(f"  ABIs: {r.abis}")
        print(f"  Shared libs: {len(r.shared_libs)}")
        print(f"  Entry points: {len(r.entry_points)}")
        for issue in r.issues:
            marker = "ERROR" if issue.severity == "error" else "WARN"
            print(f"  [{marker}] {issue.message}" +
                  (f" ({issue.file})" if issue.file else ""))
        if not r.passed:
            all_passed = False

    # Write JSON report
    if args.json:
        report = {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "artifacts": [
                {
                    "wheel": str(r.wheel),
                    "wheel_tag": r.wheel_tag,
                    "abis": r.abis,
                    "shared_libs": r.shared_libs,
                    "entry_points": r.entry_points,
                    "passed": r.passed,
                    "issues": [
                        {
                            "severity": i.severity,
                            "message": i.message,
                            "file": i.file,
                        }
                        for i in r.issues
                    ],
                }
                for r in results
            ],
        }
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to {args.json}")

    if args.fail_on_warning:
        for r in results:
            for i in r.issues:
                if i.severity in ("error", "warning"):
                    all_passed = False

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
