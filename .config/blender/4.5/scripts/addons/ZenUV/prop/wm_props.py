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

# Copyright 2023, Alex Zhornyak, alexander.zhornyak@gmail.com

import bpy

import numpy as np
from dataclasses import dataclass
from timeit import default_timer as timer
import uuid

from ZenUV.utils.vlog import Log
from ZenUV.ops.event_service import get_blender_event
from ZenUV.ops.texel_density.td_props import TdProps


@dataclass
class TimeDataUVMap:
    time: float = 0.0
    idx: int = -1

    obj = None
    literal_id = 'zenuv_uvmap_time_data'


class ZuvUVMeshGroup(bpy.types.PropertyGroup):
    mesh_name: bpy.props.StringProperty(
        name='Mesh Name',
        default=''
    )

    obj_name: bpy.props.StringProperty(
        name='Object Name',
        default=''
    )

    def get_obj(self, context: bpy.types.Context) -> bpy.types.Object:
        return context.view_layer.objects.get(self.obj_name, None)

    def get_mesh(self, context: bpy.types.Context) -> bpy.types.Mesh:
        return bpy.data.meshes.get(self.mesh_name, None)


class ZuvUVMapWrapper(bpy.types.PropertyGroup):
    select: bpy.props.BoolProperty(
        name='Select',
        default=False
    )

    def _update_name_ex(self, context):
        bpy.app.driver_namespace[TimeDataUVMap.literal_id] = TimeDataUVMap()

    @classmethod
    def rename_uv(cls, value: str, p_uv: bpy.types.MeshUVLoopLayer, p_uv_layers: bpy.types.UVLoopLayers):
        if p_uv:
            if p_uv.name != value:
                s_was_name = p_uv.name

                p_uv.name = value

                # NOTE: Blender can change name if it existed before
                s_new_name = p_uv.name
                if s_new_name != value:
                    p_exist_uv: bpy.types.MeshUVLoopLayer = p_uv_layers.get(value, None)
                    if p_exist_uv:
                        p_exist_uv.name = str(uuid.uuid4())
                        p_uv.name = str(uuid.uuid4())

                        # NOTE: swap names if exists, make the same behaviour as Outliner
                        p_exist_uv.name = s_was_name
                        p_uv.name = value

    @classmethod
    def rename_uv_2(cls, value: str, p_uv: bpy.types.MeshUVLoopLayer, p_uv_layers: bpy.types.UVLoopLayers):
        if p_uv:
            if p_uv.name != value:
                p_uv.name = value

                s_new_name = p_uv.name

                # NOTE: Blender can change name if it existed before
                if p_uv.name != value:
                    p_exist_uv: bpy.types.MeshUVLoopLayer = p_uv_layers.get(value, None)
                    if p_exist_uv:
                        # NOTE: swap names if exists, make the same behaviour as Outliner
                        p_uv.name = str(uuid.uuid4())
                        p_exist_uv.name = s_new_name
                        p_uv.name = value

    def _set_name_ex(self, value):
        if not value:
            return

        was_name = self.name

        context = bpy.context
        for me_group in self.mesh_groups:
            me: bpy.types.Mesh = me_group.get_mesh(context)
            if me:
                p_uv_layers = me.uv_layers
                p_uv = p_uv_layers.get(was_name, None)

                ZuvUVMapWrapper.rename_uv(value, p_uv, p_uv_layers)

        self.name = value

    name_ex: bpy.props.StringProperty(
        name='Name',
        description='Set UV map name of the selected objects',
        get=lambda self: self.name,
        set=_set_name_ex,
        update=_update_name_ex,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def _set_name_ex_active(self, value):
        was_name = self.name

        p_act_obj = bpy.context.active_object
        if p_act_obj and p_act_obj.type == 'MESH':
            p_uv = p_act_obj.data.uv_layers.get(was_name, None)
            if p_uv:
                if p_uv.name != value:
                    p_uv.name = value

    name_ex_active: bpy.props.StringProperty(
        name='Name',
        description='Set UV map name of the active object',
        get=lambda self: self.name,
        set=_set_name_ex_active,
        update=_update_name_ex,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def _set_name_ex_auto(self, value):
        p_scene_props = bpy.context.scene.zen_uv.adv_maps
        if p_scene_props.sync_adv_maps:
            self._set_name_ex(value)
        else:
            self._set_name_ex_active(value)

    name_ex_auto: bpy.props.StringProperty(
        name='Name',
        description='UV map name',
        get=lambda self: self.name,
        set=_set_name_ex_auto,
        update=_update_name_ex,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def _get_active_render(self):
        if len(self.mesh_groups) > 0:
            me = self.mesh_groups[0].get_mesh(bpy.context)
            if me:
                p_uv = me.uv_layers.get(self.name, None)
                if p_uv:
                    return p_uv.active_render
        return False

    def _set_active_render(self, value):
        me_group: ZuvUVMeshGroup
        for me_group in self.mesh_groups:
            me = me_group.get_mesh(bpy.context)
            if me:
                p_uv = me.uv_layers.get(self.name, None)
                if p_uv:
                    if not p_uv.active_render:
                        # Always set to True as in Blender
                        p_uv.active_render = True

    def _set_active_render_active(self, value):
        p_act_obj = bpy.context.active_object
        if p_act_obj and p_act_obj.type == 'MESH':
            p_uv = p_act_obj.data.uv_layers.get(self.name, None)
            if p_uv:
                p_uv.active_render = True

    active_render_ex: bpy.props.BoolProperty(
        name='Active Render',
        description='Set the UV map as active for rendering of the selected objects',
        get=_get_active_render,
        set=_set_active_render,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    active_render_ex_active: bpy.props.BoolProperty(
        name='Active Render',
        description='Set the UV map as active for rendering of the active object',
        get=_get_active_render,
        set=_set_active_render_active,
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    mesh_groups: bpy.props.CollectionProperty(
        type=ZuvUVMeshGroup
    )


class ZuvObjUVGroup(bpy.types.PropertyGroup):
    uvmaps: bpy.props.CollectionProperty(
        name='Selected Object UVS',
        type=ZuvUVMapWrapper
    )

    lock_selection_by_index: bpy.props.BoolProperty(
        name='Lock Selection by Index',
        default=False
    )

    selected_meshes: bpy.props.CollectionProperty(
        type=ZuvUVMeshGroup
    )

    active_uv_name: bpy.props.StringProperty(
        name='Active UV Name',
        default=''
    )

    active_mesh_name: bpy.props.StringProperty(
        name='Active Mesh Name',
        default=''
    )

    def _update_uv_object_name(self, context: bpy.types.Context):
        p_act_obj = self.get_active_uv_object(context)
        if p_act_obj and p_act_obj.type == 'MESH':
            if p_act_obj and context.view_layer.objects.active != p_act_obj:
                context.view_layer.objects.active = p_act_obj
                p_act_obj.select_set(True)

    def get_active_uv_object(self, context: bpy.types.Context):
        return context.view_layer.objects.get(self.active_uv_object_name, None)

    active_uv_object_name: bpy.props.StringProperty(
        name='Active UV Object Name',
        update=_update_uv_object_name,
        default=''
    )

    def _update_uv_object(self, context: bpy.types.Context):
        self.active_uv_object_name = self.active_uv_object.name if self.active_uv_object else ''

    active_uv_object: bpy.props.PointerProperty(
        name='Active UV Object',
        type=bpy.types.Object,
        options={'HIDDEN', 'SKIP_SAVE'},
        update=_update_uv_object
    )

    def _get_selected_index(self):
        return self.get('selected_index', -1)

    def _set_selected_index(self, value):
        p_event = get_blender_event(force=True)

        mode = 'ACTIVE'

        b_ctrl = p_event.get('ctrl', False)
        b_shift = p_event.get('shift', False)

        if b_shift and b_ctrl:
            mode = 'TOGGLE_ALL'
        elif b_ctrl:
            mode = 'TOGGLE'
        elif b_shift:
            mode = 'EXTEND'

        self._set_selected_index_by_mode(value, mode)

    def _set_selected_index_by_mode(self, value: str, mode: str):
        try:
            n_count = len(self.uvmaps)
            if n_count > 0:
                if mode == 'ACTIVE':
                    arr_selected = [False] * n_count
                    arr_selected[value] = True
                    self.uvmaps.foreach_set("select", arr_selected)
                    self['selected_index'] = value
                elif mode == 'EXTEND':
                    start_idx = min(max(0, self.get('selected_index', -1)), max(0, value))
                    end_idx = max(max(0, self.get('selected_index', -1)), max(0, value))
                    for idx in range(start_idx, end_idx + 1):
                        self.uvmaps[idx].select = True
                    self['selected_index'] = value
                elif mode == 'TOGGLE':
                    self.uvmaps[value].select = not self.uvmaps[value].select
                    if self.uvmaps[value].select:
                        self['selected_index'] = value
                elif mode == 'TOGGLE_ALL':
                    arr = np.empty(n_count, 'b')
                    self.uvmaps.foreach_get('select', arr)

                    arr.fill(False if arr.all() else True)

                    self.uvmaps.foreach_set('select', arr)

        except Exception as e:
            Log.error('SET UVMAP INDEX:', str(e))

    def _update_selected_index_time_data(self, context: bpy.types.Context):
        p_last_time_data = bpy.app.driver_namespace.get(TimeDataUVMap.literal_id, TimeDataUVMap())  # type: TimeDataUVMap

        if timer() - p_last_time_data.time < 0.3 and self.selected_index == p_last_time_data.idx:
            p_last_time_data.obj = context.active_object
        else:
            p_last_time_data.obj = None
        p_last_time_data.time = timer()
        p_last_time_data.idx = self.selected_index
        bpy.app.driver_namespace[TimeDataUVMap.literal_id] = p_last_time_data

    def _update_selected_index(self, context: bpy.types.Context):
        self._update_selected_index_time_data(context)

        if self.selected_index in range(len(self.uvmaps)):
            p_uv_map = self.uvmaps[self.selected_index]
            for me_group in p_uv_map.mesh_groups:
                me = me_group.get_mesh(context)
                if me:
                    idx = me.uv_layers.find(p_uv_map.name)
                    if idx != -1 and idx != me.uv_layers.active_index:
                        me.uv_layers.active_index = idx

    selected_index: bpy.props.IntProperty(
        name='Selected Object UVS Index',
        default=-1,
        get=_get_selected_index,
        set=_set_selected_index,
        update=_update_selected_index
    )

    def _update_selected_index_active(self, context: bpy.types.Context):
        self._update_selected_index_time_data(context)

        p_act_obj = context.active_object
        if p_act_obj and p_act_obj.type == 'MESH':
            if self.selected_index in range(len(self.uvmaps)):
                p_uv_map = self.uvmaps[self.selected_index]

                me = p_act_obj.data
                idx = me.uv_layers.find(p_uv_map.name)
                if idx != -1 and idx != me.uv_layers.active_index:
                    me.uv_layers.active_index = idx

    selected_index_active: bpy.props.IntProperty(
        name='Selected Object UVS Index',
        default=-1,
        get=_get_selected_index,
        set=_set_selected_index,
        update=_update_selected_index_active
    )

    def _update_selected_index_auto(self, context: bpy.types.Context):
        p_scene_props = context.scene.zen_uv.adv_maps
        if p_scene_props.sync_adv_maps:
            self._update_selected_index(context)
        else:
            self._update_selected_index_active(context)

    selected_index_auto: bpy.props.IntProperty(
        name='Selected Object UVS Index',
        get=_get_selected_index,
        set=_set_selected_index,
        update=_update_selected_index_auto
    )

    def _set_selected_index_for_keymap(self, value):
        mode = 'ACTIVE'

        self._set_selected_index_by_mode(value, mode)

    selected_index_for_keymap: bpy.props.IntProperty(
        name='Selected Object UVS Index For Keymap',
        default=-1,
        get=_get_selected_index,
        set=_set_selected_index_for_keymap,
        update=_update_selected_index
    )

    selected_index_for_keymap_active: bpy.props.IntProperty(
        name='Selected Object UVS Index For Keymap',
        default=-1,
        get=_get_selected_index,
        set=_set_selected_index_for_keymap,
        update=_update_selected_index_active
    )

    def get_active_uvmap(self) -> ZuvUVMapWrapper:
        if self.selected_index in range(len(self.uvmaps)):
            return self.uvmaps[self.selected_index]
        return None

    def get_active_render_uvmap(self) -> ZuvUVMapWrapper:
        for p_uv_map in self.uvmaps:
            if p_uv_map.active_render_ex:
                return p_uv_map
        return None


class ZuvWMDrawGroup(bpy.types.PropertyGroup):
    draw_auto_update: bpy.props.BoolProperty(
        name='Auto Update Draw',
        description='Update draw cache every time when mesh is changed',
        default=True
    )


class ZuvWMTexelDensityGroup(bpy.types.PropertyGroup):
    def get_td_limits(self):
        p_limits = self.get('td_limits', (0.0, 0.0))
        if p_limits[0] > p_limits[1]:
            return p_limits[0], p_limits[0]
        else:
            return p_limits

    def set_td_limits(self, value):
        self['td_limits'] = value

    td_limits: bpy.props.FloatVectorProperty(
        name='Limits',
        description='',
        size=2,
        default=(0.0, 0.0),
        min=0.0,
        soft_min=0.0,
        subtype='COORDINATES',
        get=get_td_limits,
        set=set_td_limits
    )

    td_limits_ui: bpy.props.FloatVectorProperty(
        name='Limits',
        description='',
        size=2,
        default=(0.0, 0.0),
        min=0.0,
        soft_min=0.0,
        subtype='COORDINATES',
        get=get_td_limits,
        set=set_td_limits,
        update=TdProps.update_td_draw_force
    )

    def get_balanced_checker(self):
        return self.get('balanced_checker', 47.59)

    def set_balanced_checker(self, value):
        self['balanced_checker'] = value

    balanced_checker: bpy.props.FloatProperty(
        name='TD Checker',
        description='Texel Density value used for Show TD Balanced method',
        min=0.001,
        get=get_balanced_checker,
        set=set_balanced_checker,
        precision=2
    )

    balanced_checker_ui: bpy.props.FloatProperty(
        name='TD Checker',
        description='Texel Density value used for Show TD Balanced method',
        min=0.001,
        get=get_balanced_checker,
        set=set_balanced_checker,
        precision=2,
        update=TdProps.update_td_draw_force
    )


class ZuvWMTrimsheetLinkedGroup(bpy.types.PropertyGroup):
    def get_image(self):
        for img in bpy.data.images:
            if self.name and img.name_full == self.name:
                return img
        return None

    def get_trimsheet_index(self):
        p_image = self.get_image()
        if p_image:
            return p_image.zen_uv.trimsheet_index_ui
        return -1

    def set_trimsheet_index(self, value):
        p_image = self.get_image()
        if p_image:
            p_image.zen_uv.trimsheet_index_ui = value

    trimsheet_index_ui: bpy.props.IntProperty(
        name="Trimsheet Index",
        min=-1,
        get=get_trimsheet_index,
        set=set_trimsheet_index
    )

    def get_trimsheet_previews(self):
        from .image_props import TrimsheetPreviewUtils
        p_image = self.get_image()
        if p_image:
            return TrimsheetPreviewUtils._get_trimsheet_previews(p_image.zen_uv)

    def set_trimsheet_previews(self, value):
        from .image_props import TrimsheetPreviewUtils
        p_image = self.get_image()
        if p_image:
            TrimsheetPreviewUtils._set_trimsheet_previews(p_image.zen_uv, value)

    def on_zenuv_trimsheet_previews_update(self, context: bpy.types.Context):
        from .image_props import TrimsheetPreviewUtils
        p_image = self.get_image()
        if p_image:
            TrimsheetPreviewUtils._on_zenuv_trimsheet_previews_update(p_image.zen_uv, context)

    def enum_previews_from_directory_items(self, context: bpy.types.Context):
        from ZenUV.ops.trimsheets.trimsheet_preview import preview_collections, ZuvTrimPreviewer
        enum_items = []

        p_image = self.get_image()
        if p_image is not None:
            if p_image.name not in preview_collections:
                preview_collections[p_image.name] = ZuvTrimPreviewer()

            p_preview = preview_collections[p_image.name]
            n_trim_count = len(p_image.zen_uv.trimsheet)
            # NOTE: this is very fast comparison, more deep is in 'update_preview'
            if p_preview.enum_previews is None or n_trim_count != len(p_preview.enum_previews):
                p_preview.collect_previews(p_image)

            return p_preview.enum_previews

        return enum_items

    trimsheet_previews: bpy.props.EnumProperty(
        name='Trimsheet Previews',
        items=enum_previews_from_directory_items,
        get=get_trimsheet_previews,
        set=set_trimsheet_previews,
        update=on_zenuv_trimsheet_previews_update)

    def get_use_fit_to_trim(self):
        p_image = self.get_image()
        if p_image:
            return p_image.zen_uv.use_fit_to_trim
        return False

    def set_use_fit_to_trim(self, value):
        p_image = self.get_image()
        if p_image:
            p_image.zen_uv.use_fit_to_trim = value

    use_fit_to_trim: bpy.props.BoolProperty(
        name="Auto Fit",
        description="Execute fit to trim operation after trim is selected in preview",
        get=get_use_fit_to_trim,
        set=set_use_fit_to_trim
    )


class ZUV_WMProps(bpy.types.PropertyGroup):
    obj_uvs: bpy.props.PointerProperty(
        type=ZuvObjUVGroup
    )

    draw_props: bpy.props.PointerProperty(
        type=ZuvWMDrawGroup
    )

    td_props: bpy.props.PointerProperty(
        type=ZuvWMTexelDensityGroup
    )

    trimsheet_linked_overrides: bpy.props.CollectionProperty(
        type=ZuvWMTrimsheetLinkedGroup
    )
