import bpy
from bpy.props import EnumProperty, BoolProperty

from .. utils.collection import get_collection_depth
from .. utils.draw import draw_fading_label
from .. utils.group import ensure_internal_index_group_name, get_group_base_name, group, set_unique_group_name, ungroup, get_group_matrix, select_group_children, get_child_depth, clean_up_groups, fade_group_sizes
from .. utils.math import average_locations
from .. utils.mesh import get_coords, get_eval_mesh
from .. utils.modifier import get_mods_as_dict, add_mods_from_dict
from .. utils.object import get_eval_bbox, parent, unparent, compensate_children
from .. utils.registration import get_prefs
from .. utils.ui import get_mouse_pos
from .. utils.view import ensure_visibility, get_location_2d, is_local_view, restore_visibility, visible_get
from .. utils.workspace import is_outliner

from .. items import group_location_items
from .. colors import red, green, yellow, white

ungroupable_batches = None

class Group(bpy.types.Operator):
    bl_idname = "machin3.group"
    bl_label = "MACHIN3: Group"
    bl_description = "Group Objects by Parenting them to an Empty"
    bl_options = {'REGISTER', 'UNDO'}

    location: EnumProperty(name="Location", items=group_location_items, default='AVERAGE')
    rotation: EnumProperty(name="Rotation", items=group_location_items, default='WORLD')
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            sel = [obj for obj in context.selected_objects]

            if len(sel) == 1:
                obj = sel[0]
                parent = obj.parent

                if parent:
                    booleans = [mod for mod in parent.modifiers if mod.type == 'BOOLEAN' and mod.object == obj]
                    if booleans:
                        return False
            return True

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row()
        row.label(text="Location")
        row.prop(self, 'location', expand=True)

        row = column.row()
        row.label(text="Rotation")
        row.prop(self, 'rotation', expand=True)

    def invoke(self, context, event):
        get_mouse_pos(self, context, event, hud_offset=(0, 20))
        return self.execute(context)

    def execute(self, context):
        context.evaluated_depsgraph_get()

        groupable = {obj for obj in context.selected_objects if (obj.parent and obj.parent.M3.is_group_empty) or not obj.parent}

        if any(col.library for obj in groupable for col in obj.users_collection):
            draw_fading_label(context, text="You can't group objects that are in a Linked Collection!", x=self.HUD_x, y=self.HUD_y, color=red, time=get_prefs().HUD_fade_group * 2)
            return {'CANCELLED'}

        if groupable:
            ungroupable = [obj for obj in context.selected_objects if obj.parent and not obj.parent.M3.is_group_empty and obj.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT']]

            self.group(context, groupable, ungroupable, debug=False)

            global ungroupable_batches
            ungroupable_batches = []

            if ungroupable:
                dg = context.evaluated_depsgraph_get()

                for obj in ungroupable:
                    mx = obj.matrix_world

                    mesh = get_eval_mesh(dg, obj, data_block=False)
                    batch = get_coords(mesh, mx=mx, indices=True)

                    bbox = get_eval_bbox(obj)
                    loc2d = get_location_2d(context, mx @ average_locations(bbox), default='OFF_SCREEN')
                    ungroupable_batches.append((loc2d, batch))
                    del mesh

                bpy.ops.machin3.draw_ungroupable()

            return {'FINISHED'}

        text = ["ℹℹ Illegal Selection ℹℹ",
                "You can't create a group from a selection of Objects, that are parented to something other than group empties"]

        draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, color=[yellow, white], alpha=0.75, time=get_prefs().HUD_fade_group * 4, delay=1)
        return {'CANCELLED'}

    def group(self, context, objects, ungroupable, debug=False):
        grouped = {obj for obj in objects if obj.parent and obj.parent.M3.is_group_empty}

        selected_empties = {obj for obj in objects if obj.M3.is_group_empty}

        if debug:
            print("               sel: ", [obj.name for obj in objects])
            print("           grouped: ", [obj.name for obj in grouped])
            print("  selected empties: ", [obj.name for obj in selected_empties])

        if grouped == objects:

            unselected_empties = {obj.parent for obj in objects if obj not in selected_empties and obj.parent and obj.parent.M3.is_group_empty and obj.parent not in selected_empties}

            top_level = {obj for obj in selected_empties | unselected_empties if obj.parent not in selected_empties | unselected_empties}

            if debug:
                print("unselected empties", [obj.name for obj in unselected_empties])
                print("         top level", [obj.name for obj in top_level])

            if len(top_level) == 1:
                new_parent = top_level.pop()

            else:
                parent_groups = {obj.parent for obj in top_level}

                if debug:
                    print("     parent_groups", [obj.name if obj else None for obj in parent_groups])

                new_parent = parent_groups.pop() if len(parent_groups) == 1 else None

        else:
            new_parent = None

        if debug:
            print("        new parent", new_parent.name if new_parent else None)
            print(20 * "-")

        ungrouped = {obj for obj in objects - grouped if obj not in selected_empties}

        top_level = {obj for obj in selected_empties if obj.parent not in selected_empties}

        grouped = {obj for obj in grouped if obj not in selected_empties and obj.parent not in selected_empties}

        if len(top_level) == 1 and new_parent in top_level:
            new_parent = list(top_level)[0].parent

            if debug:
                print("updated parent", new_parent.name)

        if debug:
            print("     top level", [obj.name for obj in top_level])
            print("       grouped", [obj.name for obj in grouped])
            print("     ungrouped", [obj.name for obj in ungrouped])

        for obj in top_level | grouped:
            unparent(obj)

        empty = group(context, top_level | grouped | ungrouped, location=self.location, rotation=self.rotation)

        if new_parent:
            parent(empty, new_parent)
            empty.M3.is_group_object = True

        clean_up_groups(context)

        if get_prefs().group_tools_fade_sizes:
            fade_group_sizes(context, init=True)

        text = [f"{'Sub' if new_parent else 'Root'} Goup: {empty.name}"]
        color = [green if new_parent else yellow]
        time = get_prefs().HUD_fade_group
        alpha = 0.75

        if ungroupable:
            text.append(f"{len(ungroupable)}/{len(objects) + len(ungroupable)} Objects could not be grouped")
            color.append(yellow)
            time = get_prefs().HUD_fade_group * 4
            alpha = 1

        draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, color=color, alpha=alpha, time=time)

class Groupify(bpy.types.Operator):
    bl_idname = "machin3.groupify"
    bl_label = "MACHIN3: Groupify"
    bl_description = "Turn any Empty Hierarchy into Group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            return [obj for obj in context.selected_objects if obj.type == 'EMPTY' and not obj.M3.is_group_empty and obj.children]

    def execute(self, context):
        all_empties = [obj for obj in context.selected_objects if obj.type == 'EMPTY' and not obj.M3.is_group_empty and obj.children]

        empties = [e for e in all_empties if e.parent not in all_empties]

        self.groupify(empties)

        if get_prefs().group_tools_fade_sizes:
            fade_group_sizes(context, init=True)

        return {'FINISHED'}

    def groupify(self, objects):
        for obj in objects:
            if obj.type == 'EMPTY' and not obj.M3.is_group_empty and obj.children:
                obj.M3.is_group_empty = True
                obj.M3.is_group_object = True if obj.parent and obj.parent.M3.is_group_empty else False
                obj.show_in_front = True
                obj.empty_display_type = 'CUBE'
                obj.empty_display_size = get_prefs().group_tools_size
                obj.show_name = True

                if get_prefs().group_tools_auto_name:
                    set_unique_group_name(obj)

                self.groupify(obj.children)

            else:
                obj.M3.is_group_object = True

ungrouped_child_locations = None
ungrouped_child_batches = None

class UnGroup(bpy.types.Operator):
    bl_idname = "machin3.ungroup"
    bl_label = "MACHIN3: Un-Group"
    bl_options = {'REGISTER', 'UNDO'}

    ungroup_all_selected: BoolProperty(name="Un-Group all Selected Groups", default=False)
    ungroup_entire_hierarchy: BoolProperty(name="Un-Group entire Hierarchy down", default=False)
    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode

    @classmethod
    def description(cls, context, properties):
        if context.scene.M3.group_recursive_select and context.scene.M3.group_select:
            return "Un-Group selected top-level Groups\nALT: Un-Group all selected Groups"
        else:
            return "Un-Group selected top-level Groups\nALT: Un-Group all selected Groups\nCTRL: Un-Group entire Hierarchy down"

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        row = column.row(align=True)
        row.label(text="Un-Group")
        row.prop(self, 'ungroup_all_selected', text='All Selected', toggle=True)
        row.prop(self, 'ungroup_entire_hierarchy', text='Entire Hierarchy', toggle=True)

    def invoke(self, context, event):
        self.ungroup_all_selected = event.alt
        self.ungroup_entire_hierarchy = event.ctrl

        return self.execute(context)

    def execute(self, context):
        global ungrouped_child_locations, ungrouped_child_batches

        dg = context.evaluated_depsgraph_get()

        empties = self.get_group_empties(context)

        if empties:

            ungrouped_child_locations, ungrouped_child_batches, ungrouped_count = self.ungroup(empties, depsgraph=dg)#

            clean_up_groups(context)

            if get_prefs().group_tools_fade_sizes:
                fade_group_sizes(context, init=True)

            text = [f"Removed {ungrouped_count} Groups"]
            color = [red]
            alpha = [1]

            if ungrouped_child_locations:
                text.append(f"with {len(ungrouped_child_locations)} Sub-Groups")
                color.append(yellow)
                alpha.append(0.3)

            if ungrouped_child_batches:
                text.append(f"{'and' if ungrouped_child_locations else 'with'} {len(ungrouped_child_batches)} Group Objects")
                color.append(yellow)
                alpha.append(0.3)

            time_extension = bool(ungrouped_child_locations) + bool(ungrouped_child_batches)
            draw_fading_label(context, text=text, color=color, alpha=alpha, move_y=20 + 10 * time_extension, time=2 + time_extension)

            bpy.ops.machin3.draw_ungroup()

            return {'FINISHED'}
        return {'CANCELLED'}

    def get_group_empties(self, context):
        all_empties = [obj for obj in context.selected_objects if obj.M3.is_group_empty]

        if self.ungroup_all_selected:
            return all_empties

        else:
            return [e for e in all_empties if e.parent not in all_empties]

    def collect_entire_hierarchy(self, empties):
        for e in empties:
            children = [obj for obj in e.children if obj.M3.is_group_empty]

            for c in children:
                self.empties.add(c)

                self.collect_entire_hierarchy([c])

    def ungroup(self, empties, depsgraph):
        if self.ungroup_entire_hierarchy:
            self.empties = set(empties)

            self.collect_entire_hierarchy(empties)

        else:
            self.empties = empties

        empty_locations = []
        object_batches = []

        ungrouped_count = len(self.empties)

        for empty in self.empties:
            locations, batches = ungroup(empty, depsgraph=depsgraph)

            empty_locations.extend(locations)
            object_batches.extend(batches)

        return empty_locations, object_batches, ungrouped_count

class Select(bpy.types.Operator):
    bl_idname = "machin3.select_group"
    bl_label = "MACHIN3: Select Group"
    bl_description = "Select Group\nCTRL: Select entire Group Hierarchy down"
    bl_options = {'REGISTER', 'UNDO'}

    unhide: BoolProperty(name="Unhide Group Objects", default=True)
    recursive: BoolProperty(name="Recursive Selection", default=False)
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            return [obj for obj in context.selected_objects if obj.M3.is_group_empty or obj.M3.is_group_object]

    @classmethod
    def description(cls, context, properties):
        if not context.scene.M3.group_recursive_select or is_local_view():
            return "Select Groups of the current Selection\nCTRL: Select entire Group Hierarchy down"

        else:
            return "Select entire Group Hierarchies down"

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)

        column.prop(self, "unhide", toggle=True)

        if is_local_view() or not context.scene.M3.group_recursive_select:
            column.prop(self, "recursive", toggle=True)

    def invoke(self, context, event):
        if is_local_view() or not context.scene.M3.group_recursive_select:
            self.recursive = event.ctrl

        else:
            self.recursive = context.scene.M3.group_recursive_select
        return self.execute(context)

    def execute(self, context):
        clean_up_groups(context)

        empties = {obj for obj in context.selected_objects if obj.M3.is_group_empty}
        objects = [obj for obj in context.selected_objects if obj.M3.is_group_object and obj not in empties]

        for obj in objects:
            if obj.parent and obj.parent.M3.is_group_empty:
                empties.add(obj.parent)

        ensure_visibility(context, empties, scene=False, select=True)

        children = [obj for group in empties for obj in group.children_recursive if obj.M3.is_group_object] if self.recursive else [obj for group in empties for obj in group.children if obj.M3.is_group_object]

        ensure_visibility(context, children, scene=False, unhide=self.unhide, unhide_viewport=self.unhide, select=False)

        for e in empties:
            if len(empties) == 1:
                context.view_layer.objects.active = e

            select_group_children(context.view_layer, e, recursive=self.recursive or context.scene.M3.group_recursive_select)

        if get_prefs().group_tools_fade_sizes:
            fade_group_sizes(context, init=True)

        return {'FINISHED'}

class Duplicate(bpy.types.Operator):
    bl_idname = "machin3.duplicate_group"
    bl_label = "MACHIN3: duplicate_group"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            return [obj for obj in context.selected_objects if obj.M3.is_group_empty]

    @classmethod
    def description(cls, context, properties):
        if context.scene.M3.group_recursive_select:
            return "Duplicate entire Group Hierarchies down\nALT: Create Instances"
        else:
            return "Duplicate Top Level Groups\nALT: Create Instances\nCTRL: Duplicate entire Group Hierarchies down"

    def invoke(self, context, event):
        empties = [obj for obj in context.selected_objects if obj.M3.is_group_empty]

        bpy.ops.object.select_all(action='DESELECT')

        for e in empties:
            e.select_set(True)
            select_group_children(context.view_layer, e, recursive=event.ctrl or context.scene.M3.group_recursive_select)

        if get_prefs().group_tools_fade_sizes:
            fade_group_sizes(context, init=True)

        bpy.ops.object.duplicate_move_linked('INVOKE_DEFAULT') if event.alt else bpy.ops.object.duplicate_move('INVOKE_DEFAULT')

        return {'FINISHED'}

class Add(bpy.types.Operator):
    bl_idname = "machin3.add_to_group"
    bl_label = "MACHIN3: Add to Group"
    bl_description = "Add Selection to Group"
    bl_options = {'REGISTER', 'UNDO'}

    realign_group_empty: BoolProperty(name="Re-Align Group Empty", default=False)
    location: EnumProperty(name="Location", items=group_location_items, default='AVERAGE')
    rotation: EnumProperty(name="Rotation", items=group_location_items, default='WORLD')
    add_mirror: BoolProperty(name="Add Mirror Modifiers, if there are common ones among the existing Group's objects, that are missing from the new Objects", default=True)
    is_mirror: BoolProperty()

    add_color: BoolProperty(name="Add Object Color, from Group's Empty", default=True)
    is_color: BoolProperty()

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, 'realign_group_empty', toggle=True)

        row = column.row()
        row.active = self.realign_group_empty
        row.prop(self, 'location', expand=True)

        row = column.row()
        row.active = self.realign_group_empty
        row.prop(self, 'rotation', expand=True)

        row = column.row(align=True)

        if self.is_color:
            row.prop(self, 'add_color', text="Add Color", toggle=True)

        if self.is_mirror:
            row.prop(self, 'add_mirror', text="Add Mirror", toggle=True)

    def invoke(self, context, event):
        get_mouse_pos(self, context, event, hud_offset=(0, 20))
        return self.execute(context)

    def execute(self, context):
        debug = False

        active_group = context.active_object if context.active_object and context.active_object.M3.is_group_empty and context.active_object.select_get() else None

        if not active_group:

            active_group = context.active_object.parent if context.active_object and context.active_object.M3.is_group_object and context.active_object.select_get() else None

            if not active_group:
                return {'CANCELLED'}

        objects = [obj for obj in context.selected_objects if obj != active_group and obj not in active_group.children and (not obj.parent or (obj.parent and obj.parent.M3.is_group_empty and not obj.parent.select_get()))]

        if debug:
            print("active group", active_group.name)
            print("     addable", [obj.name for obj in objects])

        if objects:

            children = [c for c in active_group.children if c.M3.is_group_object and c.type == 'MESH' and c.name in context.view_layer.objects]

            self.is_mirror = any(obj for obj in children for mod in obj.modifiers if mod.type == 'MIRROR')

            self.is_color = any(obj.type == 'MESH' for obj in objects)

            for obj in objects:
                if obj.parent:
                    unparent(obj)

                parent(obj, active_group)

                obj.M3.is_group_object = True

                if obj.type == 'MESH':

                    if children and self.add_mirror:
                        self.mirror(obj, active_group, children)

                    if self.add_color:
                        obj.color = active_group.color

            if self.realign_group_empty:

                gmx = get_group_matrix(context, [c for c in active_group.children], self.location, self.rotation)

                compensate_children(active_group, active_group.matrix_world, gmx)

                active_group.matrix_world = gmx

            clean_up_groups(context)

            if get_prefs().group_tools_fade_sizes:
                fade_group_sizes(context, init=True)

            text = f"Added {len(objects)} objects to group '{active_group.name}'"
            draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, color=green, time=get_prefs().HUD_fade_group)

            return {'FINISHED'}
        return {'CANCELLED'}

    def mirror(self, obj, active_group, children):
        all_mirrors = {}

        for c in children:
            if c.M3.is_group_object and not c.M3.is_group_empty and c.type == 'MESH':
                mirrors = get_mods_as_dict(c, types=['MIRROR'], skip_show_expanded=True)

                if mirrors:
                    all_mirrors[c] = mirrors

        if all_mirrors and len(all_mirrors) == len(children):

            obj_props = [props for props in get_mods_as_dict(obj, types=['MIRROR'], skip_show_expanded=True).values()]

            if len(all_mirrors) == 1:

                common_props = [props for props in next(iter(all_mirrors.values())).values() if props not in obj_props]

            else:
                common_props = []

                for c, mirrors in all_mirrors.items():
                    others = [obj for obj in all_mirrors if obj != c]

                    for name, props in mirrors.items():
                        if all(props in all_mirrors[o].values() for o in others) and props not in common_props:
                            if props not in obj_props:
                                common_props.append(props)

            if common_props:
                common_mirrors = {f"Mirror{'.' + str(idx).zfill(3) if idx else ''}": props for idx, props in enumerate(common_props)}

                add_mods_from_dict(obj, common_mirrors)

class Remove(bpy.types.Operator):
    bl_idname = "machin3.remove_from_group"
    bl_label = "MACHIN3: Remove from Group"
    bl_description = "Remove Selection from Group"
    bl_options = {'REGISTER', 'UNDO'}

    realign_group_empty: BoolProperty(name="Re-Align Group Empty", default=False)
    location: EnumProperty(name="Location", items=group_location_items, default='AVERAGE')
    rotation: EnumProperty(name="Rotation", items=group_location_items, default='WORLD')
    @classmethod
    def poll(cls, context):
        if context.mode == 'OBJECT' and not context.scene.M3.group_origin_mode:
            return True

    def draw(self, context):
        layout = self.layout

        column = layout.column()

        column.prop(self, 'realign_group_empty', toggle=True)

        row = column.row()
        row.active = self.realign_group_empty
        row.prop(self, 'location', expand=True)

        row = column.row()
        row.active = self.realign_group_empty
        row.prop(self, 'rotation', expand=True)

    def invoke(self, context, event):
        get_mouse_pos(self, context, event, hud_offset=(0, 20))
        return self.execute(context)

    def execute(self, context):
        debug = False

        all_group_objects = [obj for obj in context.selected_objects if obj.M3.is_group_object]

        group_objects = [obj for obj in all_group_objects if obj.parent not in all_group_objects]

        if debug:
            print()
            print("all group objects", [obj.name for obj in all_group_objects])
            print("    group objects", [obj.name for obj in group_objects])

        if group_objects:

            empties = set()

            for obj in group_objects:
                empties.add(obj.parent)

                unparent(obj)
                obj.M3.is_group_object = False

            if self.realign_group_empty:
                for e in empties:
                    children = [c for c in e.children]

                    if children:
                        gmx = get_group_matrix(context, children, self.location, self.rotation)

                        compensate_children(e, e.matrix_world, gmx)

                        e.matrix_world = gmx

            clean_up_groups(context)

            text = f"Removed {len(group_objects)} objects from their group"
            draw_fading_label(context, text=text, x=self.HUD_x, y=self.HUD_y, color=red, time=get_prefs().HUD_fade_group)

            return {'FINISHED'}
        return {'CANCELLED'}

class ToggleGroupMode(bpy.types.Operator):
    bl_idname = "machin3.toggle_outliner_group_mode"
    bl_label = "MACHIN3: Toggle Outliner Group Mode"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and is_outliner(context)

    def execute(self, context):
        area = context.area
        space = area.spaces[0]

        init_state = context.workspace.get('outliner_group_mode_toggle', False)

        if init_state:

            for name, prop in init_state.items():

                if name == 'M3':
                    for n, p in prop.items():
                        setattr(context.scene.M3, n, p)

                elif name == 'VISIBILITY':
                    for groupname, vis in prop.items():
                        if group := bpy.data.objects.get(groupname):
                            del vis['select']
                            restore_visibility(group, vis)

                        else:
                            print(f"WARNING: Couldn't find group empty {groupname}, skipped restoring visibility",)

                else:
                    setattr(space, name, prop)

            del init_state['M3']
            del context.workspace['outliner_group_mode_toggle']

            clean_up_groups(context)

        else:
            groups = [(obj, visible_get(obj)) for obj in context.view_layer.objects if obj.M3.is_group_empty]

            if groups:
                ensure_internal_index_group_name([obj for obj, _ in groups])

                init_state = {
                    'display_mode': space.display_mode,

                    'show_restrict_column_enable': space.show_restrict_column_enable,
                    'show_restrict_column_select': space.show_restrict_column_select,
                    'show_restrict_column_hide': space.show_restrict_column_hide,
                    'show_restrict_column_viewport': space.show_restrict_column_viewport,
                    'show_restrict_column_render': space.show_restrict_column_render,
                    'show_restrict_column_holdout': space.show_restrict_column_holdout,
                    'show_restrict_column_indirect_only': space.show_restrict_column_indirect_only,

                    'use_sort_alpha': space.use_sort_alpha,
                    'use_sync_select': space.use_sync_select,
                    'show_mode_column': space.show_mode_column,

                    'use_filter_complete': space.use_filter_complete,
                    'use_filter_case_sensitive': space.use_filter_case_sensitive,

                    'use_filter_view_layers': space.use_filter_view_layers,
                    'use_filter_collection': space.use_filter_collection,
                    'use_filter_object_mesh': space.use_filter_object_mesh,
                    'use_filter_object_content': space.use_filter_object_content,
                    'use_filter_object_armature': space.use_filter_object_armature,
                    'use_filter_object_light': space.use_filter_object_light,
                    'use_filter_object_camera': space.use_filter_object_camera,
                    'use_filter_object_others': space.use_filter_object_others,
                    'use_filter_object_grease_pencil': space.use_filter_object_grease_pencil,
                    'use_filter_object_empty': space.use_filter_object_empty,
                    'use_filter_children': space.use_filter_children,

                    'filter_state': space.filter_state,
                    'filter_text': space.filter_text,

                    'M3': {
                        'group_select': context.scene.M3.group_select,
                        'group_recursive_select': context.scene.M3.group_recursive_select,
                        'group_hide': context.scene.M3.group_hide,
                        'draw_group_relations': context.scene.M3.draw_group_relations
                    },

                    'VISIBILITY': {obj.name: vis for obj, vis in groups}
                }

                context.workspace['outliner_group_mode_toggle'] = init_state

                ensure_visibility(context, [obj for obj, vis in groups if not vis['visible']])

                if space.display_mode != 'VIEW_LAYER':
                    space.display_mode = 'VIEW_LAYER'

                space.show_restrict_column_enable = False
                space.show_restrict_column_select = True
                space.show_restrict_column_hide = True
                space.show_restrict_column_viewport = False
                space.show_restrict_column_render = False
                space.show_restrict_column_holdout = False
                space.show_restrict_column_indirect_only = False

                space.use_sort_alpha = True
                space.use_sync_select = True
                space.show_mode_column = True

                space.use_filter_complete = True
                space.use_filter_case_sensitive = True

                space.use_filter_view_layers = False
                space.use_filter_collection = False
                space.use_filter_object_mesh = False
                space.use_filter_object_content = False
                space.use_filter_object_armature = False
                space.use_filter_object_light = False
                space.use_filter_object_camera = False
                space.use_filter_object_others = False
                space.use_filter_object_grease_pencil = False
                space.use_filter_object_empty = True

                space.use_filter_children = True

                space.filter_state = 'ALL'

                if get_prefs().group_tools_auto_name:

                    empties = {obj for obj in context.view_layer.objects if obj.type == 'EMPTY'}
                    groups = {obj for obj in empties if obj.M3.is_group_empty}

                    if empties - groups:

                        has_prefix = False
                        has_suffix = False

                        for obj in groups:
                            prefix, basename, suffix = get_group_base_name(obj.name, debug=False)

                            if has_prefix is False and prefix:
                                has_prefix = True

                            if has_suffix is False and suffix:
                                has_suffix = True

                        if has_suffix and (suffix := get_prefs().group_tools_suffix) and has_prefix and (prefix := get_prefs().group_tools_prefix):
                            space.filter_text = f"{prefix}*{suffix}"

                        elif has_suffix and (suffix := get_prefs().group_tools_suffix):
                            space.filter_text = f"*{suffix}"

                        elif has_prefix and (prefix := get_prefs().group_tools_prefix):
                            space.filter_text = f"{prefix}*"

                if get_prefs().group_tools_group_mode_disable_auto_select:
                    context.scene.M3.group_select = False

                if get_prefs().group_tools_group_mode_disable_recursive_select:
                    context.scene.M3.group_recursive_select = False

                if get_prefs().group_tools_group_mode_disable_group_hide:
                    context.scene.M3.group_hide = False

                if get_prefs().group_tools_group_mode_enable_group_draw_relations:
                    context.scene.M3.draw_group_relations = True

            else:
                print("WARNING: Can't toggle Outliner into Group Mode, as there aren't any group objects!")

        return {'FINISHED'}

class ExpandOutliner(bpy.types.Operator):
    bl_idname = "machin3.expand_outliner"
    bl_label = "MACHIN3: Expand Outliner"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_outliner(context)

    def execute(self, context):
        bpy.ops.outliner.show_hierarchy()

        depth = get_collection_depth(self, [context.scene.collection], init=True)

        for i in range(depth):
            bpy.ops.outliner.show_one_level(open=True)

        return {'FINISHED'}

class CollapseOutliner(bpy.types.Operator):
    bl_idname = "machin3.collapse_outliner"
    bl_label = "MACHIN3: Collapse Outliner"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_outliner(context)

    def execute(self, context):
        col_depth = get_collection_depth(self, [context.scene.collection], init=True)

        child_depth = get_child_depth(self, [obj for obj in context.scene.objects if obj.children], init=True)

        for i in range(max(col_depth, child_depth) + 2):
            bpy.ops.outliner.show_one_level(open=False)

        return {'FINISHED'}

class ToggleChildren(bpy.types.Operator):
    bl_idname = "machin3.toggle_outliner_children"
    bl_label = "MACHIN3: Toggle Outliner Children"
    bl_description = ""
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_outliner(context)

    def execute(self, context):
        area = context.area
        space = area.spaces[0]

        space.use_filter_children = not space.use_filter_children
        return {'FINISHED'}
