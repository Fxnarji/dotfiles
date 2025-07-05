
echo "stowing dotfiles"
DOTFILES_DIR="$(dirname "$(realpath "$0")")"

# Change to the dotfiles directory
cd "$DOTFILES_DIR" || exit 1

# Run stow for the current directory (dotfiles)
stow .


rows=$(tput lines)
