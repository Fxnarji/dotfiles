#!/bin/bash
# Set wallpaper using wal and apply it to Hyprpaper

wal -i "$1" || exit 1

WALLPAPER=$(<~/.cache/wal/wal)

cat > ~/.config/hypr/hyprpaper.conf <<EOF
preload = $WALLPAPER
wallpaper = DP-6,$WALLPAPER
EOF

pkill hyprpaper
hyprpaper &
