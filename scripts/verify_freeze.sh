#!/usr/bin/env bash
# Verify the pre-registered 2026/27 forecast against the fingerprint published on 8 Oct 2026.
set -euo pipefail
EXPECTED="e9753a97bafee5a04ce2c9229f843ed216f3e2459d97cd33a45006028530cf1a"
cd "$(dirname "$0")/../preregistration/2026-27"
shasum -a 256 -c MANIFEST.sha256 --quiet && echo "All $(wc -l < MANIFEST.sha256 | tr -d ' ') frozen files match MANIFEST.sha256"
ACTUAL=$(shasum -a 256 MANIFEST.sha256 | cut -d' ' -f1)
[ "$ACTUAL" = "$EXPECTED" ] && echo "Fingerprint matches the published hash: $ACTUAL" || { echo "MISMATCH: $ACTUAL"; exit 1; }
