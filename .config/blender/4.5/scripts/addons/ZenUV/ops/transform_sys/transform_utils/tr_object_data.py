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

# Copyright 2023, Valeriy Yatsenko, Alex Zhornyak

import bpy
import bmesh

from dataclasses import dataclass, field

from ZenUV.utils.generic import get_mesh_data, verify_uv_layer
from ZenUV.utils import get_uv_islands as island_util


@dataclass
class TrObjectInfo:
    bm: bmesh.types.BMesh = None
    me: bpy.types.Mesh = None
    loops: list = field(default_factory=list)
    uv_layer: bmesh.types.BMLayerItem = None
    loops_data: list = field(default_factory=dict)


class TrObjectData:

    def __init__(self) -> None:
        self.object_storage = {}  # type: dict[bpy.types.Object, TrObjectInfo]
        self.influence_mode = ''
        self.order = ''
        self.message = ''

    def is_valid(self, objs, influence_mode, order):
        res = (
            self.influence_mode == influence_mode and
            self.order == order and
            set(self.object_storage.keys()).issubset(objs)
            )
        if res:
            try:
                # this operation will check that loops are still actual
                for _, v in self.object_storage.items():
                    for lp_cluster in v.loops:
                        if lp_cluster:
                            _ = lp_cluster[0][v.uv_layer]
                            break
            except Exception:
                return False
        return res

    def setup(
        self,
        context: bpy.types.Context,
        objs: list,
        influence_mode: str,
        order: str,
    ) -> int:
        self.object_storage.clear()

        self.influence_mode = influence_mode
        self.order = order

        i_total_loops_count = 0

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            if influence_mode == 'ISLAND':
                loops = island_util.LoopsFactory.loops_by_islands(context, bm, uv_layer)
                for lp_cluster in loops:
                    if len(lp_cluster) == 0:
                        print('EMPTY')
            else:
                loops = island_util.LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=True)

            if order == 'OVERALL':
                if len(loops) > 0:
                    loops = [[lp for group in loops for lp in group], ]

            n_loops_count = len(loops)
            if n_loops_count:
                self.object_storage[obj] = TrObjectInfo(
                    bm=bm, me=me, loops=loops, uv_layer=uv_layer)

            i_total_loops_count += n_loops_count

        return i_total_loops_count


# Global Object Data Storage
transform_object_data = TrObjectData()
