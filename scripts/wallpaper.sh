#!/bin/bash
# Set wallpaper using wal and apply it to Hyprpaper

wal -i "$1" || exit 1

WALLPAPER=$(<~/.cache/wal/wal)

$WALLPAPER | wl-copy
awww img \
  --transition-type wipe --transition-angle 30 \
  --transition-step 30 \
  --transition-duration 1 \
  "$WALLPAPER"
