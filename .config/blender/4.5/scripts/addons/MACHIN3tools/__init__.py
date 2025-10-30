bl_info = {
    "name": "MACHIN3tools",
    "author": "MACHIN3, TitusLVR",
    "version": (1, 12, 2),
    "blender": (4, 2, 0),
    "location": "Everywhere",
    "revision": "6b2ed97664636e6fc228c27f55332ee7c8fce3da",
    "description": "Streamlining Blender 4.2+.",
    "warning": "",
    "doc_url": "https://machin3.io/MACHIN3tools/docs",
    "category": "3D View"}

def reload_modules(name):
    import importlib

    dbg = False

    from . import registration, items, colors

    for module in [registration, items, colors]:
        importlib.reload(module)

    utils_modules = sorted([name[:-3] for name in os.listdir(os.path.join(__path__[0], "utils")) if name.endswith('.py')])

    for module in utils_modules:
        impline = f"from . utils import {module}"

        if dbg:
            print(f"reloading {name}.utils.{module}")

        exec(impline)
        importlib.reload(eval(module))

    from . import handlers

    if dbg:
        print("reloading", handlers.__name__)

    importlib.reload(handlers)

    modules = []

    for label in registration.classes:
        entries = registration.classes[label]
        for entry in entries:
            path = entry[0].split('.')
            module = path.pop(-1)

            if (path, module) not in modules:
                modules.append((path, module))

    for path, module in modules:
        if path:
            impline = f"from . {'.'.join(path)} import {module}"
        else:
            impline = f"from . import {module}"

        if dbg:
            print(f"reloading {name}.{'.'.join(path)}.{module}")

        exec(impline)
        importlib.reload(eval(module))

if 'bpy' in locals():
    reload_modules(bl_info['name'])

import bpy
from bpy.props import PointerProperty, BoolProperty, EnumProperty

import os
import importlib

from . properties import M3SceneProperties, M3ObjectProperties, M3CollectionProperties

from . utils.registration import get_addon, get_core, get_prefs, get_tools, get_pie_menus
from . utils.registration import register_classes, unregister_classes, register_keymaps, unregister_keymaps, register_icons, unregister_icons, register_msgbus, unregister_msgbus
from . utils.system import printd, verify_update, install_update

from . handlers import load_post, undo_pre, depsgraph_update_post, render_start, render_end

from . ui.menus import asset_browser_bookmark_buttons, asset_browser_metadata, object_context_menu, mesh_context_menu, face_context_menu, apply_transform_menu, add_object_buttons, material_pick_button, outliner_group_toggles, extrude_menu, group_origin_adjustment_toggle, render_menu, render_buttons, asset_browser_update_thumbnail

def register():
    global classes, keymaps, icons, owner

    MACHIN3toolsManager.clear_registered_count()

    core_classes = register_classes(get_core())

    bpy.types.Scene.M3 = PointerProperty(type=M3SceneProperties)
    bpy.types.Object.M3 = PointerProperty(type=M3ObjectProperties)
    bpy.types.Collection.M3 = PointerProperty(type=M3CollectionProperties)

    bpy.types.WindowManager.M3_screen_cast = BoolProperty()
    bpy.types.WindowManager.M3_asset_catalogs = EnumProperty(items=[])

    tool_classlists, tool_keylists, tool_count = get_tools()
    pie_classlists, pie_keylists, pie_count = get_pie_menus()

    classes = register_classes(tool_classlists + pie_classlists) + core_classes
    keymaps = register_keymaps(tool_keylists + pie_keylists)

    bpy.types.VIEW3D_MT_object_context_menu.prepend(object_context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.prepend(mesh_context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_faces.append(face_context_menu)

    bpy.types.VIEW3D_MT_edit_mesh_extrude.append(extrude_menu)
    bpy.types.VIEW3D_MT_mesh_add.prepend(add_object_buttons)
    bpy.types.VIEW3D_MT_object_apply.append(apply_transform_menu)

    bpy.types.VIEW3D_MT_editor_menus.append(material_pick_button)

    bpy.types.OUTLINER_HT_header.prepend(outliner_group_toggles)

    bpy.types.ASSETBROWSER_MT_editor_menus.append(asset_browser_bookmark_buttons)
    bpy.types.ASSETBROWSER_PT_metadata.prepend(asset_browser_metadata)
    bpy.types.ASSETBROWSER_PT_metadata_preview.append(asset_browser_update_thumbnail)

    bpy.types.VIEW3D_PT_tools_object_options_transform.append(group_origin_adjustment_toggle)

    bpy.types.TOPBAR_MT_render.append(render_menu)
    bpy.types.DATA_PT_context_light.prepend(render_buttons)

    icons = register_icons()

    owner = object()
    register_msgbus(owner)

    bpy.app.handlers.load_post.append(load_post)
    bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)

    bpy.app.handlers.render_init.append(render_start)
    bpy.app.handlers.render_cancel.append(render_end)
    bpy.app.handlers.render_complete.append(render_end)

    bpy.app.handlers.undo_pre.append(undo_pre)

    MACHIN3toolsManager.clear_addons()

    if get_prefs().registration_debug:
        print(f"Registered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])} with {tool_count} {'tool' if tool_count == 1 else 'tools'}, {pie_count} pie {'menu' if pie_count == 1 else 'menus'}")

    verify_update()

def unregister():
    global classes, keymaps, icons, owner

    debug = get_prefs().registration_debug

    bpy.app.handlers.load_post.remove(load_post)

    from . handlers import axesVIEW3D, focusHUD, surfaceslideHUD, screencastHUD, grouprelationsVIEW3D, assemblyeditHUD

    if axesVIEW3D and "RNA_HANDLE_REMOVED" not in str(axesVIEW3D):
        bpy.types.SpaceView3D.draw_handler_remove(axesVIEW3D, 'WINDOW')

    if focusHUD and "RNA_HANDLE_REMOVED" not in str(focusHUD):
        bpy.types.SpaceView3D.draw_handler_remove(focusHUD, 'WINDOW')

    if surfaceslideHUD and "RNA_HANDLE_REMOVED" not in str(surfaceslideHUD):
        bpy.types.SpaceView3D.draw_handler_remove(surfaceslideHUD, 'WINDOW')

    if screencastHUD and "RNA_HANDLE_REMOVED" not in str(screencastHUD):
        bpy.types.SpaceView3D.draw_handler_remove(screencastHUD, 'WINDOW')

    if grouprelationsVIEW3D and "RNA_HANDLE_REMOVED" not in str(grouprelationsVIEW3D):
        bpy.types.SpaceView3D.draw_handler_remove(grouprelationsVIEW3D, 'WINDOW')

    if assemblyeditHUD and "RNA_HANDLE_REMOVED" not in str(assemblyeditHUD):
        bpy.types.SpaceView3D.draw_handler_remove(assemblyeditHUD, 'WINDOW')

    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)

    bpy.app.handlers.render_init.remove(render_start)
    bpy.app.handlers.render_cancel.remove(render_end)
    bpy.app.handlers.render_complete.remove(render_end)

    bpy.app.handlers.undo_pre.remove(undo_pre)

    unregister_msgbus(owner)

    bpy.types.VIEW3D_MT_object_context_menu.remove(object_context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(mesh_context_menu)
    bpy.types.VIEW3D_MT_edit_mesh_faces.remove(face_context_menu)

    bpy.types.VIEW3D_MT_edit_mesh_extrude.remove(extrude_menu)
    bpy.types.VIEW3D_MT_mesh_add.remove(add_object_buttons)
    bpy.types.VIEW3D_MT_object_apply.remove(apply_transform_menu)
    bpy.types.VIEW3D_MT_editor_menus.remove(material_pick_button)

    bpy.types.OUTLINER_HT_header.remove(outliner_group_toggles)

    bpy.types.ASSETBROWSER_MT_editor_menus.remove(asset_browser_bookmark_buttons)
    bpy.types.ASSETBROWSER_PT_metadata.remove(asset_browser_metadata)
    bpy.types.ASSETBROWSER_PT_metadata_preview.remove(asset_browser_update_thumbnail)

    bpy.types.VIEW3D_PT_tools_object_options_transform.remove(group_origin_adjustment_toggle)

    bpy.types.TOPBAR_MT_render.remove(render_menu)
    bpy.types.DATA_PT_context_light.remove(render_buttons)

    unregister_keymaps(keymaps)
    unregister_classes(classes)

    del bpy.types.Scene.M3
    del bpy.types.Object.M3
    del bpy.types.Collection.M3

    del bpy.types.WindowManager.M3_screen_cast
    del bpy.types.WindowManager.M3_asset_catalogs

    unregister_icons(icons)

    if debug:
        print(f"Unregistered {bl_info['name']} {'.'.join([str(i) for i in bl_info['version']])}.")

    install_update()

class MACHIN3toolsManager:

    props = {
        'operators': {
            'tools': 0,
            'pies': 0
        },

        'keymaps': {
            'tools': 0,
            'pies': 0
        }

    }

    addons = {}
    defaults = []
    @classmethod
    def get_addon(cls, name='SomeAddon', version=False, debug=False):

        addon = cls.addons.setdefault(name.lower(), {'enabled': None, 'version': None, 'foldername': '', 'path': '', 'module': None})
        if addon['enabled'] is None:
            addon['enabled'],  addon['foldername'],  addon['version'],  addon['path'] = get_addon(name)

            if addon['enabled']:
                addon['module'] = importlib.import_module(addon['foldername'])

            if debug:
                printd(addon, name)

        return (addon['enabled'], addon['version']) if version else addon['enabled']

    @classmethod
    def clear_addons(cls):
        cls.addons.clear()

    @classmethod
    def clear_registered_count(cls):
        cls.props['operators']['tools'] = 0
        cls.props['operators']['pies'] = 0

        cls.props['keymaps']['tools'] = 0
        cls.props['keymaps']['pies'] = 0

    @classmethod
    def init_machin3_operator_idnames(cls):
        for addon in ['MACHIN3tools', 'DECALmachine', 'MESHmachine', 'CURVEmachine', 'HyperCursor', 'PUNCHit']:
            if cls.get_addon(addon) and 'idnames' not in cls.addons[addon.lower()]:
                module = cls.addons[addon.lower()]['module']
                classes = module.registration.classes

                idnames = []

                for imps in classes.values():
                    op_imps = [imp for imp in imps if 'operators' in imp[0] or 'macros' in imp[0]]
                    idnames.extend([f"machin3.{idname}" for _, cls in op_imps for _, idname in cls])

                cls.addons[addon.lower()]['idnames'] = idnames

    @classmethod
    def get_core_operator_idnames(cls):
        idnames = []

        for fr, imps in get_core()[0]:
            if 'operators' in fr:
                for name, idname in imps:
                    idnames.append(f"machin3.{idname}")

        return idnames

    @classmethod
    def init_operator_defaults(cls, bl_idname, properties, skip=None, debug=False):
        if bl_idname not in cls.defaults:
            if debug:
                print("\ngetting defaults for", bl_idname, "from addon prefs")
            cls.defaults.append(bl_idname)
            ignore = [
                "__doc__",
                "__module__",
                "__slots__",
                "bl_rna",
                "rna_type",
            ]

            if skip:
                props = [prop for prop in dir(properties) if prop not in ignore and prop not in skip]
            else:
                props = [prop for prop in dir(properties) if prop not in ignore]

            op = bl_idname.replace('MACHIN3_OT_', '')

            for prop in props:
                if debug:
                    print(" prop:", prop)

                if (default := getattr(get_prefs(), f"{op}_default_{prop}", None)) is not None:
                    if debug:
                        print("  prefs default:", default)
                        print("  op default:", getattr(properties, prop))
                    if default != getattr(properties, prop):
                        setattr(properties, prop, default)
        else:
            if debug:
                print("\ndefaults already set for", bl_idname)
