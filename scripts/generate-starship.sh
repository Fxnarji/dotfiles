#!/bin/bash
# Generate starship.toml using wal colors

WAL_COLORS="$HOME/.cache/wal/colors-rio.toml"
TEMPLATE="$HOME/.config/starship/template.toml"
OUTPUT="$HOME/.config/starship.toml"
FORMAT_TEMPLATE="$HOME/.config/starship/template_format.toml"

cat "$FORMAT_TEMPLATE" \
    <(
        sed 's/^\[colors\]/[palettes.color]/' "$WAL_COLORS" |
        sed -E 's/(#[0-9a-fA-F]{6})[0-9a-fA-F]{2}/\1/g'
    ) \
    "$TEMPLATE" \
    > "$OUTPUT"
