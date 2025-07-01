#!/bin/bash
WALL="$1"

if [ ! -f "$WALL" ]; then
  echo "Invalid wallpaper path."
  exit 1
fi

echo "FILE RAN"

"$HOME/dotfiles/scripts/wallpaper.sh" "$WALL"
"$HOME/dotfiles/scripts/generate-starship.sh"
"$HOME/dotfiles/scripts/restart-waybar.sh"
"$HOME/dotfiles/scripts/generate-rofi-launcher.sh"
"$HOME/dotfiles/scripts/generate-rofi-wallpaper-picker.sh"
