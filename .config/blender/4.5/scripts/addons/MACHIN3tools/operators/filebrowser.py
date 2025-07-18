import bpy
from bpy.props import StringProperty, BoolProperty, FloatProperty

from mathutils import Vector

import os

from .. utils.asset import get_asset_library_reference, get_registered_library_references, set_asset_catalog_id, set_asset_library_reference, get_asset_import_method, set_asset_import_method, get_asset_details_from_space, get_asset_ids
from .. utils.draw import draw_fading_label, draw_init, draw_label, draw_tris
from .. utils.property import step_list
from .. utils.registration import get_prefs
from .. utils.system import abspath, open_folder
from .. utils.ui import draw_status_item, finish_status, force_ui_update, get_mouse_pos, get_scale, ignore_events, init_modal_handlers, init_status, warp_mouse, wrap_mouse, update_mod_keys
from .. utils.workspace import get_3dview

from .. colors import red, white, blue
from .. items import alt

class Open(bpy.types.Operator):
    bl_idname = "machin3.filebrowser_open"
    bl_label = "MACHIN3: Open in System's filebrowser"
    bl_description = "Open the current location in the System's own filebrowser\nALT: Open .blend file"
    bl_options = {'REGISTER'}

    path: StringProperty(name="Path")
    blend_file: BoolProperty(name="Open .blend file")

    @classmethod
    def poll(cls, context):
        if context.area:
            return context.area.type == 'FILE_BROWSER'

    def execute(self, context):
        space = context.space_data
        params = space.params

        directory = abspath(params.directory.decode())
        active_file = context.active_file

        if active_file:
            if self.blend_file:

                if active_file.asset_data:
                    _, _, local_id = get_asset_ids(context)

                    if not local_id:
                        bpy.ops.asset.open_containing_blend_file()

                    else:
                        area, region, region_data, _ = get_3dview(context)

                        if area:
                            with context.temp_override(area=area, region=region, region_data=region_data):
                                draw_fading_label(context, text="The blend file containing this asset is already open.", color=red)

                else:
                    path = os.path.join(directory, active_file.relative_path)
                    bpy.ops.machin3.open_library_blend(blendpath=path)

            else:

                if active_file.asset_data:
                    _, libpath, _, _ = get_asset_details_from_space(context, space, debug=False)

                    if libpath:
                        open_folder(libpath)

                else:
                    open_folder(directory)

            return {'FINISHED'}
        return {'CANCELLED'}

class Toggle(bpy.types.Operator):
    bl_idname = "machin3.filebrowser_toggle"
    bl_label = "MACHIN3: Toggle Filebrowser"
    bl_description = ""
    bl_options = {'INTERNAL'}

    type: StringProperty()

    @classmethod
    def poll(cls, context):
        if context.area:
            return context.area.type == 'FILE_BROWSER'

    @classmethod
    def description(cls, context, properties):
        if context.area.ui_type == 'ASSETS' and properties.type == 'DISPLAY_TYPE':
            return f"Cycle Display Type: {context.space_data.params.display_type}"
        return "Toggle/Cycle SORT, DISPLAY_TYPE, HIDDEN"

    def execute(self, context):
        params = context.space_data.params

        if self.type == 'SORT':

            if context.area.ui_type == 'FILES':
                if params.sort_method == 'FILE_SORT_ALPHA':
                    params.sort_method = 'FILE_SORT_TIME'

                else:
                    params.sort_method = 'FILE_SORT_ALPHA'

            elif context.area.ui_type == 'ASSETS':
                asset_libraries = get_registered_library_references(context)

                current = get_asset_library_reference(params)
                next = step_list(current, asset_libraries, 1)

                set_asset_library_reference(params, next)

                set_asset_catalog_id(params, 'ALL')

        elif self.type == 'DISPLAY_TYPE':

            if context.area.ui_type == 'FILES':
                display_types = ['LIST_VERTICAL', 'THUMBNAIL']

            elif context.area.ui_type == 'ASSETS':
                if bpy.app.version >= (4, 5, 0):
                    display_types = ['LIST_HORIZONTAL', 'THUMBNAIL']
                else:
                    display_types = ['LIST_VERTICAL', 'LIST_HORIZONTAL', 'THUMBNAIL']

            if context.area.ui_type == 'FILES' and params.display_type == 'LIST_HORIZONTAL':
                params.display_type = 'LIST_VERTICAL'

            else:
                params.display_type = step_list(params.display_type, display_types, step=1, loop=True)

        elif self.type == 'HIDDEN':
            if context.area.ui_type == 'FILES':
                params.show_hidden = not params.show_hidden
                params.use_filter_backup = params.show_hidden

            elif context.area.ui_type == 'ASSETS':
                current = get_asset_library_reference(params)

                if current != 'LOCAL':
                    if context.region.width > context.region.height:
                        bpy.ops.machin3.set_asset_import_method('INVOKE_DEFAULT')

                    else:
                        if current != 'LOCAL':
                            import_methods = ['LINK', 'APPEND', 'APPEND_REUSE', 'FOLLOW_PREFS']

                            current = get_asset_import_method(params)
                            next = step_list(current, import_methods, 1)
                            set_asset_import_method(params, next)

        return {'FINISHED'}

def draw_adjust_thumbnail_size_status(op):
    def draw(self, context):
        layout = self.layout

        row = layout.row(align=True)
        row.label(text=f"Adjust Asset {'Shelf' if op.shelf else 'Browser'} {'Column' if op.is_45_list_view and op.is_alt else 'Thumbnail'} Size")

        draw_status_item(row, key='LMB', text='Finish')
        draw_status_item(row, key='RMB', text='Cancel')

        if op.is_45_list_view:
            draw_status_item(row, active=op.is_alt, key='ALT', text='Adjust Column', gap=10)

        if op.is_45_list_view:
            if op.is_alt:
                size = op.column_size
            else:
                size = op.list_size
        else:
            size = op.size

        draw_status_item(row, key='MOVE', text='Size', prop=int(size), gap=2 if op.is_45_list_view else 10)

    return draw

class AdjustThumbnailSize(bpy.types.Operator):
    bl_idname = "machin3.filebrowser_adjust_thumbnail_size"
    bl_label = "MACHIN3: Adjust Thumbnail Size"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    size: FloatProperty(name="Thumbnail Size", min=24, max=256)
    list_size: FloatProperty(name="List Size", min=16, max=128)
    column_size: FloatProperty(name="Column Size", min=32, max=750)

    is_45_list_view: BoolProperty(default=False)
    @classmethod
    def poll(cls, context):
        if context.area:

            if context.area.type == 'FILE_BROWSER':
                params = context.space_data.params
                if params.display_type == 'THUMBNAIL':
                    return True

                elif bpy.app.version >= (4, 5, 0) and context.area.ui_type == 'ASSETS':
                    return params.display_type in ['THUMBNAIL', 'LIST_HORIZONTAL']

            elif context.region.type == 'ASSET_SHELF':
                return True

    def draw_HUD(self, context):
        if context.area == self.area:
            draw_init(self)

            scale_compensate = context.preferences.system.ui_scale * get_prefs().modal_hud_scale

            if self.is_45_list_view:
                if self.is_alt:
                    title, color = (str(int(self.column_size)), blue)
                else:
                    title, color = (str(int(self.list_size)), white)
            else:
                title, color = (str(int(self.size)), white)

            if self.shelf:
                text_size = int(self.size * scale_compensate)

                x = (self.window_size.x / 2)

                if self.shelf_region.alignment == "BOTTOM":
                    y = self.shelf_region.y - context.region.y + self.shelf_region.height + 10 * scale_compensate
                else:
                    y = context.region.height - self.shelf_region.height - text_size

            else:
                text_size = int(self.window_size.y * 0.75 / scale_compensate)

                x = (self.window_size.x / 2)
                y = (self.window_size.y / 2) - ((text_size * scale_compensate) / 3)  # not sure why 3, but 2 does not center it properly

            draw_label(context, title=title, coords=Vector((x, y)), center=True, size=text_size, color=color, alpha=0.5)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        update_mod_keys(self, event)

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)
            wrap_mouse(self, context, x=True, y=False)

            deltax = self.mouse_pos.x - self.last_mouse.x
            sensitivity = 0.1 * self.scale

            if self.is_45_list_view:
                if self.is_alt:
                    self.column_size += deltax * sensitivity

                    params = context.space_data.params
                    params.list_column_size = int(self.column_size)

                    self.last_mouse = self.mouse_pos
                    return {'RUNNING_MODAL'}

                else:
                    self.list_size += deltax * sensitivity

            else:
                self.size += deltax * sensitivity

            self.set_thumbnail_size(context)

            force_ui_update(context)

            self.last_mouse = self.mouse_pos
            return {'RUNNING_MODAL'}

        if (event.value == 'RELEASE' and event.type not in alt) or event.type in ['LEFTMOUSE', 'SPACE']:
            self.finish(context)
            return {'FINISHED'}

        elif event.type in ['RIGHTMOUSE', 'ESC']:
            self.finish(context)

            if self.is_45_list_view:
                context.space_data.params.list_display_size = int(self.init_size)
                context.space_data.params.list_column_size = int(self.init_column_size)

            else:
                context.space_data.params.display_size = int(self.init_size)

            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        if self.shelf:
            bpy.types.SpaceView3D.draw_handler_remove(self.HUD, 'WINDOW')
        else:
            bpy.types.SpaceFileBrowser.draw_handler_remove(self.HUD, 'WINDOW')

        finish_status(self)

        context.window.cursor_set('DEFAULT')

    def invoke(self, context, event):
        self.shelf, self.shelf_region = self.get_asset_shelf(context)

        self.get_thumbnail_size(context, init=True)

        get_mouse_pos(self, context, event)
        context.window.cursor_set('SCROLL_X')
        self.last_mouse = self.mouse_pos

        self.scale = get_scale(context)

        for region in context.area.regions:
            if region.type == 'WINDOW':
                self.window_size = Vector((region.width, region.height))
                break

        update_mod_keys(self)

        init_status(self, context, func=draw_adjust_thumbnail_size_status(self))

        force_ui_update(context)

        init_modal_handlers(self, context)

        if self.shelf:
            self.HUD = bpy.types.SpaceView3D.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')
        else:
            self.HUD = bpy.types.SpaceFileBrowser.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        warp_mouse(self, context, self.mouse_pos)
        return {'RUNNING_MODAL'}

    def get_thumbnail_size(self, context, init=False):
        self.is_45_list_view = False

        if context.region.type == 'ASSET_SHELF':
            if init:
                self.size = context.asset_shelf.preview_size
                self.init_size = self.size

            return context.asset_shelf.preview_size

        else:
            params = context.space_data.params

            if params.display_type == 'THUMBNAIL':
                if init:
                    self.size = params.display_size
                    self.init_size = self.size

                return params.display_size

            elif bpy.app.version >= (4, 5, 0) and context.area.ui_type == 'ASSETS':
                if init:
                    self.is_45_list_view = True

                    self.list_size = params.list_display_size
                    self.init_size = self.list_size

                    self.column_size = params.list_column_size
                    self.init_column_size = self.column_size

                return params.list_display_size

    def set_thumbnail_size(self, context):
        if context.region.type == 'ASSET_SHELF':
            context.asset_shelf.preview_size = int(self.size)

        else:
            params = context.space_data.params

            if params.display_type == 'THUMBNAIL':
                params.display_size = int(self.size)

            elif self.is_45_list_view:
                params.list_display_size = int(self.list_size)

    def get_asset_shelf(self, context):
        if context.region.type == 'ASSET_SHELF':
            return context.asset_shelf, context.region

        return None, None

class SetAssetImportMethod(bpy.types.Operator):
    bl_idname = "machin3.set_asset_import_method"
    bl_label = "MACHIN3: Set Asset Import Method"
    bl_description = "Set Asset Import Method"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        if context.area:
            if context.area.type == 'FILE_BROWSER' and context.area.ui_type == 'ASSETS':
                params = context.space_data.params
                return get_asset_library_reference(params) != 'LOCAL'

    def draw_HUD(self, context):
        if context.area == self.area:
            indices = ((0, 1, 2), (0, 2, 3))

            bgcolor = context.preferences.themes['Default'].file_browser.space.back

            for method, field in self.fields.items():
                is_hover = method == self.method

                color = (0.1, 0.1, 0.1) if is_hover else bgcolor
                draw_tris(field['coords'], indices, color=color, alpha=0.9)

                alpha = 1 if is_hover else 0.5
                title = method.replace('_', ' ').title()
                size = 14 if is_hover else 12
                draw_label(context, title=title, coords=field['center'], size=size, alpha=alpha)

    def modal(self, context, event):
        if ignore_events(event):
            return {'RUNNING_MODAL'}

        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            get_mouse_pos(self, context, event)

            for method, field in self.fields.items():
                if self.mouse_pos.x > field['coords'][0].x and self.mouse_pos.x <= field['coords'][1].x:
                    if self.mouse_pos.y > field['coords'][0].y and self.mouse_pos.y <= field['coords'][3].y:
                        self.method = method

                        if (method := get_asset_import_method(context.space_data.params)) != self.method:
                            set_asset_import_method(context.space_data.params, self.method)

                        break

        if event.value == 'RELEASE' or event.type in ['LEFTMOUSE', 'SPACE']:
            self.finish(context)

            return {'FINISHED'}

        elif event.type in ['RIGHTMOUSE', 'ESC']:
            self.finish(context)

            set_asset_import_method(context.space_data.params, self.init_method)
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}

    def finish(self, context):
        bpy.types.SpaceFileBrowser.draw_handler_remove(self.HUD, 'WINDOW')
        context.window.cursor_set('DEFAULT')

    def invoke(self, context, event):
        params = context.space_data.params
        import_methods = ['LINK', 'APPEND', 'APPEND_REUSE', 'FOLLOW_PREFS']

        self.method = get_asset_import_method(params)
        self.init_method = self.method

        get_mouse_pos(self, context, event)
        context.window.cursor_set('SCROLL_X')
        self.last_mouse = self.mouse_pos

        self.scale = get_scale(context)

        for region in context.area.regions:
            if region.type == 'WINDOW':
                self.fields = {}

                for idx, method in enumerate(import_methods):
                    width = region.width / len(import_methods)

                    coords = [Vector((width * idx, 0, 0)), Vector((width * (idx + 1) , 0, 0)), Vector((width * (idx + 1), region.height, 0)), Vector((width * idx, region.height, 0))]
                    center = Vector((width * idx + width / 2, region.height / 2))

                    data = {'index': idx,
                            'coords': coords,
                            'center': center}

                    self.fields[method] = data

                break

        init_modal_handlers(self, context)

        self.HUD = bpy.types.SpaceFileBrowser.draw_handler_add(self.draw_HUD, (context, ), 'WINDOW', 'POST_PIXEL')

        warp_mouse(self, context, self.mouse_pos)
        return {'RUNNING_MODAL'}
