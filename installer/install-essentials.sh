#!/bin/bash
essentials=(
rofi
waybar
stow
gum
)

sudo pacman -S --needed "${essentials[@]}"
