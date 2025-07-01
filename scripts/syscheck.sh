#!/bin/bash

# Define colors (optional, can remove if not wanted)
GREEN='\e[1;32m'
YELLOW='\e[1;33m'
RED='\e[1;31m'
CYAN='\e[1;36m'
NC='\e[0m'


echo -e "${CYAN}==== YAY PACKAGE HEALTH CHECK ====${NC}"

# -- Broken packages check --
echo -e "\n${GREEN}  Checking for broken packages (missing files)...${NC}"
broken=$(yay -Qk | grep -v '0 missing')
if [[ -z "$broken" ]]; then
    echo -e "${CYAN}  All files present.${NC}"
    broken_count=0
else
    echo "$broken"
    broken_count=$(echo "$broken" | wc -l)
fi

# -- Orphaned packages check --
echo -e "\n${CYAN}<============| Orphaned packages |============>${NC}"
orphans=$(yay -Qdt)
if [[ -z "$orphans" ]]; then
    echo -e "${GREEN} No orphaned packages found.${NC}"
    orphan_count=0
else
    echo "$orphans"
    orphan_count=$(echo "$orphans" | wc -l)
fi

# -- Foreign (AUR) packages check --
echo -e "\n${CYAN}<============|   AUR packages    |============>${NC}"
foreign=$(yay -Qm)
if [[ -z "$foreign" ]]; then
    echo -e "${GREEN}✔ No foreign packages installed.${NC}"
    aur_count=0
else
    echo "$foreign"
    aur_count=$(echo "$foreign" | wc -l)
fi

# -- Total installed packages --
total_packages=$(yay -Qq | wc -l)

# -- Final Summary --
echo -e "\n${CYAN}<============|  CHECK COMPLETE   |============>${NC}"
echo -e "${GREEN}| Total installed packages:     ${total_packages}${NC}"
echo -e "${GREEN}| Total AUR packages:           ${aur_count}${NC}"
echo -e "${GREEN}| Total orphaned packages:      ${orphan_count}${NC}"
echo -e "${GREEN}| Total broken packages:        ${broken_count}${NC}"

day=$(date +%u)
if [[ "$day" == "1" ]]; then
    echo -e "\n Start of the week, please do a system update!\n"
    read -p " Do you want to run yay -Syu now? [Y/n] " answer
    answer=${answer:-y}
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        echo "updating..."
        yay -Syu --devel --timeupdate && yay -Yc --noconfirm
        exit 1

    else
        echo " Alright. Make sure to do it tomorrow then!"
        exit 1
    fi

else

    echo -e "\n"
    read -p "Do you want to run yay -Syu now? [y/N] " answer
    answer=${answer:-n}
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        echo "updating..."
        yay -Syu --devel --timeupdate && yay -Yc --noconfirm

    else
        exit 1
    fi
fi

echo 