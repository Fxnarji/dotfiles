    if status is-interactive
    fastfetch
end

starship init fish | source

function sudo_last
    eval sudo $history[1]
end




function toggle_dns_pi
    sudo resolvectl dns enp6s0 192.168.178.192
    notify-send "switching dns to 192.168.178.192"
    sudo systemd-resolve --flush-caches


end

function toggle_dns_google
    sudo resolvectl dns enp6s0 8.8.4.4
    notify-send "switching dns to 8.8.4.4"
    sudo systemd-resolve --flush-caches

end

function fish_config
    code /home/fxnarji/dotfiles/.config/fish/config.fish
end


function hyprconf 
    code "$HOME/dotfiles/.config/hypr/hyprland.conf"
end





function wallpaper
    ~/dotfiles/scripts/wallpaper-picker.sh
end

alias google toggle_dns_google
alias hole toggle_dns_pi
alias sudo!! sudo_last