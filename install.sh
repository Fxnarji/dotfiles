#!/bin/bash
scripts=(
"install-essentials.sh"
"install-yay.sh"
"install-yay-packages.sh"
"stow-dotfiles.sh"
)

for script in "${scripts[@]}"; do
 ./scripts/installer/"$script"
done

