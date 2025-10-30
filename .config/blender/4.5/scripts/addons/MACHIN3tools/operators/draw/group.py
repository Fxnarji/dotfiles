import bpy
from bpy.props import FloatProperty

from mathutils import Vector

from ... utils.draw import draw_label, draw_mesh_wire, draw_points
from ... utils.registration import get_prefs
from ... utils.ui import finish_modal_handlers, get_scale, init_modal_handlers, set_countdown, get_timer_progress
from ... colors import yellow, red

class DrawUnGroupable(bpy.types.Operator):
    bl_idname = "machin3.draw_ungroupable"
    bl_label = "MACHIN3: Draw Ungroupable"
    bl_options = {'INTERNAL'}

    time: FloatProperty(name="Time (s)", default=1)
    alpha: FloatProperty(name="Alpha", default=1, min=0.1, max=1)
    def draw_HUD(self, context):
        if context.area == self.area:
            scale = get_scale(context)
            alpha = get_timer_progress(self) * self.alpha

            for loc2d, _ in self.batches:
                draw_label(context, title="Ungroupable", coords=loc2d - Vector((0, 36 * scale)), color=yellow, alpha=alpha)
                draw_label(context, title="Object is parented", coords=loc2d - Vector((0, 54 * scale)), alpha=alpha / 2)

    def draw_VIEW3D(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self) * self.alpha * 0.5

            for _, batch in self.batches:
                draw_mesh_wire(batch, color=yellow, alpha=alpha)

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        else:
            self.finish(context)
            return {'CANCELLED'}

        if self.countdown < 0:
            self.finish(context)
            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        return {'PASS_THROUGH'}

    def finish(self, context):
        finish_modal_handlers(self)

    def execute(self, context):
        from .. group import ungroupable_batches
        self.batches = ungroupable_batches

        self.time = get_prefs().HUD_fade_group * 3

        init_modal_handlers(self, context, hud=True, view3d=True, timer=True, time_step=0.01)
        return {'RUNNING_MODAL'}

class DrawUnGroup(bpy.types.Operator):
    bl_idname = "machin3.draw_ungroup"
    bl_label = "MACHIN3: Draw Ungroup"
    bl_options = {'INTERNAL'}

    time: FloatProperty(name="Time (s)", default=1)
    alpha: FloatProperty(name="Alpha", default=1, min=0.1, max=1)
    def draw_VIEW3D(self, context):
        if context.area == self.area:
            alpha = get_timer_progress(self) * self.alpha * 0.5

            if self.locations:
                draw_points(self.locations, color=red, size=10, alpha=alpha)

            for batch in self.batches:
                draw_mesh_wire(batch, color=red, alpha=alpha)

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        else:
            self.finish(context)
            return {'CANCELLED'}

        if self.countdown < 0:
            self.finish(context)
            return {'FINISHED'}

        if event.type == 'TIMER':
            set_countdown(self)

        return {'PASS_THROUGH'}

    def finish(self, context):
        finish_modal_handlers(self)

    def execute(self, context):
        from .. group import ungrouped_child_locations, ungrouped_child_batches

        self.batches = ungrouped_child_batches
        self.locations = ungrouped_child_locations

        self.time = get_prefs().HUD_fade_group * 2

        init_modal_handlers(self, context, view3d=True, timer=True, time_step=0.01)
        return {'RUNNING_MODAL'}
