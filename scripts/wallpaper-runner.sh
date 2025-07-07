#!/bin/bash
set -euo pipefail

# Change to scripts directory for relative calls
cd "$HOME/dotfiles/scripts" || exit 1

WALL="${1:-}"

if [[ -z "$WALL" ]]; then
  echo "Usage: $0 /path/to/wallpaper"
  exit 1
fi

if [[ ! -f "$WALL" ]]; then
  echo "Invalid wallpaper path: $WALL"
  exit 1
fi

echo "Running wallpaper runner for: $WALL"

# Array of scripts to run in order
scripts=(
  "wallpaper.sh"
  "generate-starship.sh"
  "restart-waybar.sh"
  "generate-rofi-launcher.sh"
  "generate-rofi-wallpaper-picker.sh"
  "generate-blender-theme.sh"
  "set-blender-splash.sh"
)

for script in "${scripts[@]}"; do
  if [[ ! -x "$script" ]]; then
    echo "Error: Script '$script' not found or not executable."
    exit 1
  fi

  echo "Executing $script"
  ./"$script" "$WALL" || {
    echo "Error running $script"
    exit 1
  }
done

echo "All scripts executed successfully."
