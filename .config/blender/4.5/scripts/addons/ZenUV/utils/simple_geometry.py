# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# Copyright 2022, Alex Zhornyak

import blf

from dataclasses import dataclass


@dataclass
class Rectangle:
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    auto_normalize: bool = True

    @property
    def width(self):
        return self.right - self.left

    @width.setter
    def width(self, val):
        self.right = self.left + val

    @property
    def height(self):
        return self.top - self.bottom

    @height.setter
    def height(self, val):
        self.top = self.bottom + val

    def __post_init__(self):
        if self.auto_normalize:
            self.normalize()

    def normalize(self):
        p_left = min(self.left, self.right)
        p_right = max(self.left, self.right)
        p_bottom = min(self.top, self.bottom)
        p_top = max(self.top, self.bottom)

        self.left = p_left
        self.top = p_top
        self.right = p_right
        self.bottom = p_bottom

    def center(self):
        return (self.left + self.width / 2, self.bottom + self.height / 2)

    def intersects(self, other):
        if self.left > other.right or self.right < other.left:
            return False

        if self.top < other.bottom or self.bottom > other.top:
            return False

        return True

    def __hash__(self):
        return hash((self.left, self.top, self.right, self.bottom))


@dataclass
class TextRect(Rectangle):
    name: str = ''
    color: tuple = (0, 0, 0, 0)

    def __hash__(self):
        return hash((super().__hash__(), self.name, self.color))

    def draw_text(self):
        blf.position(0, self.left, self.bottom, 0)

        blf.color(0, *self.color)

        blf.enable(0, blf.SHADOW)
        blf.shadow(0, 3, 0.0, 0.0, 0.0, 1.0)
        blf.shadow_offset(0, 1, -1)

        blf.draw(0, self.name)

        blf.disable(0, blf.SHADOW)
