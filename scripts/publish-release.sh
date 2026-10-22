#!/bin/bash
set -euo pipefail

# MobileStudio Android Python - Publish Release Script
# Publishes wheels to GitHub Releases with checksums

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DISTDIR="${DISTDIR:-$REPO_ROOT/dist}"

REPO="${REPO:-MobileStudio-AndroidIDE/MobileStudio-AndroidPython}"
TAG="${TAG:-}"
RELEASE_NAME="${RELEASE_NAME:-}"

echo "============================================"
echo "MobileStudio Android Python - Publish Release"
echo "Repo: $REPO"
echo "============================================"

# Check gh
if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: gh (GitHub CLI) not found"
    exit 1
fi

# Check auth
if ! gh auth status >/dev/null 2>&1; then
    echo "ERROR: Not authenticated with gh"
    echo "Run: gh auth login"
    exit 1
fi

# Determine tag
if [ -z "$TAG" ]; then
    TAG=$(date +%Y%m%d)-android-arm64
    echo "Using auto-generated tag: $TAG"
fi

# Check if tag already exists
if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
    echo "WARNING: Release $TAG already exists"
    read -p "Continue anyway? (y/N): " -r
    if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create release
echo ""
echo "Creating release: $TAG"
gh release create "$TAG" \
    --repo "$REPO" \
    --name "${RELEASE_NAME:-Android ARM64 Python 3.13 Packages - $TAG}" \
    --generate-notes \
    --target main 2>&1

# Upload wheels
echo ""
echo "Uploading wheels..."
for wheel in "$DISTDIR"/*.whl; do
    [ -f "$wheel" ] || continue
    echo "  Uploading: $(basename "$wheel")"
    gh release upload "$TAG" "$wheel" --repo "$REPO" --clobber 2>&1
done

# Generate and upload checksums
CHECKSUM_FILE="$DISTDIR/checksums.sha256"
cd "$DISTDIR"
sha256sum *.whl > "$CHECKSUM_FILE"
cd "$REPO_ROOT"

echo ""
echo "Uploading checksums..."
gh release upload "$TAG" "$CHECKSUM_FILE" --repo "$REPO" --clobber 2>&1

echo ""
echo "============================================"
echo "Release Published: $TAG"
echo "URL: https://github.com/$REPO/releases/tag/$TAG"
echo "============================================"
