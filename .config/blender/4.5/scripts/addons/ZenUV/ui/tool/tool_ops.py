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
from mathutils import Vector, Matrix

from timeit import default_timer as timer
import re

from ZenUV.utils.constants import UV_AREA_BBOX
from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens, rsetattr
from ZenUV.utils.vlog import Log
from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
from ZenUV.prop.scene_ui_props import ZUV_UVToolProps


class ZUV_OT_ToolTrimHandle(bpy.types.Operator):
    bl_idname = 'zenuv.tool_trim_handle'
    bl_label = 'Align|Fit|Flip Trims'
    bl_options = {'INTERNAL'}

    direction: bpy.props.StringProperty(
        name='Handle Direction',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('ALIGN', 'Align', ''),
            ('FIT', 'Fit', ''),
            ('FLIP', 'Flip', ''),
            ('ROTATE', 'Rotate', ''),
            ('ORIENT', 'Orient', ''),

            ('PIVOT', 'Island Pivot', ''),
            ('UNWRAP', 'Unwrap', ''),
            ('WORLD_ORIENT', 'World Orient', ''),
            ('SELECT_BY_FACE', 'Trim By Face', 'Trim select by active face'),
        ],
        default='ALIGN',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    pivot_prop: bpy.props.StringProperty(
        name='Pivot Property',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def __init__(self) -> None:
        self._timer = None
        self._last_click = 0

    def cancel(self, context: bpy.types.Context):
        if self._timer is not None:
            wm = context.window_manager
            wm.event_timer_remove(self._timer)
            self._timer = None
        self._last_click = 0

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        if properties:
            from ZenUV.ops.transform_sys.trim_depend_transform import (
                ZUV_OT_TrAlignToTrim,
                ZUV_OT_TrFlipInTrim,
                ZUV_OT_TrFitToTrim
            )

            from ZenUV.ops.transform_sys.tr_rotate import (
                ZUV_OT_TrRotate3DV
            )

            s_out = [
                ZUV_OT_TrAlignToTrim.bl_description,
                ' * Ctrl - ' + ZUV_OT_TrRotate3DV.bl_description,
                ' * Shift - ' + ZUV_OT_TrFitToTrim.bl_description,
                ' * Ctrl+Shift - ' + ZUV_OT_TrFlipInTrim.bl_description
            ]

            s_double = ['-----------------------']
            if properties.pivot_prop:
                s_double.append(
                    ' * Double Click - Set Transform Pivot'
                )
            if properties.direction == 'cen':
                s_double.append(
                    ' * Double Click+Shift - Unwrap'
                )
                s_double.append(
                    ' * Double Click+Ctrl - World Orient'
                )
                s_double.append(
                    ' * Double Click+Ctrl+Shift - Trim by Face'
                )

            if len(s_double) > 1:
                s_out += s_double

            return '\n'.join(s_out)
        else:
            return cls.bl_description

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        if self._timer is None:
            return {'CANCELLED'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.cancel(context)

            if self.mode == 'FIT':
                self.mode = 'UNWRAP'
                return self.execute(context)
            elif self.mode in {'ROTATE', 'ORIENT'}:
                self.mode = 'WORLD_ORIENT'
                return self.execute(context)
            elif self.mode == 'FLIP':
                self.mode = 'SELECT_BY_FACE'
                return self.execute(context)
            elif self.pivot_prop:
                self.mode = 'PIVOT'
                return self.execute(context)

            return {'CANCELLED'}

        if timer() - self._last_click > 0.3:
            self.cancel(context)
            return self.execute(context)

        return {'RUNNING_MODAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        if self._timer is not None:
            return {'CANCELLED'}

        self.mode = 'ALIGN'
        if event.ctrl and event.shift:
            self.mode = 'FLIP'
        elif event.ctrl:
            self.mode = (
                'ROTATE' if self.direction in UV_AREA_BBOX.bbox_corner_handles else
                'ORIENT')
        elif event.shift:
            self.mode = 'FIT'

        if self.pivot_prop or ((event.ctrl or event.shift) and self.direction == 'cen'):
            wm = context.window_manager
            wm.modal_handler_add(self)

            self._timer = wm.event_timer_add(0.1, window=context.window)
            self._last_click = timer()

            return {'RUNNING_MODAL'}
        else:
            return self.execute(context)

    def execute(self, context: bpy.types.Context):
        try:
            def handle_failed_poll(op_mod):
                op_cls = bpy.types.Operator.bl_rna_get_subclass_py(op_mod.idname())
                s_reason = op_cls.poll_reason(context)
                if s_reason:
                    raise RuntimeError(s_reason)

            if self.mode == 'ALIGN':
                op_mod = bpy.ops.uv.zenuv_align_to_trim
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True,
                        align_direction=self.direction,
                        island_pivot=self.direction,
                        i_pivot_as_direction=True,
                        )
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'ROTATE':
                if self.direction in UV_AREA_BBOX.bbox_not_bottom_left:
                    angle = 90
                if self.direction == UV_AREA_BBOX.bbox_bottom_left:
                    angle = -90
                op_mod = bpy.ops.view3d.zenuv_rotate
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True,
                        rotation_mode='ANGLE',
                        tr_rot_inc_full_range=angle)
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'ORIENT':
                if self.direction in UV_AREA_BBOX.bbox_horizontal_handles:
                    orient_dir = 'HORIZONTAL'
                elif self.direction in UV_AREA_BBOX.bbox_vertical_handles:
                    orient_dir = "VERTICAL"
                elif self.direction == 'cen':
                    orient_dir = "AUTO"
                op_mod = bpy.ops.uv.zenuv_orient_island
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT',
                        mode='BBOX',
                        orient_direction=orient_dir,
                        rotate_direction='CW')
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'FIT':
                op_mod = bpy.ops.uv.zenuv_fit_to_trim
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True,
                        op_align_to=self.direction,
                        )
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'FLIP':
                op_mod = bpy.ops.uv.zenuv_flip_in_trim
                if op_mod.poll():
                    return bpy.ops.uv.zenuv_flip_in_trim(
                        'INVOKE_DEFAULT', True,
                        direction=self.direction)
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'PIVOT':
                if self.pivot_prop:
                    p_scene = context.scene
                    rsetattr(p_scene, self.pivot_prop, self.direction)
                    context.area.tag_redraw()
            elif self.mode == 'UNWRAP':
                op_mod = bpy.ops.uv.zenuv_unwrap_for_tool
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True)
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'WORLD_ORIENT':
                op_mod = bpy.ops.uv.zenuv_world_orient
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True)
                else:
                    handle_failed_poll(op_mod)
            elif self.mode == 'SELECT_BY_FACE':
                op_mod = bpy.ops.uv.zenuv_trim_select_by_face
                if op_mod.poll():
                    return op_mod(
                        'INVOKE_DEFAULT', True)
                else:
                    handle_failed_poll(op_mod)
            return {'FINISHED'}

        except Exception as e:
            self.report({'WARNING'}, str(e))

        return {'CANCELLED'}


class ZUV_OT_ToolAreaUpdate(bpy.types.Operator):
    bl_idname = 'zenuv.tool_area_update'
    bl_label = 'Update UV and 3D Areas'
    bl_description = 'Internal Zen UV tool operator to update UV and 3D areas by hotkeys'
    bl_options = {'INTERNAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        bpy.ops.wm.zuv_event_service('INVOKE_DEFAULT')
        update_areas_in_all_screens(context)
        return {'PASS_THROUGH'}  # NEVER CHANGE THIS !


class ZUV_OT_ToolExitCreate(bpy.types.Operator):
    bl_idname = 'zenuv.tool_exit_create'
    bl_label = 'Exit Create Mode'
    bl_description = 'Exit Zen Uv tool create trims mode'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        return p_scene.zen_uv.ui.uv_tool.trim_mode == 'CREATE'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_scene = context.scene
        p_scene.zen_uv.ui.uv_tool.trim_mode = 'RESIZE'
        return {'PASS_THROUGH'}  # NEVER CHANGE THIS !


class ZUV_OT_TrimScrollFit(bpy.types.Operator):
    bl_idname = 'wm.zenuv_trim_scroll_fit'
    bl_label = 'Scroll Fit To Trim'
    bl_description = 'Scroll active trim forward-backward and fit island(s) to it'
    bl_options = {'REGISTER', 'UNDO'}

    is_up: bpy.props.BoolProperty(
        name="Scroll Up",
        description="Scroll to beginning of the trimsheet",
        default=False
    )

    filter: bpy.props.StringProperty(
        name="Filter",
        description="Comma separeted list of partial or full filter by trim name",
        default=""
    )

    # NOTE: this property is required to fight bug:
    # https://projects.blender.org/blender/blender/issues/125901
    influence_mode: bpy.props.EnumProperty(
        name='Mode',
        description="Transform Mode",
        items=[
            ("ISLAND", "Islands", "Transform islands mode", 'UV_ISLANDSEL', 0),
            ("SELECTION", "Selection", "Transform selection (uv, mesh) mode", 'UV_FACESEL', 1),
        ],
    )

    LITERAL_CATEGORIES = "_trimsheet_categories"
    LITERAL_CATEGORIES_SET = "_trimsheet_categories_set"
    LITERAL_TRIM_NOT_CHANGED = "Active trim not changed!"

    def get_categories_items(self, context: bpy.types.Context):
        items = {}

        p_trimsheet = ZuvTrimsheetUtils.getTrimsheet(context)
        if p_trimsheet:
            pattern = r'[^_\.\d\s]+'
            i_count = 0
            for trim in p_trimsheet:
                match = re.search(pattern, trim.name)
                if match:
                    s_category = match.group()
                    if s_category not in items:
                        items[s_category] = ((s_category, s_category, "", "NONE", 2**len(items)))
                        i_count += 1
                        if i_count >= 31:
                            # NOTE: 32 is limitation of set
                            break

        were_items = bpy.app.driver_namespace.get(ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES, [])
        p_list = list(items.values())
        if were_items != p_list:
            bpy.app.driver_namespace[ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES] = p_list
            return bpy.app.driver_namespace[ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES]
        else:
            return were_items

    def get_trimsheet_categories(self):
        were_items = bpy.app.driver_namespace.get(ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES, [])
        t_items = {item[0].lower(): idx for idx, item in enumerate(were_items)}
        t_cats = self.filter.split(",")
        value = 0
        for cat in t_cats:
            cat = cat.strip().lower()
            if cat in t_items:
                value = value | (1 << t_items[cat])
        return value

    def set_trimsheet_categories(self, value):
        t_items = []
        were_items = bpy.app.driver_namespace.get(ZUV_OT_TrimScrollFit.LITERAL_CATEGORIES, [])
        for idx, item in enumerate(were_items):
            if value & (1 << idx):
                t_items.append(item[0])
        self.filter = ", ".join(t_items)

    trimsheet_categories: bpy.props.EnumProperty(
        name="Categories",
        description="Categories that are created from trim names",
        items=get_categories_items,
        get=get_trimsheet_categories,
        set=set_trimsheet_categories,
        options={'ENUM_FLAG', 'HIDDEN', 'SKIP_SAVE'},
    )

    warning_message: bpy.props.StringProperty(
        name="Warning",
        description="Warning message",
        default=""
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        # NOTE: Do not change poll to be able to change scroll increment
        return True

    def draw(self, context: bpy.types.Context):
        layout = self.layout

        if self.warning_message:
            box = layout.box()
            box.alert = True
            box.label(text=self.warning_message, icon='ERROR')

        row = layout.row(align=True)
        row.alert = self.warning_message == self.LITERAL_TRIM_NOT_CHANGED
        row.prop(self, "filter")
        row.prop_menu_enum(self, "trimsheet_categories", text="", icon="TRIA_DOWN")

        from ZenUV.ops.transform_sys.trim_depend_transform import ZUV_OT_TrFitToTrim
        wm = context.window_manager
        op_props = wm.operator_properties_last(ZUV_OT_TrFitToTrim.bl_idname)
        if op_props:
            p_influence_instance = self
            p_instance = op_props
            ZUV_OT_TrFitToTrim.do_draw(p_influence_instance, p_instance, self.layout, context)

    def is_interrupted(self, p_trim, context: bpy.types.Context):
        if self.filter:
            t_cats = self.filter.split(",")
            return any(cat.strip().lower() in p_trim.name.lower() for cat in t_cats)

        return True

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.warning_message = ""
        p_trim_owner = ZuvTrimsheetUtils.getTrimsheetOwner(context)
        if p_trim_owner:
            idx = p_trim_owner.trimsheet_index
            p_trimsheet = p_trim_owner.trimsheet

            n_count = len(p_trimsheet)
            if n_count > 1:
                new_idx = idx

                if self.is_up:
                    for _ in range(n_count):
                        new_idx = new_idx + 1
                        if new_idx >= n_count:
                            new_idx = 0

                        if self.is_interrupted(p_trimsheet[new_idx], context):
                            break
                else:
                    for _ in range(n_count):
                        new_idx = new_idx - 1
                        if new_idx < 0:
                            new_idx = n_count - 1

                        if self.is_interrupted(p_trimsheet[new_idx], context):
                            break

                if new_idx != idx:
                    bpy.ops.wm.zuv_trim_set_index(trimsheet_index=new_idx)
                    self.influence_mode = context.scene.zen_uv.tr_type
                    return self.execute(context)
                else:
                    self.warning_message = self.LITERAL_TRIM_NOT_CHANGED
                    self.report({'INFO'}, self.warning_message)
                    return {'FINISHED'}  # NOTE: Do not change return value !!!
        return {'CANCELLED'}

    def execute(self, context: bpy.types.Context):
        if bpy.ops.uv.zenuv_fit_to_trim.poll():
            wm = context.window_manager
            op_props = wm.operator_properties_last("uv.zenuv_fit_to_trim")
            if op_props:
                props = op_props.bl_rna.properties
                keys = set(props.keys()) - {'rna_type'}
                t_kwargs = dict()
                for k in keys:
                    t_kwargs[k] = getattr(op_props, k)
                    if k == 'influence_mode':
                        t_kwargs[k] = self.influence_mode

                res = bpy.ops.uv.zenuv_fit_to_trim('INVOKE_DEFAULT', True, **t_kwargs)
                context.area.tag_redraw()
                return res

        return {'CANCELLED'}


# NOTE: we create this internal class to avoid this issue:
# https://projects.blender.org/blender/blender/issues/125901
class ZUV_OT_TrimScrollFitInternal(bpy.types.Operator):
    bl_idname = 'wm.zenuv_trim_scroll_fit_internal'
    bl_label = ZUV_OT_TrimScrollFit.bl_label
    bl_description = ZUV_OT_TrimScrollFit.bl_description
    bl_options = {'INTERNAL'}

    is_up: bpy.props.BoolProperty(
        name="Scroll Up",
        description="Scroll to beginning of the trimsheet",
        default=False
    )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        bpy.ops.wm.zenuv_trim_scroll_fit('INVOKE_DEFAULT', True, is_up=self.is_up)
        return {'PASS_THROUGH'}


class ZUV_OT_ToolScreenZoom(bpy.types.Operator):
    bl_idname = 'view3d.tool_screen_zoom'
    bl_label = 'Screen Select Scale'
    bl_description = 'Scale view3d tool in screen select mode'
    bl_options = {'INTERNAL'}

    is_up: bpy.props.BoolProperty(
        default=False
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        return p_scene.zen_uv.ui.view3d_tool.is_screen_selector_position_enabled()

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_scene = context.scene
        p_scene.zen_uv.ui.view3d_tool.screen_scale += (0.1 if self.is_up else -0.1)
        context.area.tag_redraw()
        return {'FINISHED'}


class ZUV_OT_ToolScreenPan(bpy.types.Operator):
    bl_idname = 'view3d.tool_screen_pan'
    bl_label = 'Screen Select Pan'
    bl_description = 'Pan view3d tool in screen select mode'
    bl_options = {'INTERNAL'}

    def __init__(self) -> None:
        self.init_mouse = Vector((0, 0))
        self.init_value = Vector((0, 0))

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        return p_scene.zen_uv.ui.view3d_tool.is_screen_selector_position_enabled()

    def modal(self, context: bpy.types.Context, event: bpy.types.Event):
        if event.value == 'RELEASE' or event.type in {'LEFTMOUSE', 'RIGHTMOUSE', 'ESC'}:
            return {'CANCELLED'}

        delta = self.init_mouse - Vector((event.mouse_x, event.mouse_y))

        p_scene = context.scene

        value = self.init_value - delta

        p_scene.zen_uv.ui.view3d_tool.screen_pan_x = value.x
        p_scene.zen_uv.ui.view3d_tool.screen_pan_y = value.y

        context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.init_mouse = Vector((event.mouse_x, event.mouse_y))

        wm = context.window_manager
        p_scene = context.scene

        self.init_value = Vector((
            p_scene.zen_uv.ui.view3d_tool.screen_pan_x,
            p_scene.zen_uv.ui.view3d_tool.screen_pan_y
        ))

        wm.modal_handler_add(self)

        return {'RUNNING_MODAL'}


class ZUV_OT_ToolScreenReset(bpy.types.Operator):
    bl_idname = 'view3d.tool_screen_reset'
    bl_label = 'Screen Select Reset'
    bl_description = 'Reset scale and pan view3d tool in screen select mode'
    bl_options = {'INTERNAL'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('RESET', 'Reset', ''),
            ('CENTER', 'Center in view', '')
        ],
        default='RESET'
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        p_scene = context.scene
        tool_props = p_scene.zen_uv.ui.view3d_tool
        return tool_props.is_screen_selector_position_enabled()

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_scene = context.scene
        p_tool_props = p_scene.zen_uv.ui.view3d_tool

        p_trim_data = ZuvTrimsheetUtils.getActiveTrimData(context)

        if self.mode == 'RESET' or p_trim_data is None:
            p_tool_props.screen_scale = 1.0
            p_tool_props.screen_pan_x = 0.0
            p_tool_props.screen_pan_y = 0.0
        else:
            v_scr_cen = Vector(p_tool_props.screen_pos)
            v_scr_pan = Vector((p_tool_props.screen_pan_x, p_tool_props.screen_pan_y))
            d_rect_length = p_tool_props.screen_size

            v_scr = v_scr_cen - v_scr_pan
            v_start = v_scr - Vector((d_rect_length / 2, d_rect_length / 2))

            _, p_trim, p_trimsheet = p_trim_data
            bounds = ZuvTrimsheetUtils.getTrimsheetBounds(p_trimsheet)

            v_cen = Vector(p_trim.get_center()).to_3d()

            d_trimsheet_size = max(max(bounds.width, bounds.height), 1.0)
            d_trimsheet_size_ratio = 1.0 / d_trimsheet_size

            d_size = max(p_trim.width, p_trim.height) * 2.0 * d_trimsheet_size_ratio
            was_scale = p_tool_props.screen_scale

            if d_size != 0 and was_scale != 0:
                p_tool_props.screen_scale = 1 / d_size
                sca_diff = p_tool_props.screen_scale / was_scale
            else:
                sca_diff = 1.0

            mtx_pos = Matrix.Translation(v_start.resized(3))
            mtx_sca = Matrix.Diagonal((d_rect_length, d_rect_length, 1.0)).to_4x4()
            mtx = mtx_pos @ mtx_sca
            v_cen = mtx @ v_cen

            p_tool_props.screen_pan_x = (v_scr.x - v_cen.x) * sca_diff
            p_tool_props.screen_pan_y = (v_scr.y - v_cen.y) * sca_diff

        context.area.tag_redraw()
        return {'FINISHED'}


class ZUV_OT_ToolScreenSelector(bpy.types.Operator):
    bl_idname = 'view3d.tool_screen_selector'
    bl_label = 'Trim Screen Selector'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            p_scene = context.scene
            t_out = ['Show screen viewport trim selector']
            if p_scene.zen_uv.ui.view3d_tool.enable_screen_selector:
                s_locked = "Unlock" if p_scene.zen_uv.ui.view3d_tool.screen_position_locked else "Lock"
                t_out.append(f'* Shift+Click - {s_locked} screen selector position')
                if p_scene.zen_uv.ui.view3d_tool.screen_position_locked:
                    t_out.append("   to be able to move widget by hotkeys")
            return '\n'.join(t_out)
        else:
            return cls.bl_description

    mode: bpy.props.EnumProperty(
        name='Mode',
        items=[
            ('DEFAULT', 'Default', ''),
            ('LOCK', 'Lock', '')
        ],
        default='DEFAULT',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    @classmethod
    def poll(cls, context: bpy.types.Context):
        return True

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.mode = 'DEFAULT'
        p_scene = context.scene
        if p_scene.zen_uv.ui.view3d_tool.enable_screen_selector:
            if event.shift:
                self.mode = 'LOCK'
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        p_scene = context.scene
        if self.mode == 'DEFAULT':
            p_scene.zen_uv.ui.view3d_tool.enable_screen_selector = not p_scene.zen_uv.ui.view3d_tool.enable_screen_selector
        elif self.mode == 'LOCK':
            p_scene.zen_uv.ui.view3d_tool.screen_position_locked = not p_scene.zen_uv.ui.view3d_tool.screen_position_locked

        context.area.tag_redraw()

        return {'FINISHED'}


class ZUV_OT_TrimActivateTool(bpy.types.Operator):
    bl_idname = "uv.zuv_activate_tool"
    bl_label = "Zen UV Tool"
    bl_description = 'Activate Zen UV tool'  # Is used for Pie
    bl_option = {'REGISTER'}

    mode: bpy.props.EnumProperty(
        name='Mode',
        description='Trim sheets data mode',
        items=[
            ('OFF', 'Off', ''),
            ('RESIZE', 'Resize', ''),
            ('CREATE', 'Create', ''),
            ('ACTIVATE', 'Activate', '')
        ],
        default='OFF'
    )

    prev_tool: bpy.props.StringProperty(
        name='Previous Tool',
        default=''
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties) -> str:
        if properties:
            if properties.mode == 'RESIZE':
                return "Activate Tool in Resize Trims mode"
            if properties.mode == 'CREATE':
                return "Activate Tool in Create Trims mode"
            if properties.mode == 'ACTIVATE':
                return "Activate Tool"

            return "Deactivate Tool"
        else:
            return cls.bl_description

    def set_uv_prev_tool(self, context: bpy.types.Context):
        _id_UV = getattr(context.workspace.tools.from_space_image_mode('UV', create=False), 'idname', None)
        if isinstance(_id_UV, str):
            self.prev_tool = _id_UV

    def execute(self, context: bpy.types.Context):
        if self.mode == 'CREATE':
            self.set_uv_prev_tool(context)

            bpy.context.scene.zen_uv.ui.uv_tool.category = 'TRIMS'
            bpy.context.scene.zen_uv.ui.uv_tool.trim_mode = 'CREATE'
            bpy.ops.wm.tool_set_by_id(name="zenuv.uv_tool")

        elif self.mode == 'RESIZE':
            self.set_uv_prev_tool(context)

            bpy.context.scene.zen_uv.ui.uv_tool.category = 'TRIMS'
            bpy.context.scene.zen_uv.ui.uv_tool.trim_mode = 'RESIZE'
            bpy.ops.wm.tool_set_by_id(name="zenuv.uv_tool")
        elif self.mode == 'ACTIVATE':
            self.prev_tool = ''
            if context.area.type == 'IMAGE_EDITOR':
                bpy.ops.wm.tool_set_by_id(name="zenuv.uv_tool")
            elif context.area.type == 'VIEW_3D':
                bpy.ops.wm.tool_set_by_id(name="zenuv.view3d_tool")
        else:
            bpy.context.scene.zen_uv.ui.uv_tool.category = 'TRANSFORMS'

            if self.prev_tool:
                try:
                    bpy.ops.wm.tool_set_by_id(name=self.prev_tool)
                except Exception as e:
                    Log.error('DEACTIVATE TOOL:', str(e))

        return {'FINISHED'}


class ZUV_OT_ToolSnapHandle(bpy.types.Operator):
    bl_idname = 'zenuv.tool_snap_handle'
    bl_label = 'Snap Pivot'
    bl_description = 'Click to change snap pivot'
    bl_options = {'INTERNAL'}

    direction: bpy.props.StringProperty(
        name='Handle Direction',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def execute(self, context: bpy.types.Context):
        p_scene = context.scene
        p_tool_props: ZUV_UVToolProps = p_scene.zen_uv.ui.uv_tool
        p_tool_props.trim_snap_pivot = self.direction
        context.area.tag_redraw()
        return {'FINISHED'}
