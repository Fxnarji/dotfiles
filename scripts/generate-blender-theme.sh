#!/bin/bash

# Hardcoded paths
template_file="$HOME/dotfiles/scripts/blender/blender_template.xml"
output_file="$HOME/dotfiles/.config/blender/4.4/scripts/presets/interface_theme/Blender_pywal.xml"
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

echo "Blender theme generated: $output_file"
