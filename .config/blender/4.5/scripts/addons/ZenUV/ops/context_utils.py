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

from ZenUV.utils.blender_zen_utils import update_areas_in_all_screens, ZenPolls
from ZenUV.prop.zuv_preferences import get_prefs


class FakeContext:
    def __init__(self, d: dict = None):
        if d is not None:
            for key, value in d.items():
                setattr(self, key, value)


class ZUV_OT_UpdateToggle(bpy.types.Operator):
    bl_idname = 'wm.zenuv_update_toggle'
    bl_label = 'Toggle Value'
    bl_description = 'Toggles value with updating viewports'
    bl_options = {'INTERNAL'}

    data_path: bpy.props.StringProperty(
        name='Data Path',
        default='',
        options={'HIDDEN', 'SKIP_SAVE'}
    )

    def execute(self, context: bpy.types.Context):
        bpy.ops.wm.context_toggle('INVOKE_DEFAULT', data_path=self.data_path)
        update_areas_in_all_screens(context)
        return {'FINISHED'}


class ZUV_OT_ScriptExec(bpy.types.Operator):
    bl_idname = 'wm.zenuv_script_exec'
    bl_label = 'Exec Script'
    bl_description = ''
    bl_options = {'INTERNAL'}

    script: bpy.props.StringProperty(
        name="Script",
        description="Must be valid python script code in 1 line",
        options={"SKIP_SAVE"})
    desc: bpy.props.StringProperty(
        name="Description",
        description="Operator description in UI",
        options={"SKIP_SAVE"})
    return_value: bpy.props.StringProperty(
        name='Return Value',
        description='Operator return value. Use "PASS_THROUGH" if you would like to run other operator',
        default="{'FINISHED'}",
        options={"SKIP_SAVE"}
    )
    redraw_areas: bpy.props.BoolProperty(
        name='Redraw Areas',
        description='Redraw all UV, View3D areas after execution',
        default=True,
        options={"SKIP_SAVE"}
    )

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        return properties.desc if properties else ''

    def execute(self, context: bpy.types.Context):

        # CONVINIENCE IMPORTS
        import mathutils  # noqa
        import math       # noqa

        # CONVINIENCE VARIABLES
        C, D, P = context, bpy.data, get_prefs()  # noqa

        exec(self.script)

        if self.redraw_areas:
            update_areas_in_all_screens(context)

        t_res = eval(self.return_value)

        if 'FINISHED' in t_res:
            bpy.ops.ed.undo_push(message=self.desc if self.desc else self.bl_idname)

        return t_res


class ZUV_OT_TextExec(bpy.types.Operator):
    bl_idname = 'wm.zenuv_text_exec'
    bl_label = 'Exec Text'
    bl_description = ''
    bl_options = {'INTERNAL'}

    script: bpy.props.StringProperty(
        name="Script Text",
        description="Name of the valid script text datablock",
        options={"SKIP_SAVE"})
    desc: bpy.props.StringProperty(
        name="Description",
        description="Operator description in UI",
        options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context: bpy.types.Context, properties: bpy.types.OperatorProperties):
        return properties.desc if properties else ''

    def execute(self, context: bpy.types.Context):
        try:
            p_text = bpy.data.texts.get(self.script, None)
            if p_text is None:
                raise RuntimeError(f"Can not find - {self.script}")

            ctx_override = context.copy()
            ctx_override['edit_text'] = p_text

            if ZenPolls.version_since_3_2_0:
                with bpy.context.temp_override(**ctx_override):
                    bpy.ops.text.run_script()
            else:
                bpy.ops.text.run_script(ctx_override)

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))

        return {'CANCELLED'}


context_utils_classes = (
    ZUV_OT_UpdateToggle,
    ZUV_OT_ScriptExec,
    ZUV_OT_TextExec
)
