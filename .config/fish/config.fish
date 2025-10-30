if status is-interactive
    fastfetch
end

starship init fish | source

function sudo_last
    eval sudo $history[1]
end

function toggle_dns_pi
    sudo resolvectl dns enp6s0 192.168.178.138
    notify-send "switching dns to 192.168.178.138"
    sudo systemd-resolve --flush-caches

end

function toggle_dns_google
    sudo resolvectl dns enp6s0 8.8.4.4
    notify-send "switching dns to 8.8.4.4"
    sudo resolvectl flush-caches

end

function fishconf
    nvim /home/fxnarji/dotfiles/.config/fish/config.fish
end

function hyprconf
    nvim "$HOME/dotfiles/.config/hypr/hyprland.conf"
end

function b
    headsetcontrol -b | grep Level
end

function wallpaper
    ~/dotfiles/scripts/wallpaper-picker.sh
end

function inv
    code $(fzf -m --preview="bat --color=always {}")
end

function off
    echo turn pc off?
    sudo shutdown now
end

alias google toggle_dns_google
alias hole toggle_dns_pi
alias sudo!! sudo_last
alias invoice $HOME/Github/pdf-generator/gumscript.sh
alias update $HOME/scripts/syscheck.sh
alias summary $HOME/Github/summary-generator/summary-generator.sh
