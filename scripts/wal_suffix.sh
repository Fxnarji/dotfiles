#-----------------------------------------HYPRPAPER
#!/bin/bash
# Path from wal

wal -i "$1" || exit 1

WALLPAPER=$(<~/.cache/wal/wal)

# Write hyprpaper config
cat > ~/.config/hypr/hyprpaper.conf <<EOF
preload = $WALLPAPER
wallpaper = DP-6,$WALLPAPER
EOF

# Kill existing hyprpaper and restart it
pkill hyprpaper
hyprpaper &




##-----------------------------------------WAYBAR
#!/bin/bash
pkill waybar
waybar &


#!/bin/bash


##-----------------------------------------STARSHIP
# Paths
WAL_COLORS="$HOME/.cache/wal/colors-rio.toml"    # or whatever your wal-colored file is
TEMPLATE="$HOME/.config/starship/template.toml"
OUTPUT="$HOME/.config/starship.toml"
FORMAT_TEMPLATE="$HOME/.config/starship/template_format.toml"

# Splice them together:
# 1. format block
# 2. [palettes.color] (renamed from [colors]), with alpha stripped
# 3. rest of config

cat "$FORMAT_TEMPLATE" \
    <(
        # Rename [colors] -> [palettes.color]
        # Strip alpha from any hex color (e.g., #abcdef88 -> #abcdef)
        sed 's/^\[colors\]/[palettes.color]/' "$WAL_COLORS" |
        sed -E 's/(#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1/g'
    ) \
    "$TEMPLATE" \
    > "$OUTPUT"
