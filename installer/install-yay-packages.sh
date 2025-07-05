#!/bin/bash
set -e

# Define packages
packages=(
    bat
    btop
    discord
    fastfetch
    firefox
    fish
    gitkraken
    grim
    kitty
    hyprpaper
    hyprshell
    slurp
    python-pip
    python-pywal16
    python-pywalfox
    thunar
    ttf-fira-code
    ttf-firacode-nerd
    ttf-mononoki-nerd
    visual-studio-code-bin
    wl-clipboard
    blender
    imagemagick
    fzf
    yazi
)


rows=$(tput lines)
((rows -= 5))
# Use gum to select packages
selected=$(printf "%s\n" "${packages[@]}" | gum choose --no-limit \
 --cursor="> " \
  --cursor-prefix="[ ]"\
  --unselected-prefix="[ ]" \
  --selected-prefix="[*]" \
  --selected=* \
  --height=$rows\
  --header="Deselect packages you want to skip:" \


)

# If no selection, exit
if [[ -z "$selected" ]]; then
  echo "No packages selected. Exiting."
  exit 1
fi

# Convert newline-separated list into array
IFS=$'\n' read -r -d '' -a selected_packages < <(printf '%s\0' "$selected")

# Install selected packages
echo "Installing selected packages..."
yay -S --needed "${selected_packages[@]}"

