#!/bin/bash

set -euo pipefail

cd "$HOME/dotfiles/scripts" || exit 1

DIR="$HOME/dotfiles/wallpapers"
PREVIEW_DIR="$DIR/.preview"
LAUNCHER="$HOME/dotfiles/scripts/wallpaper-runner.sh"

# Check required commands
for cmd in identify convert rofi; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "Error: $cmd is not installed or not in PATH."
    exit 1
  fi
done

if [[ ! -d "$DIR" ]]; then
  echo "Directory $DIR not found!"
  exit 1
fi

if [[ ! -x "$LAUNCHER" ]]; then
  echo "Launcher script $LAUNCHER not found or not executable."
  exit 1
fi

mkdir -p "$PREVIEW_DIR"

input=""
while IFS= read -r -d '' file; do
  name=$(basename "$file")
  preview_icon="$PREVIEW_DIR/$name"

  if [[ ! -f "$preview_icon" ]]; then
    height=$(identify -format '%h' "$file")
    convert "$file" -gravity center -crop "${height}x${height}+0+0" +repage "$preview_icon"
  fi

  input+="$name\0icon\x1f$preview_icon\n"
done < <(find "$DIR" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" \) -print0)

chosen=$(printf '%b' "$input" | rofi -dmenu -i -p "Select image:" -config "$HOME/dotfiles/.config/rofi/wallpapers/wallpapers_config.rasi")

if [[ -n "$chosen" ]]; then
  # Pass the full path to the launcher script
  "$LAUNCHER" "$DIR/$chosen"
fi
