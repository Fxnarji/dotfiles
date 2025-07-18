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

""" Zen UV The batch transformation is dependent on the Trim module """

# Copyright 2023, Valeriy Yatsenko

import bpy
import bmesh
from dataclasses import dataclass, field
from mathutils import Vector
from random import choice

from ZenUV.utils.register_util import RegisterUtils
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.ops.trimsheets.trimsheet import ZuvTrimsheetGroup
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.utils.generic import get_mesh_data, Scope
from ZenUV.utils.generic import resort_by_type_mesh_in_edit_mode_and_sel, verify_uv_layer
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
from ZenUV.utils.vlog import Log

from .hotspot import HspPropertiesBase


CAT = 'DIR_HOTSPOT'


@dataclass
class HspTrim:

    trim: ZuvTrimsheetGroup = None
    bbox: BoundingBox2d = None
    normal: Vector = None  # 3 Dimension

    def __hash__(self):
        return hash(tuple(self.bbox.center))

    @property
    def radial(self):
        if self.trim.get_tag_value(tag_category='HOTSPOT', default='None') == 'Radial':
            return True
        return False


@dataclass
class HspIsland:

    faces: list = field(default_factory=list)
    bbox: BoundingBox2d = None
    normal: Vector = None  # 3 Dimension
    _loops: list = field(default_factory=list)

    def __hash__(self):
        return hash(tuple(self.faces))

    @property
    def loops(self):
        return [lp for f in self.faces for lp in f.loops]

    @property
    def radial(self):
        if self._radial is None:
            self._radial = self.bbox.is_circle()
        return self._radial

    @radial.setter
    def radial(self):
        raise RuntimeError('HspIsland.radial read only.')


@dataclass
class HspProperties(HspPropertiesBase):
    """ HotspotFactory Properties """
    trims_preselection: str = 'ALL'  # in {"ALL", "SELECTED"}
    orient: str = 'AS_IS'  # in {"NONE", "WORLD", "ORIENT"}
    compliance: str = 'STRICT'  # in {"STRICT", "NEAREST"}
    allow_location_variation: bool = False
    keep_proportion: bool = True

    def __post_init__(self, PROPS) -> None:
        super().__post_init__(PROPS)


class HotspotFactory(HspProperties):

    def __init__(self, PROPS: bpy.types.OperatorProperties) -> None:
        super().__post_init__(PROPS)

        self.hTrims = []
        self.hIslands = []


class HspStorage:

    def __init__(self) -> None:

        self.trims = set()
        self.islands = set()

        self.radial_trims = set()
        self.radial_islands = set()

        self._trims_count = 0
        self._islands_count = 0

        self.radial_islands_idxs_scope = []

    @property
    def islands_count(self):
        self._islands_count = len(self.islands) + len(self.radial_islands)
        return self._islands_count

    def collect_trims(self, trimsheet: list) -> None:
        self.trims.clear()
        for trim in trimsheet:
            trim_bbox = BoundingBox2d(points=(trim.left_bottom, trim.top_right))

            self.trims.add(
                HspTrim(
                    trim=trim,
                    bbox=trim_bbox,
                    normal=trim.normal
                )
            )

    def collect_islands(self, context, bm, uv_layer) -> None:
        self.islands.clear()
        for island in island_util.get_island(context, bm, uv_layer):
            i_bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)
            i_normal = self.get_cluster_overall_normal(island)
            self.islands.add(
                HspIsland(
                    faces=island,
                    bbox=i_bbox,
                    normal=i_normal.normalized()
                )
            )

    def get_cluster_overall_normal(self, island):
        normal = Vector()
        for face in island:
            normal += face.normal
        return normal

    def get_normal_suited_trims(self, container, normal, compliance):
        t_scp = Scope()
        t_scp.name = 'Trims Scope'
        for trim in container:
            t_scp.append(trim.normal.copy().freeze(), trim)
        if compliance == 'STRICT':
            keys = [key for key in t_scp.data.keys() if key.angle(normal, 180) == 0.0]
            if len(keys):
                return t_scp.data[keys[0]]
            else:
                return None
        return t_scp.data[min(t_scp.data.keys(), key=lambda x: normal.angle(x, 180))]


class DirHotspotFactory(HotspotFactory):

    def __init__(self, PROPS: bpy.types.OperatorProperties) -> None:
        super().__init__(PROPS)

    def conditional_store_trims(self, p_trimsheet):
        HST = HspStorage()

        if self.trims_preselection == 'SELECTED':
            p_presel_trims = [tr for tr in p_trimsheet if tr.selected]
        else:
            p_presel_trims = p_trimsheet
        HST.collect_trims(p_presel_trims)
        return HST

    def do_directional_hotspotting(self, context: bpy.types.Context, objs: list, p_trimsheet: list):
        # Log.debug_header(' Start Dir Hotspot ')
        from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
        HST = self.conditional_store_trims(p_trimsheet)

        i_counter = 0
        for obj in objs:
            me, bm = get_mesh_data(obj)
            uv_layer = verify_uv_layer(bm)
            M = obj.matrix_world

            HST.collect_islands(context, bm, uv_layer)

            if self.orient == 'WORLD':
                self.world_orient_islands(context, obj, bm, HST.islands)
                HST.update_islands(uv_layer)
            elif self.orient == 'ORIENT':
                self.orient_to_near_axis(context, HST.islands, uv_layer)
                HST.update_islands(uv_layer)

            for island in HST.islands:
                suited_trims = HST.get_normal_suited_trims(HST.trims, island.normal, self.compliance)

                if suited_trims is None:
                    continue

                if self.allow_location_variation:
                    suited_trim = choice(suited_trims)
                else:
                    suited_trim = suited_trims[0]

                TransformLoops.fit_loops(
                        island.loops,
                        uv_layer,
                        suited_trim.bbox,
                        'AUTO',
                        keep_proportion=self.keep_proportion,
                        angle=0.0,
                        image_aspect=ActiveUvImage(context).aspect,
                        rotate=False
                    )
            i_counter += HST.islands_count
            bmesh.update_edit_mesh(me)
        return i_counter


class ZUV_OT_TrHotspotByNormal(bpy.types.Operator):
    bl_idname = "uv.zenuv_fit_to_trim_by_normal"
    bl_label = "Hotspot by Normal"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Hotspot by Island normal mapping"

    trims_preselection: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ("ALL", "All Trims", "Use all available Trims"),
            ("SELECTED", "Selected Trims", "Use only the selected Trims"),
        ],
        description='Use all Trims or selected Trims to map Islands',
        default='ALL'
    )
    orient: bpy.props.EnumProperty(
        name='Orient',
        description='Perform some Island rotation before Hotspotting',
        items=[
            ("AS_IS", "As is", "No rotation at all"),
            ("WORLD", "Orient to World", "Orient to World"),
            ("ORIENT", "Orient to axis", "Auto orient island to nearest axis")
            ],
        default='AS_IS'
    )
    compliance: bpy.props.EnumProperty(
        name='Compliance',
        description='Perform some Island rotation before Hotspotting',
        items=[
            ("STRICT", "Strict", "Maintain strict compliance with the Island normal and the Trim normal"),
            ("NEAREST", "Nearest", "Maintain approximate correspondence to the normals. If a strictly matching normal is not found, the island will be assigned to the Trim with a similar normal"),
            ],
        default='STRICT'
    )
    keep_proportion: bpy.props.BoolProperty(
        name="Keep proportion",
        description="",
        default=True,
    )
    allow_location_variation: bpy.props.BoolProperty(
        name='Allow Location Variation',
        description='Allow islands to be placed in other trims with similar parameters',
        default=False
    )
    seed: bpy.props.IntProperty(
        name='Seed',
        description='Seed of variable island distribution in similar trims',
        default=132,
    )

    @classmethod
    def poll(cls, context):
        """ Validate context """
        active_object = context.active_object
        return active_object is not None and active_object.type == 'MESH' and context.mode == 'EDIT_MESH'

    def draw(self, context):
        layout = self.layout

        # Preprocess
        layout.label(text='Preprocess:')
        box = layout.box()
        box.prop(self, 'trims_preselection')
        box.prop(self, 'orient')

        # Settings
        layout.label(text='Settings:')
        box = layout.box()
        box.prop(self, 'keep_proportion')
        box.prop(self, 'compliance')

        # Variability
        layout.label(text='Variability:')
        box = layout.box()
        box.prop(self, 'allow_location_variation')
        box.prop(self, 'seed')

    def execute(self, context):
        self.cat = 'HOTSPOT'
        self.tag = 'Radial'
        objs = resort_by_type_mesh_in_edit_mode_and_sel(context)
        if not objs:
            self.report({'INFO'}, "There are no selected objects.")
            return {'CANCELLED'}

        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if not len(p_trimsheet):
            self.report({'INFO'}, "There are no trims.")
            return {'CANCELLED'}

        HSP = DirHotspotFactory(self.properties)
        i_counter = HSP.do_directional_hotspotting(context, objs, p_trimsheet)

        if not i_counter:
            self.report({'WARNING'}, "Zen UV: Select something.")
            return {'CANCELLED'}

        return {"FINISHED"}


classes = (
    ZUV_OT_TrHotspotByNormal,
)


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
