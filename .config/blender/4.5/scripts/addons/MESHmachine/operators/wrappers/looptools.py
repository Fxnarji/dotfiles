import bpy
import bmesh
from bpy.props import BoolProperty, FloatProperty, EnumProperty
from mathutils import Vector

from ... utils.developer import output_traceback
from ... utils.draw import draw_point
from ... utils.math import average_locations, get_irregular_circle_center
from ... utils.property import step_enum
from ... utils.selection import get_boundary_edges, get_edge_selection_islands
from ... utils.ui import draw_init, draw_title, draw_prop, init_cursor, wrap_cursor, get_zoom_factor, update_HUD_location
from ... utils.ui import init_status, finish_status

from ... colors import yellow, red
from ... items import looptools_circle_method, looptools_relax_input_items, looptools_relax_interpolation_items, looptools_relax_iterations_items

class LoopToolsCircle(bpy.types.Operator):
    bl_idname = "machin3.looptools_circle"
    bl_label = "MACHIN3: LoopTools Circle"
    bl_description = "LoopTools' Circle as a modal"
    bl_options = {'REGISTER', 'UNDO'}

    method: EnumProperty(name="Method", items=looptools_circle_method, default='best')
    influence: FloatProperty(name="Influence", description="Force of the tool", default=100.0, min=0.0, max=100.0, precision=1, subtype='PERCENTAGE')
    flatten: BoolProperty(name="Flatten", description="Flatten the circle, instead of projecting it on the mesh", default=True)
    regular: BoolProperty(name="Regular", description="Distribute vertices at constant distances along the circle", default=True)
    use_custom_radius: BoolProperty(name="Radius", description="Force a custom radius", default=False)
    radius: FloatProperty(name="Radius", description="Custom radius for circle", default=1.0, min=0.0, soft_max=1000.0)
    lock_x: BoolProperty(name="Lock X", description="Lock editing of the x-coordinate", default=False)
    lock_y: BoolProperty(name="Lock Y", description="Lock editing of the y-coordinate", default=False)
    lock_z: BoolProperty(name="Lock Z", description="Lock editing of the z-coordinate", default=False)
    fix_midpoint: BoolProperty(name="Fix Midpoint", default=False)
    passthrough: BoolProperty(default=False)
    allowmodalradius: BoolProperty(default=False)
    allowmodalinfluence: BoolProperty(default=False)
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Circle", subtitle="LoopTools")

            draw_prop(self, "Method", self.method, hint="scroll UP/DOWN")
            self.offset += 10

            draw_prop(self, "Flatten", self.flatten, offset=18, hint="toggle F")
            draw_prop(self, "Regular", self.regular, offset=18, hint="toggle R")
            self.offset += 10

            draw_prop(self, "Custom Radius", self.use_custom_radius, offset=18, hint="toggle C")
            draw_prop(self, "Radius", self.radius, offset=18, active=self.allowmodalradius, hint="move LEFT/RIGHT, toggle W, reset ALT + W")
            self.offset += 10

            draw_prop(self, "Influence", self.influence, offset=18, active=self.allowmodalinfluence, hint="move UP/DOWN, toggle Q, reset ALT + Q")
            self.offset += 10

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == "MOUSEMOVE":
            wrap_cursor(self, context, event)
            update_HUD_location(self, event)

        events = ['WHEELUPMOUSE', 'ONE', 'WHEELDOWNMOUSE', 'TWO', 'C', 'W', 'I', 'Q', 'F', 'R']

        if any([self.allowmodalradius, self.allowmodalinfluence]):
            events.append('MOUSEMOVE')

        if event.type in events:
            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.passthrough = False

                else:
                    if self.allowmodalradius:
                        divisor = 100 if event.shift else 1 if event.ctrl else 10

                        delta_x = event.mouse_x - self.last_mouse_x
                        delta_radius = delta_x / divisor * self.factor

                        self.radius += delta_radius

                    if self.allowmodalinfluence:
                        divisor = 10 if event.shift else 0.1 if event.ctrl else 1

                        delta_y = event.mouse_y - self.last_mouse_y
                        delta_influence = delta_y / divisor

                        self.influence += delta_influence

                    try:
                        ret = self.circle(context, self.active)

                        if not ret:
                            self.finish()
                            return {'FINISHED'}

                    except Exception as e:
                        self.finish()

                        if bpy.context.mode == 'OBJECT':
                            bpy.ops.object.mode_set(mode='EDIT')

                        output_traceback(self, e)
                        return {'FINISHED'}

            elif event.value == 'PRESS':

                if event.type in {'WHEELUPMOUSE', 'ONE'}:
                    self.method = step_enum(self.method, looptools_circle_method, 1)

                elif event.type in {'WHEELDOWNMOUSE', 'TWO'}:
                    self.method = step_enum(self.method, looptools_circle_method, -1)

                elif event.type == 'C':
                    self.use_custom_radius = not self.use_custom_radius

                elif event.type == 'W':
                    if event.alt:
                        self.allowmodalradius = False
                        self.radius = 1
                    else:
                        self.allowmodalradius = not self.allowmodalradius
                        if not self.use_custom_radius:
                            self.use_custom_radius = True

                elif event.type in ['I', 'Q']:
                    if event.alt:
                        self.allowmodalinfluence = False
                        self.influence = 100
                    else:
                        self.allowmodalinfluence = not self.allowmodalinfluence

                elif event.type == 'F':
                    self.flatten = not self.flatten

                elif event.type == 'R':
                    self.regular = not self.regular

                elif event.type == 'X':
                    self.fix_midpoint = not self.fix_midpoint

                try:
                    ret = self.circle(context, self.active)

                    if not ret:
                        self.finish()
                        return {'FINISHED'}

                except Exception as e:
                    self.finish()

                    if bpy.context.mode == 'OBJECT':
                        bpy.ops.object.mode_set(mode='EDIT')

                    output_traceback(self, e)
                    return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()
            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def cancel_modal(self, removeHUD=True):
        if removeHUD:
            self.finish()

        bpy.ops.object.mode_set(mode='OBJECT')
        self.initbm.to_mesh(self.active.data)
        bpy.ops.object.mode_set(mode='EDIT')

    def invoke(self, context, event):
        self.active = context.active_object
        self.mx = self.active.matrix_world

        self.active.update_from_editmode()

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

        self.fix_midpoint = False

        self.factor = get_zoom_factor(context, self.mx @ average_locations([v.co for v in self.initbm.verts if v.select]))

        init_cursor(self, event)

        try:
            ret = self.circle(context, self.active, init=False)

            if not ret:
                self.cancel_modal(removeHUD=False)
                return {'FINISHED'}
        except Exception as e:
            if bpy.context.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='EDIT')

            output_traceback(self, e)
            return {'FINISHED'}

        init_status(self, context, 'LoopTools Circle')

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def prepare_geo(self, context, initbm):
        active = context.active_object
        mx = active.matrix_world

        edges = [e for e in initbm.edges if e.select]
        faces = [f for f in initbm.faces if f.select]

        if faces:

            bm = bmesh.from_edit_mesh(active.data)

            faces = [f for f in bm.faces if f.select]

            boundary = get_boundary_edges(faces, region_to_loop=True)
            boundary_indices = [e.index for e in boundary]

            bmesh.update_edit_mesh(active.data)

            edges = [e for e in edges if e.index in boundary_indices]

        islands = get_edge_selection_islands(edges, debug=False)

        return islands

    def get_island_centers(self, islands):
        centers = []

        for island in islands:
            verts = list(set(v for e in island for v in e.verts))

            avg_center = average_locations([v.co for v in verts])
            draw_point(avg_center, mx=self.mx, color=yellow, modal=False)

            circle_center, _ = get_irregular_circle_center(verts, mx=self.mx, debug=True)
            draw_point(circle_center, mx=self.mx, color=red, modal=False)

            offset = circle_center - avg_center if circle_center else Vector()

            centers.append(offset)

        return centers

    def circle(self, context, active, init=False):
        if not init:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.initbm.to_mesh(active.data)
            bpy.ops.object.mode_set(mode='EDIT')

        bpy.ops.mesh.looptools_circle(custom_radius=self.use_custom_radius, fit=self.method, flatten=self.flatten, influence=self.influence, lock_x=self.lock_x, lock_y=self.lock_y, lock_z=self.lock_z, radius=self.radius, regular=self.regular)

        return True

class LoopToolsRelax(bpy.types.Operator):
    bl_idname = "machin3.looptools_relax"
    bl_label = "MACHIN3: LoopTools Relax"
    bl_description = "LoopTools's Relax as a modal"
    bl_options = {'REGISTER', 'UNDO'}

    iterations: EnumProperty(name="Iterations", items=looptools_relax_iterations_items, description="Number of times the loop is relaxed", default="1")
    input: EnumProperty(name="Input", items=looptools_relax_input_items, description="Loops that are relaxed", default='selected')
    interpolation: EnumProperty(name="Interpolation", items=looptools_relax_interpolation_items, description="Algorithm used for interpolation", default='cubic')
    regular: BoolProperty(name="Regular", description="Distribute vertices at constant distances along the loop", default=False)
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Relax", subtitle="LoopTools")

            draw_prop(self, "Iterations", self.iterations, hint="scroll UP/DOWN")
            draw_prop(self, "Regular", self.regular, offset=18, hint="toggle R")
            self.offset += 10

            draw_prop(self, "Input", self.input, offset=18, hint="CTRL scroll UP/DOWN")
            draw_prop(self, "Interpolation", self.interpolation, offset=18, hint="ALT scroll UP/DOWN")

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        if event.type in ['WHEELUPMOUSE', 'ONE', 'WHEELDOWNMOUSE', 'TWO', 'R']:

            if event.value == 'PRESS':

                if event.type in {'WHEELUPMOUSE', 'ONE'} and event.value == 'PRESS':
                    if event.ctrl:
                        self.input = step_enum(self.input, looptools_relax_input_items, 1)

                    elif event.alt:
                        self.interpolation = step_enum(self.interpolation, looptools_relax_interpolation_items, 1)

                    else:
                        self.iterations = step_enum(self.iterations, looptools_relax_iterations_items, 1, loop=False)

                elif event.type in {'WHEELDOWNMOUSE', 'TWO'} and event.value == 'PRESS':
                    if event.ctrl:
                        self.input = step_enum(self.input, looptools_relax_input_items, -1)

                    elif event.alt:
                        self.interpolation = step_enum(self.interpolation, looptools_relax_interpolation_items, -1)

                    else:
                        self.iterations = step_enum(self.iterations, looptools_relax_iterations_items, -1, loop=False)

                elif event.type == 'R' and event.value == "PRESS":
                    self.regular = not self.regular

                try:
                    ret = self.relax(self.active)

                    if not ret:
                        self.finish()
                        return {'FINISHED'}

                except Exception as e:
                    self.finish()

                    if bpy.context.mode == 'OBJECT':
                        bpy.ops.object.mode_set(mode='EDIT')

                    output_traceback(self, e)
                    return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def cancel_modal(self, removeHUD=True):
        if removeHUD:
            self.finish()

        bpy.ops.object.mode_set(mode='OBJECT')
        self.initbm.to_mesh(self.active.data)
        bpy.ops.object.mode_set(mode='EDIT')

    def invoke(self, context, event):
        self.active = context.active_object

        self.active.update_from_editmode()

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

        init_cursor(self, event)

        try:
            ret = self.relax(self.active, init=True)

            if not ret:
                self.cancel_modal(removeHUD=False)
                return {'FINISHED'}
        except Exception as e:
            if bpy.context.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='EDIT')

            output_traceback(self, e)
            return {'FINISHED'}

        init_status(self, context, 'LoopTools Relax')

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def relax(self, active, init=False):
        if not init:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.initbm.to_mesh(active.data)
            bpy.ops.object.mode_set(mode='EDIT')

        bpy.ops.mesh.looptools_relax(input=self.input, interpolation=self.interpolation, iterations=self.iterations, regular=self.regular)

        return True

class LoopToolsSpace(bpy.types.Operator):
    bl_idname = "machin3.looptools_space"
    bl_label = "MACHIN3: LoopTools Space"
    bl_description = "LoopTools's SPace as a modal"
    bl_options = {'REGISTER', 'UNDO'}

    influence: FloatProperty(name="Influence", description="Force of the tool", default=100.0, min=0.0, max=100.0, precision=1, subtype='PERCENTAGE')
    input: EnumProperty(name="Input", items=looptools_relax_input_items, description="Loops that are relaxed", default='selected')
    interpolation: EnumProperty(name="Interpolation", items=looptools_relax_interpolation_items, description="Algorithm used for interpolation", default='cubic')
    allowmodalinfluence: BoolProperty(default=False)
    passthrough: BoolProperty(default=False)
    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            draw_title(self, "Space", subtitle="LoopTools")

            self.offset += 10

            draw_prop(self, "Influence", self.influence, offset=18, active=self.allowmodalinfluence, hint="move UP/DOWN, toggle Q, reset ALT + Q")

            self.offset += 10

            draw_prop(self, "Input", self.input, offset=18, hint="CTRL scroll UP/DOWN")
            draw_prop(self, "Interpolation", self.interpolation, offset=18, hint="ALT scroll UP/DOWN")

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            update_HUD_location(self, event)

        events = ['WHEELUPMOUSE', 'ONE', 'WHEELDOWNMOUSE', 'TWO', 'Q', 'I']

        if self.allowmodalinfluence:
            events.append('MOUSEMOVE')

        if event.type in events:

            if event.type == 'MOUSEMOVE':
                if self.passthrough:
                    self.passthrough = False

                else:
                    if self.allowmodalinfluence:

                        divisor = 10 if event.shift else 0.1 if event.ctrl else 1

                        delta_y = event.mouse_y - self.last_mouse_y
                        delta_influence = delta_y / divisor

                        self.influence += delta_influence

                    try:
                        ret = self.space(self.active)

                        if not ret:
                            self.finish()
                            return {'FINISHED'}

                    except Exception as e:
                        self.finish()

                        if bpy.context.mode == 'OBJECT':
                            bpy.ops.object.mode_set(mode='EDIT')

                        output_traceback(self, e)
                        return {'FINISHED'}

            elif event.value == 'PRESS':

                if event.type in {'WHEELUPMOUSE', 'ONE'}:
                    if event.ctrl:
                        self.input = step_enum(self.input, looptools_relax_input_items, 1)

                    elif event.alt:
                        self.interpolation = step_enum(self.interpolation, looptools_relax_interpolation_items, 1)

                elif event.type in {'WHEELDOWNMOUSE', 'TWO'}:
                    if event.ctrl:
                        self.input = step_enum(self.input, looptools_relax_input_items, -1)

                    elif event.alt:
                        self.interpolation = step_enum(self.interpolation, looptools_relax_interpolation_items, -1)

                elif event.type in ['I', 'Q']:
                    if event.alt:
                        self.allowmodalinfluence = False
                        self.influence = 100
                    else:
                        self.allowmodalinfluence = not self.allowmodalinfluence

                try:
                    ret = self.space(self.active)

                    if not ret:
                        self.finish()
                        return {'FINISHED'}

                except Exception as e:
                    self.finish()

                    if bpy.context.mode == 'OBJECT':
                        bpy.ops.object.mode_set(mode='EDIT')

                    output_traceback(self, e)
                    return {'FINISHED'}

        elif event.type in {'MIDDLEMOUSE'} or (event.alt and event.type in {'LEFTMOUSE', 'RIGHTMOUSE'}) or event.type.startswith('NDOF'):
            self.passthrough = True
            return {'PASS_THROUGH'}

        elif event.type in {'LEFTMOUSE', 'SPACE'}:
            self.finish()
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            self.cancel_modal()
            return {'CANCELLED'}

        self.last_mouse_x = event.mouse_x
        self.last_mouse_y = event.mouse_y

        return {'RUNNING_MODAL'}

    def finish(self):
        bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

    def cancel_modal(self, removeHUD=True):
        if removeHUD:
            self.finish()

        bpy.ops.object.mode_set(mode='OBJECT')
        self.initbm.to_mesh(self.active.data)
        bpy.ops.object.mode_set(mode='EDIT')

    def invoke(self, context, event):
        self.active = context.active_object

        self.active.update_from_editmode()

        self.initbm = bmesh.new()
        self.initbm.from_mesh(self.active.data)

        init_cursor(self, event)

        try:
            ret = self.space(self.active, init=True)

            if not ret:
                self.cancel_modal(removeHUD=False)
                return {'FINISHED'}
        except Exception as e:
            if bpy.context.mode == 'OBJECT':
                bpy.ops.object.mode_set(mode='EDIT')

            output_traceback(self, e)
            return {'FINISHED'}

        init_status(self, context, 'LoopTools Relax')

        self.area = context.area
        self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def space(self, active, init=False):
        if not init:
            bpy.ops.object.mode_set(mode='OBJECT')
            self.initbm.to_mesh(active.data)
            bpy.ops.object.mode_set(mode='EDIT')

        bpy.ops.mesh.looptools_space(influence=self.influence, input=self.input, interpolation=self.interpolation, lock_x=False, lock_y=False, lock_z=False)

        return True
