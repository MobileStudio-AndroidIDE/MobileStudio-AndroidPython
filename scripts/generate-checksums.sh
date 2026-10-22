#!/bin/bash
set -euo pipefail

# MobileStudio Android Python - Generate Checksums Script
# Generates SHA-256 checksums for all wheels in dist/

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DISTDIR="${DISTDIR:-$REPO_ROOT/dist}"
OUTPUT="${OUTPUT:-$DISTDIR/checksums.sha256}"

echo "============================================"
echo "MobileStudio Android Python - Generate Checksums"
echo "Distdir: $DISTDIR"
echo "Output: $OUTPUT"
echo "============================================"

if [ ! -d "$DISTDIR" ]; then
    echo "ERROR: Dist directory not found: $DISTDIR"
    exit 1
fi

cd "$DISTDIR"

# Generate checksums
sha256sum *.whl > "$OUTPUT"

echo ""
echo "Checksums generated: $OUTPUT"
echo ""
cat "$OUTPUT"
echo ""
echo "Total: $(ls *.whl 2>/dev/null | wc -l) wheels"
