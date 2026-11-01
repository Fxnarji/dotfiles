#!/bin/sh
# Steps 1-2 of the greetd setup. Does NOT enable greetd or change the boot target.
# Run with: sudo sh scripts/setup-greetd.sh
set -e

stamp=$(date +%Y%m%d-%H%M%S)

# 1. Remove tty1 autologin (backup kept in /root)
if [ -d /etc/systemd/system/getty@tty1.service.d ]; then
    cp -a /etc/systemd/system/getty@tty1.service.d "/root/getty@tty1.service.d.bak-$stamp"
    rm -r /etc/systemd/system/getty@tty1.service.d
    echo "removed tty1 autologin (backup: /root/getty@tty1.service.d.bak-$stamp)"
fi
systemctl daemon-reload

# 2. greetd on VT7 with tuigreet launching Hyprland via uwsm
cp -a /etc/greetd/config.toml "/etc/greetd/config.toml.bak-$stamp"
cat > /etc/greetd/config.toml <<'EOF'
[terminal]
vt = 7

[default_session]
command = "tuigreet --time --remember --asterisks --cmd 'uwsm start -e -D Hyprland hyprland.desktop'"
user = "_greetd"
EOF
echo "wrote /etc/greetd/config.toml (backup: /etc/greetd/config.toml.bak-$stamp)"

systemctl is-enabled greetd || true
