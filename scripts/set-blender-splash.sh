#!/bin/bash

WALLPAPER=$(<~/.cache/wal/wal)
THEME_NAME="Fxnarji"
SPLASH="$HOME/dotfiles/.config/blender/4.4/scripts/startup/bl_app_templates_user/$THEME_NAME/splash.png"

if [[ -f "$WALLPAPER" ]]; then
  height=$(identify -format '%h' "$WALLPAPER")
  width=$(( 2 * height ))
  magick "$WALLPAPER" -gravity center -crop "${width}x${height}+0+0" +repage "$SPLASH"
fi
