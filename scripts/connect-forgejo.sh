#!/usr/bin/env bash

set -e

HOST="git.fynnluft.com"
PORT="22" # change to 22 if using default SSH

echo "================ Setting up SSH keys for Forgejo ================"

SSH_DIR="$HOME/.ssh"
KEY_NAME="forgejo"
KEY_PATH="$SSH_DIR/$KEY_NAME"

# Ensure ~/.ssh exists
if [ ! -d "$SSH_DIR" ]; then
  echo "Creating ~/.ssh directory..."
  mkdir -p "$SSH_DIR"
  chmod 700 "$SSH_DIR"
fi

cd "$SSH_DIR"

# Generate key if it doesn't exist
if [ -f "$KEY_PATH" ]; then
  echo "SSH key already exists."
else
  echo "Generating new SSH key..."
  ssh-keygen -t ed25519 -f "$KEY_NAME" -N "" -C "${USER}_office"
fi

echo
echo "Opening Forgejo SSH key settings..."
xdg-open "http://$HOST:3000/user/settings/keys" >/dev/null 2>&1 || true

echo
echo "Your public key:"
echo "--------------------------------------------------"
cat "$KEY_PATH.pub"
echo "--------------------------------------------------"
echo

echo "Copy the above key into Forgejo and press Enter when done."
read

# Start ssh-agent if not running
if ! pgrep -u "$USER" ssh-agent >/dev/null; then
  echo "Starting ssh-agent..."
  eval "$(ssh-agent -s)"
fi

# Add key
ssh-add "$KEY_PATH"

echo
echo "Testing SSH connection..."
echo

ssh -T -p "$PORT" git@"$HOST" || {
  echo "SSH connection failed."
  exit 1
}

echo
echo "Setup complete."
