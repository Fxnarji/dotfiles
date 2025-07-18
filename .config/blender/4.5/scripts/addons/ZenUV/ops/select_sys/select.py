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

# Copyright 2023, Valeriy Yatsenko

import bpy
import bmesh
from itertools import chain
from math import radians
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from ZenUV.ui.labels import ZuvLabels

from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.get_uv_islands import get_uv_bound_edges_indexes
from ZenUV.utils.base_clusters.zen_cluster import ZenCluster
from ZenUV.utils.constants import u_axis, v_axis

from ZenUV.utils.generic import (
    get_mesh_data,
    resort_objects_by_selection,
    resort_by_type_mesh_in_edit_mode_and_sel,
    select_by_context,
    is_pure_edge_mode,
    verify_uv_layer
)
from ZenUV.ops.adv_uv_maps_sys.udim_utils import UdimFactory
from ZenUV.utils.get_uv_islands import FacesFactory
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.ops.texel_density.td_utils import UvFaceArea
from ZenUV.utils.constants import FACE_UV_AREA_MULT
from ZenUV.utils.mark_utils import get_splits_edges_indices, get_open_edges_indices
from ZenUV.utils.bounding_box import BoundingBox2d, uv_area_bbox


class SelectUtils:

    @classmethod
    def select_uv_border(
            cls,
            context: bpy.types.Context,
            bm: bmesh.types.BMesh,
            uv_layer: bmesh.types.BMLayerItem,
            mode: str = 'ALL_ISLANDS',
            is_clear_selection: bool = False) -> bool:

        ''' Assume that we are working only in edge selection mode '''

        if uv_layer is None:
            return False

        from ZenUV.utils.get_uv_islands import get_uv_bound_edges_indexes, get_island
        from ZenUV.utils.generic import is_pure_edge_mode

        bm.edges.ensure_lookup_table()

        if mode == 'FACES':
            area = context.area.type
            if area == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                p_loops = cls.select_faces_borders_as_loops(bm, facelist=[f for f in bm.faces if False not in [lp[uv_layer].select for lp in f.loops]], uv_layer=uv_layer)
                for loop in {lp for v in bm.verts for lp in v.link_loops if lp not in p_loops}:
                    loop[uv_layer].select = False
                    loop[uv_layer].select_edge = False
                return
            else:
                if bpy.ops.mesh.region_to_loop.poll():
                    bpy.ops.mesh.region_to_loop()
                return

        is_selected_islands_only = mode == 'ISLAND'

        if is_pure_edge_mode(context):

            if is_selected_islands_only:
                p_islands = get_island(context, bm, uv_layer)
                if is_clear_selection:
                    cls.clear_selection(context, p_islands, uv_layer)
                bound_edges_idxs = get_uv_bound_edges_indexes([f for i in p_islands for f in i], uv_layer)
                p_loop_idxs = {lp.index for i in p_islands for f in i for lp in f.loops}
                p_loops = [loop for i in bound_edges_idxs for loop in bm.edges[i].link_loops if loop.index in p_loop_idxs]
                cls.select_uv_edges(uv_layer, p_loops)
            else:
                bound_edges_idxs = get_uv_bound_edges_indexes([f for f in bm.faces if not f.hide], uv_layer)
                p_loops = [loop for i in bound_edges_idxs for vert in bm.edges[i].verts for loop in vert.link_loops]
                for loop in p_loops:
                    loop[uv_layer].select = True
                    for loop in [loop for i in bound_edges_idxs for loop in bm.edges[i].link_loops]:
                        loop[uv_layer].select_edge = True

        else:
            if is_selected_islands_only:
                p_islands = get_island(context, bm, uv_layer)
                if is_clear_selection:
                    cls.clear_selection(context, p_islands, uv_layer)
                bound_edges_idxs = get_uv_bound_edges_indexes([f for i in p_islands for f in i], uv_layer)
            else:
                bound_edges_idxs = get_uv_bound_edges_indexes([f for f in bm.faces if not f.hide], uv_layer)

            for i in bound_edges_idxs:
                bm.edges[i].select = True

        return True

    @classmethod
    def select_uv_edges(cls, uv_layer, p_loops):
        from collections import defaultdict

        for loop in p_loops:
            loop[uv_layer].select = True
            loop.link_loop_next[uv_layer].select = True
            loop[uv_layer].select_edge = True

            scope = defaultdict(list)
            for lp in loop.vert.link_loops:
                scope[lp[uv_layer].uv.to_tuple()].append(lp)

            for lp in scope[loop[uv_layer].uv.to_tuple()]:
                lp[uv_layer].select = True

    @classmethod
    def select_faces_borders_as_loops(cls, bm, facelist, uv_layer) -> list:
        from ZenUV.utils.get_uv_islands import get_bound_edges_idxs_from_facelist
        p_edge_idxs = get_bound_edges_idxs_from_facelist(facelist)
        p_loops = [loop for i in p_edge_idxs for loop in bm.edges[i].link_loops if loop[uv_layer].select]
        cls.select_uv_edges(uv_layer, p_loops)
        return p_loops

    @classmethod
    def clear_selection(cls, context, p_islands, uv_layer):
        area = context.area.type
        if area == 'IMAGE_EDITOR' and context.scene.tool_settings.use_uv_select_sync is False:
            if ZenPolls.version_since_3_2_0:
                for loop in {lp for i in p_islands for f in i for lp in f.loops}:
                    loop[uv_layer].select = False
                    loop[uv_layer].select_edge = False
            else:
                for loop in {lp for i in p_islands for f in i for lp in f.loops}:
                    loop[uv_layer].select = False

        else:
            for i in p_islands:
                for f in i:
                    f.select = False


class ZUV_OT_SelectInTile(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_in_tile"
    bl_label = 'Select In Tile'
    bl_zen_short_name = 'In Tile'
    bl_description = 'Selects islands depending on their location bounding box relative to the UV Area or UDIM tile'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    base: EnumProperty(
        name='Base',
        description='What to select relative to',
        items=[
            ('UV_AREA', 'UV Area', 'UV Area square'),
            ('UDIM_NUM', 'UDIM tile number', 'UDIM tile number'),
            ('ACTIVE_UDIM', 'Active UDIM', 'Active UDIM tile'),
            ('ANY_UDIM', 'Any UDIM', 'Any UDIM tile')
        ],
        default='UV_AREA')

    location: EnumProperty(
        name='Location',
        description="Location of the island",
        items=[
            ('INSIDE', 'Inside', 'Inside of UV Area'),
            ('OUTSIDE', 'Outside', 'Outside of UV Area'),
            ('CROSS', 'Cross', 'Crossing of UV Area borders'),
            ('MARGIN', 'Check Margin', 'Select islands where the margin between islands within the defined area and the area itself are less than the specified value'),
        ],
        default='INSIDE'
    )
    tile_number: bpy.props.IntProperty(
        name='Tile Number',
        description='Number of UDIM tile',
        default=1001,
        min=UdimFactory.min_udim_number,
        max=UdimFactory.max_udim_number)

    margin: FloatProperty(
        name='Margin',
        description='Minimum margin between the island and the defined area',
        min=0.0,
        default=0.005,
        precision=3
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.prop(self, 'clear_selection')
        layout.prop(self, 'base')
        layout.prop(self, 'location')
        box = layout.box()
        box.enabled = self.base == 'UDIM_NUM'
        box.prop(self, 'tile_number')
        box = layout.box()
        box.enabled = self.location == 'MARGIN'
        box.prop(self, 'margin')

    def execute(self, context):
        from ZenUV.utils.generic import select_by_context
        UdimFactory.reset_report()

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        if self.base == 'UV_AREA':
            p_bboxes = [uv_area_bbox(), ]
        elif self.base == 'UDIM_NUM':
            if UdimFactory.is_udim_number_valid(self.tile_number) is False:
                self.report({'WARNING'}, '"Tile Number" value is not valid UDIM number')
                return {'CANCELLED'}
            p_bboxes = [UdimFactory.get_bbox_of_udim(self.tile_number), ]
        elif self.base == 'ACTIVE_UDIM':
            p_tile = UdimFactory.get_active_udim_tile(context)
            if p_tile is not None:
                p_bboxes = [UdimFactory.get_bbox_of_udim(p_tile.number), ]
        elif self.base == 'ANY_UDIM':
            p_udims = UdimFactory.get_udims_from_loops(objs)
            p_bboxes = [UdimFactory.get_bbox_of_udim(tile) for tile in p_udims]
        else:
            raise RuntimeError('base value not in {"UV_AREA", "UDIM_NUM", "ACTIVE_UDIM", "ANY_UDIM"}')

        if UdimFactory.result is False:
            self.report({'WARNING'}, UdimFactory.message)
            return {'CANCELLED'}

        m_bbox: BoundingBox2d = None

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            if not uv_layer:
                continue

            for island in island_util.get_islands(context, bm):
                p_bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)

                for m_bbox in p_bboxes:

                    b_is_overlapped = p_bbox.overlapped_with_bbox(m_bbox)
                    b_is_inside = p_bbox.inside_of_bbox(m_bbox)

                    if b_is_overlapped:
                        if self.location == 'INSIDE' and b_is_inside:
                            select_by_context(context, bm, [island, ], state=True)
                        elif self.location == 'CROSS' and not b_is_inside:
                            select_by_context(context, bm, [island, ], state=True)
                        elif self.location == 'MARGIN' and b_is_inside:
                            p_min_value = min([abs(m_bbox.rect[i] - p_bbox.rect[i]) for i in range(4)])
                            if p_min_value < self.margin:
                                select_by_context(context, bm, [island, ], state=True)
                    else:
                        if self.location == 'OUTSIDE' and b_is_inside is False:
                            select_by_context(context, bm, [island, ], state=True)

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}


class ZUV_OT_SelectEdgesByDirection(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_edges_by_direction"
    bl_label = 'Select Edges By Direction'
    bl_zen_short_name = 'Edges by Direction'
    bl_description = 'Select edges by direction'
    bl_options = {'REGISTER', 'UNDO'}

    direction: EnumProperty(
        name="Direction",
        description="Edge direction",
        items=[
            ("U", "U", "U Axis"),
            ("V", "V", "V Axis"),
        ],
        default="U"
    )
    clear_sel: BoolProperty(
        name="Clear",
        description="Clear previous selection",
        default=True
    )
    angle: FloatProperty(
        name="Angle",
        min=0,
        max=45,
        default=30,
    )

    desc: bpy.props.StringProperty(name="Description", default='Select edges by direction', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    @classmethod
    def description(cls, context, properties):
        if properties:
            return properties.desc
        else:
            return cls.bl_description

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "direction")
        layout.prop(self, "angle")
        layout.prop(self, "clear_sel")

    def execute(self, context):
        objs = resort_objects_by_selection(context, context.objects_in_mode)
        if not objs:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {"CANCELLED"}

        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)

            islands = island_util.get_island(context, bm, uv_layer)
            if not islands:
                self.report({'WARNING'}, "Select some Island.")
                return {"CANCELLED"}

            for island in islands:
                cl = ZenCluster(context, obj, island, bm)
                if self.clear_sel:
                    cl.deselect_all_edges()
                if self.direction == 'U':
                    axis = u_axis
                elif self.direction == 'V':
                    axis = v_axis
                edges = cl.get_edges_by_angle_to_axis(radians(self.angle), axis)
                for edge in edges:
                    edge.select(context)
            bm.select_flush_mode()
            bmesh.update_edit_mesh(me, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_Select_UV_Borders(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_uv_borders"
    bl_label = 'Select UV Borders'
    bl_zen_short_name = 'Borders'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select existing UV Borders'

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    mode: EnumProperty(
        name="Mode",
        description="Selection Type",
        items=[
            ("ISLAND", "By Island", "By selected island"),
            ("ALL_ISLANDS", "All Borders", "All UV border edges"),
            ("FACES", "By Faces", "By selected faces")
            ],
        default="ALL_ISLANDS")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'ALL_ISLANDS':
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            SelectUtils.select_uv_border(context, bm, bm.loops.layers.uv.active, self.mode, self.clear_selection)
            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_Select_OpenEdges(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_open_edges"
    bl_label = 'Select Open Edges'
    bl_zen_short_name = 'Open Edges'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select open edges. The way that looks in the 3d viewport'

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    mode: EnumProperty(
        name="Mode",
        description="Selection Type",
        items=[
            ("SELECT", "Select", "Select"),
            ("DESELECT", "Deselect", "Deselect")
            ],
        default="SELECT")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.enabled = self.mode == 'SELECT'
        row.prop(self, 'clear_selection')
        layout.prop(self, 'mode')

    def execute(self, context):
        from ZenUV.utils.generic import is_pure_edge_mode

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'SELECT':
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        p_state = self.mode == 'SELECT'

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()

            if is_pure_edge_mode(context):
                uv_layer = bm.loops.layers.uv.active
                if not uv_layer:
                    continue

                for i in get_open_edges_indices(bm):
                    for loop in bm.edges[i].link_loops:
                        loop[uv_layer].select = p_state
                        loop[uv_layer].select_edge = p_state
                        loop.link_loop_next[uv_layer].select = p_state
            else:
                for i in get_open_edges_indices(bm):
                    bm.edges[i].select = p_state

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_Select_SplitsEdges(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_splits_edges"
    bl_label = 'Select Splits Edges'
    bl_zen_short_name = 'Cylinder Edges (Splits)'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects island edges that belong to the same mesh edge and split the island by itself'

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    mode: EnumProperty(
        name="Mode",
        description="Selection Type",
        items=[
            ("SELECT", "Select", "Select"),
            ("DESELECT", "Deselect", "Deselect")
            ],
        default="SELECT")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.enabled = self.mode == 'SELECT'
        row.prop(self, 'clear_selection')
        layout.prop(self, 'mode')

    def execute(self, context):
        from ZenUV.utils import get_uv_islands as island_util

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'SELECT':
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        p_state = self.mode == 'SELECT'

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.edges.ensure_lookup_table()
            uv_layer = verify_uv_layer(bm)

            for island in island_util.get_islands(context, bm):
                if is_pure_edge_mode(context):
                    for i in get_splits_edges_indices(island, uv_layer):
                        for loop in bm.edges[i].link_loops:
                            loop[uv_layer].select = p_state
                            loop[uv_layer].select_edge = p_state
                            loop.link_loop_next[uv_layer].select = p_state
                else:
                    for i in get_splits_edges_indices(island, uv_layer):
                        bm.edges[i].select = p_state

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}


class ConditionEdge:
    def __init__(self, edge, splits_indices_list, open_indices_list, borders_indices_list):
        self.edge = edge
        self.sharp = self.init_is_sharp()
        self.seam = self.init_is_seam()
        self.splits = self.init_is_splits(splits_indices_list)
        self.boundary = self.init_is_borders(borders_indices_list)
        self.open = self.init_is_open(open_indices_list)

    def init_is_sharp(self):
        return not self.edge.smooth

    def init_is_seam(self):
        return self.edge.seam

    def init_is_splits(self, splits_indices_list):
        return self.edge.index in splits_indices_list

    def init_is_borders(self, borders_indices_list):
        return self.edge.index in borders_indices_list

    def init_is_open(self, open_indices_list):
        return self.edge.index in open_indices_list


class ZUV_OT_SelectEdgeByCondition(bpy.types.Operator):
    bl_idname = "mesh.select_edge_by_condition"
    bl_label = "Select Edge by Condition"
    bl_zen_short_name = 'Edges by Condition'
    bl_description = "Select edges based on various conditions and logic operations with NOT support"
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    select_condition: EnumProperty(
        name="Select Condition",
        items=[
            ("SHARP", "Sharp", "Select edges that are markerd sharp"),
            ("SEAM", "Seam", "Select edges that are markerd seam"),
            ("SPLITS", "Splits", "Selects edges that belong to the same mesh edge and split the island by itself"),
            ("BORDERS", "Borders", "Select edges that are UV borders"),
            ("OPEN", "Open", "Select edges that are open. Including those adjacent to hidden faces"),
        ],
        default="SHARP",
    )
    is_active_second_condition: BoolProperty(name="Second Condition", default=False)
    logic_operation: EnumProperty(
        name="Logical Operation",
        items=[
            ("AND", "AND", "All conditions must be true"),
            ("OR", "OR", "At least one condition must be true"),
            ("XOR", "XOR", "Only one condition can be true"),
            ("NOR", "NOR", "None of the conditions should be true"),
        ],
        default="AND",
    )
    apply_not: BoolProperty(name="Apply NOT", default=False)
    additional_condition: EnumProperty(
        name="Additional Condition",
        items=[
            ("SHARP", "Sharp", "Additional condition: edges that are markerd sharp"),
            ("SEAM", "Seam", "Additional condition: edges that are markerd seam"),
            ("SPLITS", "Splits", "Additional condition: edges that belong to the same mesh edge and split the island by itself"),
            ("BORDERS", "Borders", "Additional condition: edges that are UV borders"),
            ("OPEN", "Open", "Additional condition: edges that are open"),
        ],
        default="SEAM",
    )

    def draw(self, context):
        layout = self.layout
        p_split = 0.4
        layout.prop(self, 'clear_selection')
        box = layout.box()
        box.label(text='Select edge if:')
        row = box.row(align=True)
        split = row.split(factor=p_split, align=True)
        split.label(text="Edge is")
        split.prop(self, "select_condition", text="")

        layout.prop(self, 'is_active_second_condition')
        box = layout.box()
        box.enabled = self.is_active_second_condition
        row = box.row(align=True)
        split = row.split(factor=p_split, align=True)
        split.prop(self, "logic_operation", text="")

        row = box.row(align=True)
        split = row.split(factor=p_split, align=True)
        split.label(text="Edge is")
        p_text = 'Apply Not' if not self.apply_not else 'Not'
        split.prop(self, "apply_not", text=p_text, toggle=True)

        row = box.row(align=True)
        split = row.split(factor=p_split, align=True)
        split.prop(self, "additional_condition", text="")

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "EDGE"
        else:
            bpy.ops.mesh.select_mode(type="EDGE")

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        b_is_pure_edge_mode = is_pure_edge_mode(context)

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            bm.edges.ensure_lookup_table()

            p_state = True

            p_splits = []
            p_open = []
            p_borders = []
            if 'SPLITS' in {self.select_condition, self.additional_condition}:
                for island in island_util.get_islands(context, bm, is_include_hidden=True):
                    p_splits.extend(get_splits_edges_indices(island, uv_layer))
            if 'OPEN' in {self.select_condition, self.additional_condition}:
                p_open = get_open_edges_indices(bm)
            if 'BORDERS' in {self.select_condition, self.additional_condition}:
                p_borders = get_uv_bound_edges_indexes(bm.faces, uv_layer)

            condition_edges = [ConditionEdge(edge, p_splits, p_open, p_borders) for edge in bm.edges]

            conditions = {
                "SHARP": lambda edge: edge.sharp,
                "SEAM": lambda edge: edge.seam,
                "SPLITS": lambda edge: edge.splits,
                "BORDERS": lambda edge: edge.boundary,
                "OPEN": lambda edge: edge.open,
            }

            primary_condition = conditions[self.select_condition]
            secondary_condition = conditions[self.additional_condition]

            p_cond_edges_idxs = set()
            for condition_edge in condition_edges:
                primary_met = primary_condition(condition_edge)
                if self.is_active_second_condition:
                    if self.apply_not:
                        secondary_met = not secondary_condition(condition_edge)
                    else:
                        secondary_met = secondary_condition(condition_edge)
                else:
                    secondary_met = primary_met

                if self.logic_operation == "AND":
                    condition_met = primary_met and secondary_met
                elif self.logic_operation == "OR":
                    condition_met = primary_met or secondary_met
                elif self.logic_operation == "XOR":
                    condition_met = primary_met != secondary_met
                elif self.logic_operation == "NOR":
                    condition_met = not (primary_met or secondary_met)

                if condition_met:
                    p_cond_edges_idxs.add(condition_edge.edge.index)

            if b_is_pure_edge_mode:
                for index in p_cond_edges_idxs:
                    for loop in bm.edges[index].link_loops:
                        loop[uv_layer].select = p_state
                        loop[uv_layer].select_edge = p_state
                        loop.link_loop_next[uv_layer].select = p_state
            else:
                for index in p_cond_edges_idxs:
                    bm.edges[index].select = p_state

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data)

        return {'FINISHED'}


class ZUV_OT_Select_QuadedIslands(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_quaded_islands"
    bl_label = 'Select Quaded Islands'
    bl_zen_short_name = 'Quaded Islands'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects islands that consist only of quads'

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    mode: EnumProperty(
        name="Mode",
        description="Selection Type",
        items=[
            ("SELECT", "Select", "Select"),
            ("DESELECT", "Deselect", "Deselect")
            ],
        default="SELECT")

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.enabled = self.mode == 'SELECT'
        row.prop(self, 'clear_selection')
        layout.prop(self, 'mode')

    def execute(self, context):
        from collections import Counter

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        if self.clear_selection and self.mode == 'SELECT':
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        p_state = self.mode == 'SELECT'

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            bm.faces.ensure_lookup_table()
            uv_layer = verify_uv_layer(bm)

            for island in island_util.get_islands(context, bm):
                if Counter((len(f.verts) == 4 for f in island))[False] == 0:
                    if context.space_data and context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
                        if ZenPolls.version_since_3_2_0:
                            for f in island:
                                for lp in f.loops:
                                    lp[uv_layer].select = p_state
                                    lp[uv_layer].select_edge = p_state
                        else:
                            for f in island:
                                for lp in f.loops:
                                    lp[uv_layer].select = p_state
                    else:
                        for f in island:
                            f.select = p_state

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        return {'FINISHED'}


class ZUV_OT_ConvertSelFacesToSelLoops(bpy.types.Operator):
    bl_idname = "uv.zenuv_convert_sel_faces_to_sel_loops"
    bl_label = "Faces To UV Loops"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Convert selected mesh faces to UV loops and vice versa'

    toggle_uv_sync: bpy.props.BoolProperty(
        name='Toggle UV Sync',
        description='Toggle UV Sync Selection',
        default=True
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            return 'Convert selected UV loops to mesh face selection'
        else:
            return 'Convert selected mesh faces to UV loops'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}
        is_not_sync = context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            bm.faces.ensure_lookup_table()
            if uv_layer is None:
                continue
            if is_not_sync:
                bpy.ops.mesh.select_mode(type="FACE")

                p_state = [None] * len(bm.faces)

                if ZenPolls.version_since_3_2_0:
                    for face in bm.faces:
                        p_state[face.index] = False not in (lp[uv_layer].select_edge for lp in face.loops)
                else:
                    for face in bm.faces:
                        p_state[face.index] = False not in (lp[uv_layer].select for lp in face.loops)

                for face in bm.faces:
                    face.select = False

                for i, state in enumerate(p_state):
                    if state is True:
                        bm.faces[i].select = True

            else:
                if ZenPolls.version_since_3_2_0:
                    for face in bm.faces:
                        for loop in face.loops:
                            loop[uv_layer].select = face.select
                            loop[uv_layer].select_edge = face.select
                else:
                    for face in bm.faces:
                        for loop in face.loops:
                            loop[uv_layer].select = face.select

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        is_uv_sync = context.scene.tool_settings.use_uv_select_sync
        if self.toggle_uv_sync:
            if is_uv_sync:
                context.scene.tool_settings.use_uv_select_sync = False
                if bpy.ops.mesh.select_all.poll():
                    bpy.ops.mesh.select_all(action="SELECT")
            else:
                context.scene.tool_settings.use_uv_select_sync = True

        return {'FINISHED'}


class ZUV_OT_ConvertSelEdgesToSelLoops(bpy.types.Operator):
    bl_idname = "uv.zenuv_convert_sel_edges_to_sel_loops"
    bl_label = "Edges To UV Loops"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Convert selected mesh edges to UV loops and vice versa'

    toggle_uv_sync: bpy.props.BoolProperty(
        name='Toggle UV Sync',
        description='Toggle UV Sync Selection',
        default=True
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            return 'Convert selected UV loops to mesh edge selection'
        else:
            return 'Convert selected mesh edges to UV loops'

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}
        is_not_sync = context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = bm.loops.layers.uv.active
            bm.edges.ensure_lookup_table()
            if uv_layer is None:
                continue
            if is_not_sync:
                bpy.ops.mesh.select_mode(type="EDGE")

                p_state = [None] * len(bm.edges)

                if ZenPolls.version_since_3_2_0:
                    for edge in bm.edges:
                        p_state[edge.index] = any(lp[uv_layer].select_edge for lp in edge.link_loops)
                else:
                    for edge in bm.edges:
                        p_state[edge.index] = any(lp[uv_layer].select for lp in edge.link_loops)

                for edge in bm.edges:
                    edge.select = False

                for i, state in enumerate(p_state):
                    if state is True:
                        bm.edges[i].select = True

            else:
                if ZenPolls.version_since_3_2_0:
                    for edge in bm.edges:
                        for loop in edge.link_loops:
                            loop[uv_layer].select = edge.select
                            loop[uv_layer].select_edge = edge.select
                else:
                    for edge in bm.edges:
                        for loop in edge.link_loops:
                            loop[uv_layer].select = edge.select

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False)

        is_uv_sync = context.scene.tool_settings.use_uv_select_sync
        if self.toggle_uv_sync:
            if is_uv_sync:
                context.scene.tool_settings.use_uv_select_sync = False
                if bpy.ops.mesh.select_all.poll():
                    bpy.ops.mesh.select_all(action="SELECT")
            else:
                context.scene.tool_settings.use_uv_select_sync = True

        return {'FINISHED'}


class ZUV_OT_SelectLinkedLoops(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_linked_loops"
    bl_label = "Select Linked Loops"
    bl_zen_short_name = "Linked Loops"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects all loops belonging to the mesh vertex based on any already selected loop'

    @classmethod
    def description(cls, context, properties):
        s_desc = 'Selects all loops belonging to the mesh vertex based on any already selected loop'
        if context.scene.tool_settings.use_uv_select_sync:
            return f'Only for UV Sync Selection - off. {s_desc}'
        else:
            return cls.bl_description

    @classmethod
    def poll(cls, context):
        """ Validate context """
        is_no_sync = context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
        active_object = context.active_object
        return is_no_sync and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def execute(self, context):
        from ZenUV.utils.get_uv_islands import LoopsFactory

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}
        is_not_sync = context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync

        if is_not_sync:
            for obj in objs:
                bm = bmesh.from_edit_mesh(obj.data)
                uv_layer = bm.loops.layers.uv.active
                if uv_layer is None:
                    continue

                p_loops = LoopsFactory.loops_by_sel_mode(context, bm, uv_layer, groupped=False)

                if ZenPolls.version_since_3_2_0:
                    for loop in p_loops:
                        for lp in loop.vert.link_loops:
                            lp[uv_layer].select = True
                            if lp.link_loop_next[uv_layer].select is True:
                                lp[uv_layer].select_edge = True
                                lp.link_loop_radial_next[uv_layer].select_edge = True

                else:
                    for loop in p_loops:
                        for lp in loop.vert.link_loops:
                            lp[uv_layer].select = True

                bm.select_flush_mode()
                bmesh.update_edit_mesh(obj.data, loop_triangles=False)
        else:
            self.report({'WARNING'}, "Only in UV Sync Selection is Off")
            return {'CANCELLED'}

        return {'FINISHED'}


class ZUV_OT_SelectHalf(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_half"
    bl_label = 'Select Half'
    bl_zen_short_name = 'Half'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Selects a part of the model according to its location relative to the coordinate axis'

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)
    mesh_axis: bpy.props.EnumProperty(
        name='Mesh Axis',
        description='The axis along which the selection is made',
        items=[
            ("X", "X", "Aalong the X axis"),
            ("Y", "Y", "Along the Y axis"),
            ("Z", "Z", "Along the Z axis")],
        default='X')
    axis_direction: bpy.props.EnumProperty(
        name='Axis Direction',
        description='Axis direction',
        items=[
            ("NEGATIVE", "-", "Negative"),
            ("POSITIVE", "+", "Positive")],
        default='POSITIVE')
    include_zero: BoolProperty(
        name='Include Zero',
        description='Including zero coordinates',
        default=True)

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'clear_selection')
        row = layout.row(align=True)
        row.label(text='Mesh Axis:')
        row = row.row(align=True)
        s = row.split(factor=0.2, align=True)
        row = s.row(align=True)
        row.prop(self, 'axis_direction', expand=True)
        s.prop(self, 'mesh_axis', text='')
        layout.prop(self, 'include_zero')

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        b_is_not_sync = context.space_data.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync
        self.precision = 6

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_deselect_by_context
            bpy_deselect_by_context(context)

        p_axis = {'X': 0, 'Y': 1, 'Z': 2}[self.mesh_axis]

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            if b_is_not_sync:
                p_uv_select_mode = context.scene.tool_settings.uv_select_mode
                if p_uv_select_mode == 'EDGE':
                    for e in self.collect_edges(p_axis, bm):
                        self._select_loops(uv_layer, e.link_loops)

                    if not self.include_zero:
                        for e in self.get_zero_edges(p_axis, bm):
                            for lp in e.link_loops:
                                lp[uv_layer].select = False
                                if ZenPolls.version_since_3_2_0:
                                    lp[uv_layer].select_edge = False

                elif p_uv_select_mode == 'FACE':
                    p_cache = self.collect_faces(bm)
                    if self.axis_direction == 'NEGATIVE':
                        for i in p_cache:
                            if i[0][p_axis] < 0:
                                self._select_loops(uv_layer, i[1].loops)
                    else:
                        for i in p_cache:
                            if i[0][p_axis] > 0:
                                self._select_loops(uv_layer, i[1].loops)
                    if self.include_zero:
                        for i in p_cache:
                            if i[0][p_axis] == 0:
                                self._select_loops(uv_layer, i[1].loops)

                else:
                    p_cache = self.collect_verts(bm)
                    if self.axis_direction == 'NEGATIVE':
                        for i in p_cache:
                            if i[0][p_axis] < 0:
                                self._select_loops(uv_layer, i[1].link_loops)
                    else:
                        for i in p_cache:
                            if i[0][p_axis] > 0:
                                self._select_loops(uv_layer, i[1].link_loops)

                    if self.include_zero:
                        for i in p_cache:
                            if i[0][p_axis] == 0:
                                self._select_loops(uv_layer, i[1].link_loops)
            else:
                p_mesh_select_mode = context.tool_settings.mesh_select_mode[:]

                if p_mesh_select_mode == (False, True, False):
                    for e in self.collect_edges(p_axis, bm):
                        e.select = True

                    if not self.include_zero:
                        for e in self.get_zero_edges(p_axis, bm):
                            e.select = False

                elif p_mesh_select_mode == (False, False, True):
                    self.select_mesh_items(p_axis, self.collect_faces(bm))

                else:
                    self.select_mesh_items(p_axis, self.collect_verts(bm))

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        return {'FINISHED'}

    def _select_loops(self, uv_layer, loops):
        for lp in loops:
            lp[uv_layer].select = True
            if ZenPolls.version_since_3_2_0:
                lp[uv_layer].select_edge = True

    def collect_verts(self, bm):
        return [(v.co.to_tuple(self.precision), v) for v in bm.verts]

    def collect_faces(self, bm):
        return [(f.calc_center_bounds().to_tuple(self.precision), f) for f in bm.faces]

    def collect_edges(self, p_axis, bm):
        if self.axis_direction == 'NEGATIVE':
            return (e for e in bm.edges if False not in [v.co.to_tuple(self.precision)[p_axis] <= 0 for v in e.verts])
        else:
            return (e for e in bm.edges if False not in [v.co.to_tuple(self.precision)[p_axis] >= 0 for v in e.verts])

    def get_zero_edges(self, p_axis, bm):
        return (e for e in bm.edges if False not in [v.co.to_tuple(self.precision)[p_axis] == 0 for v in e.verts])

    def select_mesh_items(self, p_axis, p_cache):
        if self.axis_direction == 'NEGATIVE':
            for i in p_cache:
                if i[0][p_axis] < 0:
                    i[1].select = True
        else:
            for i in p_cache:
                if i[0][p_axis] > 0:
                    i[1].select = True
        if self.include_zero:
            for i in p_cache:
                if i[0][p_axis] == 0:
                    i[1].select = True


class AreaIsland:

    def __init__(self, faces, uv_layer) -> None:
        self.faces = faces
        self.area = UvFaceArea.get_uv_faces_area(faces, uv_layer) * FACE_UV_AREA_MULT


class ZUV_OT_SelectByUvArea(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_by_uv_area"
    bl_label = 'Select by UV Area'
    bl_zen_short_name = 'By UV Area'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = 'Select faces by their UV area'

    clear_selection: bpy.props.BoolProperty(
        name=ZuvLabels.OT_TDPR_SEL_BY_TD_CLEAR_SEL_LABEL,
        description=ZuvLabels.OT_TDPR_SEL_BY_TD_CLEAR_SEL_DESC,
        default=True
        )

    condition: EnumProperty(
        name=ZuvLabels.PROP_SEL_BY_UV_AREA_CONDITION_LABEL,
        description=ZuvLabels.PROP_SEL_BY_UV_AREA_CONDITION_DESC,
        items=[
            ("LESS", "Less than", ""),
            ("EQU", "Equal to", ""),
            ("MORE", "More than", ""),
            ("WITHIN", "Within range", ""),
            ("ZERO", "Zero Area", "")
        ],
        default="ZERO"
    )
    treshold: bpy.props.FloatProperty(
        name=ZuvLabels.PROP_SEL_BY_UV_AREA_TRESHOLD_LABEL,
        description=ZuvLabels.PROP_SEL_BY_UV_AREA_TRESHOLD_DESC,
        precision=2,
        default=0.5,
        min=0.0
    )
    mode: EnumProperty(
        name="Mode",
        description="Mode for getting area",
        items=[
            ('ISLAND', 'Island', 'Get Area from selected island'),
            ('FACE', 'Face', 'Get area from selected faces'),
        ],
        default="ISLAND"
    )

    def draw(self, context):
        sc_lv_prop = context.scene.zen_uv
        layout = self.layout
        layout.prop(self, 'mode')
        layout.prop(self, "clear_selection")
        box = layout.box()
        box.label(text=ZuvLabels.LABEL_SEL_BY_UV_AREA_DRAW if self.mode == 'FACE' else ZuvLabels.LABEL_SEL_BY_UV_AREA_DRAW.replace('Faces', 'Islands'))
        box.prop(self, "condition")
        if self.condition == "WITHIN":
            row = box.row(align=True)
            row.prop(sc_lv_prop, "range_value_start")
            row.prop(sc_lv_prop, "range_value_end")
        elif self.condition == "ZERO":
            pass
        else:
            box.prop(sc_lv_prop, "area_value_for_sel")
        box.prop(self, "treshold")

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}

        for obj in objs:
            if len(obj.data.uv_layers) == 0:
                self.report({'WARNING'}, f"Cancelled. Object {obj.name} have no active UV Map.")
                return {'CANCELLED'}

        uv_sync = context.scene.tool_settings.use_uv_select_sync
        self.sc_lv_prop = context.scene.zen_uv

        condition = {"LESS": self.less, "EQU": self.equ, "MORE": self.more, "WITHIN": self.within, "ZERO": self.zero}

        if self.clear_selection:
            bpy.ops.uv.select_all(action='DESELECT')

        p_counter = 0
        if context.area.type == 'IMAGE_EDITOR' and not uv_sync:

            context.scene.tool_settings.uv_select_mode = "FACE"

            for obj in objs:
                bm, me, uv_layer = self.get_bmesh_from_obj(obj)
                if self.mode == 'FACE':
                    for_sel_faces = [f for f in bm.faces if condition[self.condition](UvFaceArea.get_uv_faces_area([f, ], uv_layer) * FACE_UV_AREA_MULT, self.sc_lv_prop.area_value_for_sel)]
                else:
                    for_sel_faces = self.get_faces_for_select(context, condition, bm, uv_layer)
                select_by_context(context, bm, [for_sel_faces, ], state=True)
                p_counter += sum(1 for _ in for_sel_faces)
                self.update_edit_bmesh(bm, me)
        else:

            bpy.ops.mesh.select_mode(type="FACE")

            for obj in objs:
                bm, me, uv_layer = self.get_bmesh_from_obj(obj)
                init_selection = [f.index for f in bm.faces if f.select]
                if self.mode == 'FACE':
                    for face in bm.faces:
                        p_condition = condition[self.condition](UvFaceArea.get_uv_faces_area([face, ], uv_layer) * FACE_UV_AREA_MULT, self.sc_lv_prop.area_value_for_sel)
                        face.select = p_condition
                        p_counter += p_condition
                else:
                    for face in self.get_faces_for_select(context, condition, bm, uv_layer):
                        face.select = True
                        p_counter += 1

                if not self.clear_selection:
                    self.restore_selection(bm, init_selection)

                self.update_edit_bmesh(bm, me)

        if self.condition == 'ZERO':
            self.report({'INFO'}, f"Selected {p_counter} zero area face{'s' if p_counter != 1 else ''}")

        return {'FINISHED'}

    def get_faces_for_select(self, context, condition, bm, uv_layer):
        islands = island_util.get_islands(context, bm)
        ar_islands = [AreaIsland(island, uv_layer) for island in islands]
        return chain.from_iterable([i.faces for i in ar_islands if condition[self.condition](i.area, self.sc_lv_prop.area_value_for_sel)])

    def update_edit_bmesh(self, bm, me):
        bm.select_flush_mode()
        bmesh.update_edit_mesh(me, loop_triangles=False)

    def get_bmesh_from_obj(self, obj):
        bm = bmesh.from_edit_mesh(obj.data)
        bm.faces.ensure_lookup_table()
        uv_layer = verify_uv_layer(bm)
        return bm, obj.data, uv_layer

    def restore_selection(self, bm, init_selection):
        for i in init_selection:
            bm.faces[i].select = True

    def less(self, area, value):
        return area < value + self.treshold

    def equ(self, area, value):
        return value - self.treshold < area <= value + self.treshold

    def more(self, area, value):
        return area > value - self.treshold

    def within(self, area, value):
        return self.sc_lv_prop.range_value_start - self.treshold <= area <= self.sc_lv_prop.range_value_end + self.treshold

    def zero(self, area, value):
        return area <= 0.0 + self.treshold


class ZUV_OT_GrabSelectedArea(bpy.types.Operator):
    bl_idname = "uv.zenuv_grab_sel_area"
    bl_label = 'Get Selected Area'
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Get the area of the selected. This value is used in the 'Select by UV Area' operator"

    real_area: FloatProperty(
        name=ZuvLabels.PROP_GET_UV_REAL_LABEL,
        description=ZuvLabels.PROP_GET_UV_REAL_DESC,
        default=0.0,
        options={'HIDDEN'}
    )
    multiplied_area: FloatProperty(
        name=ZuvLabels.PROP_GET_UV_MULT_LABEL,
        description=ZuvLabels.PROP_GET_UV_REAL_DESC,
        default=2.0,
        options={'HIDDEN'},
    )
    mode: EnumProperty(
        name="Mode",
        description="Mode for getting area",
        items=[
            ('ISLAND', 'Island', 'Get Area from selected island'),
            ('FACE', 'Face', 'Get area from selected faces'),
        ],
        default="ISLAND"
    )
    average: bpy.props.BoolProperty(
        name='Average',
        description='Get the average value from the selected',
        default=False
        )

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'mode')
        layout.prop(self, 'average')
        box = layout.box()
        box.prop(self, "real_area")
        box.label(text="Real UV Area" + ": " + str(self.real_area))
        box.prop(self, "multiplied_area")

    def execute(self, context):
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "There are no selected objects")
            return {'CANCELLED'}
        self.sc_lv_prop = context.scene.zen_uv
        sel_faces_count = []
        part_area = []
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data).copy()
            uv_layer = verify_uv_layer(bm)
            bm.faces.ensure_lookup_table()
            if self.mode == 'FACE':
                faces = [bm.faces[i] for i in FacesFactory.face_indexes_by_sel_mode(context, bm)]
                sel_faces_count.append(len(faces))
                part_area.append(sum([UvFaceArea.get_uv_faces_area([face, ], uv_layer) for face in faces]))
            else:
                islands = island_util.get_island(context, bm, uv_layer)
                sel_faces_count.append(len(islands))
                faces = [f for island in islands for f in island]
                part_area.append(sum([UvFaceArea.get_uv_faces_area([face, ], uv_layer) for face in faces]))
        sel_faces_count = sum(sel_faces_count)
        if sel_faces_count != 0:
            self.real_area = sum(part_area)
            if self.average:
                self.real_area /= sel_faces_count
            self.multiplied_area = self.real_area * FACE_UV_AREA_MULT
            self.sc_lv_prop.area_value_for_sel = self.multiplied_area
            self.update_range_values()
            self.report({'INFO'}, f'Area of selected {"islands " if self.mode == "ISLAND" else "faces "} {self.real_area}')
        else:
            self.report({'WARNING'}, "There are no selected faces")
        return {'FINISHED'}

    def update_range_values(self):
        self.sc_lv_prop.range_value_start = self.multiplied_area - 2
        self.sc_lv_prop.range_value_end = self.multiplied_area + 2


class ZUV_OP_SelectIalsndByDirection(bpy.types.Operator):
    bl_idname = "uv.zenuv_select_island_by_direction"
    bl_label = 'Select Island by Direction'
    bl_zen_short_name = 'Island by Direction'
    bl_description = 'Select island by direction'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    orient_direction: bpy.props.EnumProperty(
        name="Type",
        description="What type of islands will be selected",
        items=[
            ("HORIZONTAL", "Horizontal", "Horizontally oriented islands"),
            ("VERTICAL", "Vertical", "Vertically oriented islands"),
            ("RADIAL", "Radial", "Islands that are shaped like a circle"),
            ("NOT_ALIGNED", "Not Aligned", "Islands that are not aligned with the axes"),
        ],
        default="HORIZONTAL"
    )

    def execute(self, context):
        from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage

        def is_oriented(p_angle):
            return abs(p_angle) < 0.0087  # Half a degree

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "FACE"
        else:
            bpy.ops.mesh.select_mode(type="FACE")

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_select_by_context
            bpy_select_by_context(context, action='DESELECT')

        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            for island in island_util.get_islands(context, bm):
                p_bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)
                p_angle = p_bbox.get_orient_angle(ActiveUvImage(context).aspect)
                is_island_radial = p_bbox.is_circle()

                if not is_island_radial and self.orient_direction == 'HORIZONTAL':
                    if is_oriented(p_angle) and p_bbox.len_x > p_bbox.len_y:
                        select_by_context(context, bm, [island, ], state=True)

                elif self.orient_direction == 'VERTICAL':
                    if not is_island_radial and is_oriented(p_angle) and p_bbox.len_x < p_bbox.len_y:
                        select_by_context(context, bm, [island, ], state=True)

                elif self.orient_direction == 'RADIAL':
                    if is_island_radial:
                        select_by_context(context, bm, [island, ], state=True)

                else:
                    if not is_island_radial and not is_oriented(p_angle):
                        select_by_context(context, bm, [island, ], state=True)

            bm.select_flush_mode()

        return {'FINISHED'}


class ZUV_OP_SelectHoledIslands(bpy.types.Operator):
    bl_idname = 'uv.zenuv_select_holed_islands'
    bl_label = 'Select Holed Islands'
    bl_description = 'Selects islands that have holes within their geometry'
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


class ZUV_OT_SelectFacesLessOnePixel(bpy.types.Operator):
    bl_description = 'Selects faces with an area less than the specified number of pixels'
    bl_idname = 'uv.zenuv_select_faces_less_than_pixel'
    bl_zen_short_name = 'Faces Less than Pixel'
    bl_label = 'Select Faces Less than Pixel'
    bl_options = {'REGISTER', 'UNDO'}

    clear_selection: bpy.props.BoolProperty(
        name='Clear Selection',
        description='Clear initial selection',
        default=True)

    pixel_count: bpy.props.IntProperty(
        name="Pixel Count",
        description="Number of pixels for the calculation",
        default=1,
        min=1
    )

    area_threshold: bpy.props.FloatProperty(
        name="Area Threshold",
        description="Tolerance level for face area selection",
        default=0.0,
        min=0.0,
        max=1.0
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return context.area.type == 'IMAGE_EDITOR' and active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout
        layout.prop(self, 'clear_selection')
        layout.prop(self, 'pixel_count')
        layout.prop(self, 'area_threshold')

    def execute(self, context):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils

        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'WARNING'}, "Zen UV: There are no selected objects.")
            return {'CANCELLED'}

        p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
        if p_image is None:
            self.report({'ERROR'}, "No image selected in the UV Editor.")
            return {'CANCELLED'}

        if p_image.size[0] == 0 or p_image.size[1] == 0:
            self.report({'ERROR'}, "The active image in the UV Editor is incorrect.")
            return {'CANCELLED'}

        if context.area.type == 'IMAGE_EDITOR' and not context.scene.tool_settings.use_uv_select_sync:
            context.scene.tool_settings.uv_select_mode = "FACE"
        else:
            bpy.ops.mesh.select_mode(type="FACE")

        if self.clear_selection:
            from ZenUV.utils.generic import bpy_select_by_context, select_by_context
            bpy_select_by_context(context, action='DESELECT')

        p_pixel_size = 1 / p_image.size[0], 1 / p_image.size[1]

        p_pixel_area = p_pixel_size[0] * p_pixel_size[1] * self.pixel_count

        p_counter = 0
        for obj in objs:
            bm = bmesh.from_edit_mesh(obj.data)
            uv_layer = verify_uv_layer(bm)

            bm.faces.ensure_lookup_table()

            for f in bm.faces:
                if UvFaceArea.get_uv_faces_area([f, ], uv_layer) <= p_pixel_area * (1 + self.area_threshold):
                    select_by_context(context, bm, [[f], ], state=True)
                    p_counter += 1

            bm.select_flush_mode()
            bmesh.update_edit_mesh(obj.data, loop_triangles=False, destructive=False)

        if p_counter:
            p_message = f'Selected {p_counter} face{"s" if p_counter != 1 else ""}'
        else:
            p_message = 'No faces were selected'

        self.report({'INFO'}, p_message)

        return {'FINISHED'}


select_classes = (
    ZUV_OT_Select_UV_Borders,
    ZUV_OT_SelectByUvArea,
    ZUV_OT_GrabSelectedArea,
    ZUV_OT_SelectInTile,
    ZUV_OT_SelectHalf,
    ZUV_OT_ConvertSelFacesToSelLoops,
    ZUV_OT_SelectLinkedLoops,
    ZUV_OT_Select_OpenEdges,
    ZUV_OT_Select_QuadedIslands,
    ZUV_OT_Select_SplitsEdges,
    ZUV_OT_SelectEdgeByCondition,
    ZUV_OT_ConvertSelEdgesToSelLoops,
    ZUV_OP_SelectIalsndByDirection,
    ZUV_OP_SelectHoledIslands,
    ZUV_OT_SelectFacesLessOnePixel
)


poll_3_2_select_classes = (
    ZUV_OT_SelectEdgesByDirection,

)

if __name__ == '__main__':
    pass
