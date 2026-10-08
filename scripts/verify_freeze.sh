#!/usr/bin/env bash
# Verify the pre-registered forecast against the fingerprint published on 8 Oct 2026.
# The freeze is the tagged commit; files like README.md have evolved since, so we check the tag itself.
set -euo pipefail
EXPECTED="e9753a97bafee5a04ce2c9229f843ed216f3e2459d97cd33a45006028530cf1a"
TMP=$(mktemp -d)
git archive freeze-2026-10-08 | tar -x -C "$TMP"
cd "$TMP"
shasum -a 256 -c MANIFEST.sha256 --quiet && echo "All $(wc -l < MANIFEST.sha256 | tr -d ' ') frozen files match MANIFEST.sha256"
ACTUAL=$(shasum -a 256 MANIFEST.sha256 | cut -d' ' -f1)
[ "$ACTUAL" = "$EXPECTED" ] && echo "MANIFEST fingerprint matches the published hash: $ACTUAL" || { echo "MISMATCH: $ACTUAL"; exit 1; }
# and the frozen forecast files are still byte-identical on the current branch
cd - > /dev/null
for f in $(awk '{print $2}' "$TMP/MANIFEST.sha256" | grep '^freeze/'); do cmp -s "$f" "$TMP/$f" || { echo "CHANGED: $f"; exit 1; }; done
echo "freeze/ on this branch is unchanged"
rm -rf "$TMP"
