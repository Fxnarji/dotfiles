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

# Copyright 2023, Alex Zhornyak

import bpy

from typing import Dict, Callable


def group_to_dict(group: bpy.types.PropertyGroup, fn_skip_prop: Callable = None) -> Dict:
    """Get values from a property group as a dict."""

    prop_dict = {}

    def rna_recursive_attr_expand(value, p_dict, rna_path_step, level):
        if isinstance(value, bpy.types.PropertyGroup):
            for sub_value_attr, sub_value_prop in value.bl_rna.properties.items():
                if sub_value_attr == "rna_type":
                    continue
                if sub_value_prop.is_skip_save:
                    continue
                if fn_skip_prop is not None:
                    if fn_skip_prop(value, sub_value_attr):
                        continue

                sub_value = getattr(value, sub_value_attr)

                rna_recursive_attr_expand(sub_value, p_dict, sub_value_attr, level)
        elif type(value).__name__ == "bpy_prop_collection_idprop":  # could use nicer method
            p_dict[rna_path_step] = []
            for sub_value in value:

                p_dict[rna_path_step].append({})

                rna_recursive_attr_expand(sub_value, p_dict[rna_path_step][-1], '', level + 1)
        else:
            # NOTE: convert thin wrapped sequences
            # to simple lists to repr()
            try:
                value = value[:]
            except Exception:
                pass

            p_dict[rna_path_step] = value

    rna_recursive_attr_expand(group, prop_dict, '', 0)

    return prop_dict


def group_from_dict(group: bpy.types.PropertyGroup, p_dict: Dict, fn_skip_prop: Callable = None) -> None:
    """ Assign dict to group """

    for key, val in p_dict.items():

        if fn_skip_prop is not None:
            if fn_skip_prop(group, key):
                continue

        p_attr = getattr(group, key, None)
        if type(p_attr).__name__ == "bpy_prop_collection_idprop":
            p_attr.clear()
            for sub in val:
                p_attr.add()
                group_from_dict(p_attr[-1], sub)
        else:
            if val != p_attr:
                setattr(group, key, val)
