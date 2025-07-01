#!/bin/bash

# Set working directory to your dotfiles folder (or wherever scripts expect to run)
cd "$HOME/dotfiles/scripts" || exit 1
./wallpaper-picker.sh "$@"
