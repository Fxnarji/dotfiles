#!/bin/bash
set -euo pipefail

WALL="${1:-}"

if [[ -z "$WALL" ]]; then
  echo "Usage: $0 /path/to/wallpaper"
  exit 1
fi

if [[ ! -f "$WALL" ]]; then
  echo "Invalid wallpaper path: $WALL"
  exit 1
fi

echo "Generating theme for: $WALL"
matugen image "$WALL" --mode dark

echo "Done."
