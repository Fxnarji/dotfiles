#!/bin/bash

# Hardcoded directory
DIR="$HOME/dotfiles/wallpapers"
RELOAD= "$HOME/dotfiles/scripts/refresh-global-themes.sh"

# Make sure directory exists
if [[ ! -d "$DIR" ]]; then
  echo "Directory $DIR not found!"
  exit 1
fi

# Generate input for rofi with icons
input=""
while IFS= read -r -d $'\0' file; do
  # Get basename for display, full path for icon
  name=$(basename "$file")
  input+="$name\0icon\x1f$file\n"
done < <(find "$DIR" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" \) -print0)

# Run rofi in dmenu mode with the input
chosen=$(echo -en "$input" | rofi -dmenu -i -p "Select image:" -config $HOME/dotfiles/.config/rofi/wallpapers/wallpapers_config.rasi)

# Optional: do something with the selection
if [[ -n "$chosen" ]]; then
  "$HOME/dotfiles/scripts/refresh-global-themes.sh" "$DIR/$chosen"
fi
