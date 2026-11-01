# GNU ls styles world-writable dirs as blue-on-green (ow/tw = 34;42 / 30;42).
# Everything on the NTFS drive (/mnt/Blender) is 777, so every dir there got
# that unreadable highlight. Render them like normal dirs instead.
if command -sq dircolors
    set -l base (dircolors -b | string match -r "^LS_COLORS='(.*)';" | tail -n 1)
    set -gx LS_COLORS "$base:ow=01;34:tw=01;34:st=01;34"
end
