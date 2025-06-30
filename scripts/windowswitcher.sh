 #!/bin/bash
XDG_CONFIG_HOME=/dotfiles/.config/rofi/ rofi -dmenu

# Get list of windows with wmctrl
WINDOWS=$(wmctrl -lx | awk -F' ' '{$3=""; $4=""; print substr($0, index($0,$5))}')

# Show with rofi in dmenu mode
SELECTED=$(echo "$WINDOWS" | rofi -dmenu -i -p "Window:")

# If a window was selected
if [ -n "$SELECTED" ]; then
    # Get the window ID by matching the selected window title
    ID=$(wmctrl -lx | grep "$SELECTED" | awk '{print $1}' | head -n 1)
    # Focus the window
    wmctrl -ia "$ID"
fi

