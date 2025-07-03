#!/bin/bash

#official pkgs:

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
    rofi
    slurp
    stow
    python-pip
    python-pywal16
    python-pywalfox
    thunar
    ttf-fira-code
    ttf-firacode-nerd
    ttf-mononoki-nerd
    waybar
    visual-studio-code-bin
    wl-clipboard
    blender
    imagemagick
)

echo "installing yay"
sudo pacman -S yay

echo "installing packages"
yay -S --needed "${packages[@]}"

echo "stowing dotfiles"
DOTFILES_DIR="$(dirname "$(realpath "$0")")"

# Change to the dotfiles directory
cd "$DOTFILES_DIR" || exit 1

# Run stow for the current directory (dotfiles)
stow .