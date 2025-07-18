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
from math import pi, radians
from mathutils import Vector

from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.generic import verify_uv_layer, resort_by_type_mesh_in_edit_mode_and_sel, select_by_context
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.ui.pie import ZsPieFactory
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops


class ZUV_OP_TestOperator(bpy.types.Operator):
    bl_idname = 'zenuv_test.test_operator'
    bl_label = 'Test Operator'
    bl_description = 'Select Holed Islands'
    bl_zen_short_name = 'Holed Islands'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)

        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {"CANCELLED"}

        from ZenUV.utils.base_clusters.zen_cluster import ZenCluster
        from ZenUV.utils.base_clusters.stripes import UvStripes
        from ZenUV.utils.generic import bpy_deselect_by_context, switch_to_face_sel_mode

        if self.clear_selection:
            bpy_deselect_by_context(context)

        switch_to_face_sel_mode(context)

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            islands = island_util.get_islands(context, bm)

            for island in islands:
                cl = ZenCluster(context, obj, island, bm)
                p_uv_bound_edges = cl.get_bound_edges()
                z_stripes = UvStripes(p_uv_bound_edges, uv_layer)

                if z_stripes.is_cluster_holed():
                    select_by_context(context, bm, [island, ])

            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OP_SpeedTestOperator(bpy.types.Operator):
    bl_idname = 'zenuv_test.speed_test_operator'
    bl_label = 'Speed Test Operator'
    bl_description = 'Compares the speed of two functions.'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):

        import time

        def get_uv_bound_edges_indexes_original(faces, uv_layer):
            """ Return indexes of border edges of given island (faces) from current UV Layer """
            if not faces:
                return []

            edges = {edge for face in faces for edge in face.edges if edge.link_loops}
            return [edge.index for edge in edges
                    if edge.link_loops[0][uv_layer].uv
                    != edge.link_loops[0].link_loop_radial_next.link_loop_next[uv_layer].uv
                    or edge.link_loops[-1][uv_layer].uv
                    != edge.link_loops[-1].link_loop_radial_next.link_loop_next[uv_layer].uv]

        # Optimized function using bmesh
        def get_uv_bound_edges_indexes_optimized(faces, uv_layer):
            """ Return indexes of border edges of given island (faces) from current UV Layer """

            if not faces:
                return []

            edges = {edge for face in faces for edge in face.edges if edge.link_loops}
            uv_diff_edges = []

            for edge in edges:
                loop1, loop2 = edge.link_loops[0], edge.link_loops[-1]
                uv1_1, uv1_2 = loop1[uv_layer].uv, loop1.link_loop_radial_next.link_loop_next[uv_layer].uv
                uv2_1, uv2_2 = loop2[uv_layer].uv, loop2.link_loop_radial_next.link_loop_next[uv_layer].uv
                if uv1_1 != uv1_2 or uv2_1 != uv2_2:
                    uv_diff_edges.append(edge.index)

            return uv_diff_edges

        # Setup test data using bmesh
        def get_test_data(obj):
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            return bm, uv_layer

        obj = bpy.context.active_object
        bm, uv_layer = get_test_data(obj)
        # p_faces = bm.faces[200: 9000]
        p_faces = [f for f in bm.faces if f.select]
        print(f'{len(p_faces) = }')

        bpy.ops.mesh.select_all(action='DESELECT')
        bpy.ops.mesh.select_mode(type="EDGE")
        # Timing the original function
        start_time = time.time()
        original_result = get_uv_bound_edges_indexes_original(p_faces, uv_layer)
        original_time = time.time() - start_time

        # Timing the optimized function
        start_time = time.time()
        optimized_result = get_uv_bound_edges_indexes_optimized(p_faces, uv_layer)
        optimized_time = time.time() - start_time

        # Results
        print(f"Original function time: {original_time:.6f} seconds")
        print(f"Optimized function time: {optimized_time:.6f} seconds")

        # Verifying both functions return the same result
        assert original_result == optimized_result, "Results differ between original and optimized functions!"
        print("Both functions return the same result.")
        print(f'{len(optimized_result) = }')
        print(f'{len(original_result) = }')

        for i in optimized_result:
            bm.edges[i].select = True
        start_time = time.time()
        bmesh.update_edit_mesh(obj.data)
        update_time = time.time() - start_time
        print(f"Bmesh --> Mesh update time: {update_time:.6f} seconds")

        return {'FINISHED'}


def register_test_operator():
    bpy.utils.register_class(ZUV_OP_TestOperator)


def unregister_test_operator():
    bpy.utils.unregister_class(ZUV_OP_TestOperator)
