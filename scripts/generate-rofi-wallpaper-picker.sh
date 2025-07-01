#!/bin/bash

# Hardcoded paths
template_file="$HOME/dotfiles/.config/rofi/wallpapers/wallpapers_template.rasi"
output_file="$HOME/.config/rofi/wallpapers/wallpapers_config.rasi"
color_file="$HOME/.cache/wal/colors"

# Check template existence
if [ ! -f "$template_file" ]; then
  echo "Template file not found: $template_file"
  exit 1
fi

# Copy fresh template to output file
cp "$template_file" "$output_file"

# Read colors into an array
mapfile -t colors < "$color_file"

# Replace placeholders COLOR0, COLOR1 ... in output file
for i in "${!colors[@]}"; do
  sed -i "s/COLOR$i/${colors[$i]}/g" "$output_file"
done

echo "Rofi theme generated: $output_file"
