#!/bin/bash
set -e

# Install dependencies for building AUR packages
sudo pacman -S --needed --noconfirm base-devel git

# Clone yay repo, build and install
cd /tmp
if [ -d yay ]; then
  rm -rf yay
fi
git clone https://aur.archlinux.org/yay.git
cd yay
makepkg -si --noconfirm

# Clean up
cd ..
rm -rf yay

echo "yay installed"
