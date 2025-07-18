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

import bpy
import bmesh
from ZenUV.utils.generic import (
    resort_by_type_mesh_in_edit_mode_and_sel,
    resort_objects_by_selection,
    get_mesh_data,
    verify_uv_layer
)
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.base_clusters.base_cluster import (
    OrientCluster
)
from ZenUV.utils.base_clusters.zen_cluster import ZenCluster
from bpy.props import BoolProperty, EnumProperty
from ZenUV.ui.labels import ZuvLabels
from ZenUV.ops.transform_sys.transform_utils.tr_utils import TransformSysOpsProps


class oCluster(ZenCluster, OrientCluster):
    def __init__(self, context, obj, island, bm=None, index=-1) -> None:
        super().__init__(context, obj, island, bm, index=index)
        # ZenCluster.__init__(self)
        OrientCluster.__init__(self)


class ZUV_OT_WorldOrient(bpy.types.Operator):
    bl_idname = "uv.zenuv_world_orient"
    bl_label = ZuvLabels.OT_WORLD_ORIENT_LABEL
    bl_description = ZuvLabels.OT_WORLD_ORIENT_DESC
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(
        name=ZuvLabels.PROP_WO_METHOD_LABEL,
        description=ZuvLabels.PROP_WO_METHOD_DESC,
        items=[
            ("HARD", "Hard Surface", ""),
            ("ORGANIC", "Organic", "")
        ],
        default="HARD"
    )
    rev_x: BoolProperty(name="X", default=False, description="Reverse Axis X")
    rev_y: BoolProperty(name="Y", default=False, description="Reverse Axis Y")
    rev_z: BoolProperty(name="Z", default=False, description="Reverse Axis Z")
    rev_neg_x: BoolProperty(name="-X", default=False, description="Reverse Axis -X")
    rev_neg_y: BoolProperty(name="-Y", default=False, description="Reverse Axis -Y")
    rev_neg_z: BoolProperty(name="-Z", default=False, description="Reverse Axis -Z")

    further_orient: BoolProperty(
        name=ZuvLabels.PROP_WO_FURTHER_LABEL,
        default=True,
        description=ZuvLabels.PROP_WO_FURTHER_DESC
        )
    flip_by_axis: BoolProperty(
        name="Flip By Axis",
        default=False,
        description="Allow flip islands by axis"
        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "method")
        layout.prop(self, "further_orient")
        layout.prop(self, "flip_by_axis")
        if self.flip_by_axis:
            layout.label(text="Reverse Axis:")
            box = layout.box()
            row = box.row(align=True)
            row.prop(self, "rev_x")
            row.prop(self, "rev_y")
            row.prop(self, "rev_z")
            row = box.row(align=True)
            row.prop(self, "rev_neg_x")
            row.prop(self, "rev_neg_y")
            row.prop(self, "rev_neg_z")

    poll = TransformSysOpsProps.poll_edit_mesh_and_active_object

    poll_reason = TransformSysOpsProps.poll_reason_edit_mesh_and_active_object

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        objs = resort_objects_by_selection(context, objs)
        # print(f"\n{'-' * 50}\nObjs in WO Operator:", objs)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        for obj in objs:
            # print("\nProcessed Object --->  ", obj.name)
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            islands = island_util.get_island(context, bm, uv_layer)
            # clusters = []
            # print("Islands count: ", len(islands))
            for ids, island in enumerate(islands):
                # print(f"Island No {ids} processing")
                cluster = oCluster(context, obj, island, bm, index=ids)
                if cluster.analyser.is_warning:
                    CA = cluster.analyser
                    print(f'\n{CA.message_type}, {CA.message}\n\t{CA.data}')
                    continue
                cluster.f_orient = self.further_orient
                cluster.set_direction(
                    {
                        "x": self.rev_x,
                        "-x": self.rev_neg_x,
                        "y": self.rev_y,
                        "-y": self.rev_neg_y,
                        "z": self.rev_z,
                        "-z": self.rev_neg_z,
                    }
                )
                cluster.type = self.method
                cluster.do_orient_to_world()

            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {'FINISHED'}


w_orient_classes = (
    ZUV_OT_WorldOrient,
)
