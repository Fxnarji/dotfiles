from typing import Union
import bpy

from mathutils import Vector, Quaternion

import re

from . math import average_locations, get_loc_matrix, get_rot_matrix
from . mesh import get_coords, get_eval_mesh
from . view import is_obj_on_viewlayer

from . import object as o
from . import registration as r

def group(context, sel, location='AVERAGE', rotation='WORLD'):
    col = get_group_collection(context, sel)

    empty = bpy.data.objects.new(name=get_group_default_name(), object_data=None)
    empty.M3.is_group_empty = True
    empty.matrix_world = get_group_matrix(context, sel, location, rotation)
    col.objects.link(empty)

    context.view_layer.objects.active = empty
    empty.select_set(True)
    empty.show_in_front = True
    empty.empty_display_type = 'CUBE'

    empty.show_name = True
    empty.empty_display_size = r.get_prefs().group_tools_size

    empty.M3.group_size = r.get_prefs().group_tools_size

    for obj in sel:
        o.parent(obj, empty)
        obj.M3.is_group_object = True

    return empty

def ungroup(empty, depsgraph=None):
    if depsgraph is None:
        depsgraph = bpy.context.evaluated_depsgraph_get()

    locations = []
    batches = []

    for obj in empty.children:

        if is_obj_on_viewlayer(obj):

            if obj.M3.is_group_empty:
                locations.append(obj.matrix_world.to_translation())

            elif obj.M3.is_group_object:

                if obj.type in ['MESH', 'CURVE', 'SURFACE', 'META', 'FONT']:
                    mesh_eval = get_eval_mesh(depsgraph, obj, data_block=False)
                    batches.append(get_coords(mesh_eval, mx=obj.matrix_world, indices=True))

        o.unparent(obj)

        obj.M3.is_group_object = False

    bpy.data.objects.remove(empty, do_unlink=True)

    return locations, batches

def clean_up_groups(context):
    empties = []
    top_empties = []

    for obj in context.scene.objects:

        if obj.library:
            continue

        if obj.M3.is_group_empty:

            empties.append(obj)

            if r.get_prefs().group_tools_remove_empty and not obj.children:
                print("INFO: Removing empty Group", obj.name)
                bpy.data.objects.remove(obj, do_unlink=True)
                continue

            if obj.parent:
                if obj.parent.M3.is_group_empty and not obj.M3.is_group_object:
                    obj.M3.is_group_object = True
                    print(f"INFO: {obj.name} is now a group object, because it was manually parented to {obj.parent.name}")

            else:
                top_empties.append(obj)

        elif obj.M3.is_group_object:
            if obj.parent:

                if not obj.parent.M3.is_group_empty:
                    obj.M3.is_group_object = False
                    print(f"INFO: {obj.name} is no longer a group object, because it's parent {obj.parent.name} is not a group empty")

            else:
                obj.M3.is_group_object = False
                print(f"INFO: {obj.name} is no longer a group object, because it doesn't have any parent")

        elif not obj.M3.is_group_object and obj.parent and obj.parent.M3.is_group_empty:
            obj.M3.is_group_object = True
            print(f"INFO: {obj.name} is now a group object, because it was manually parented to {obj.parent.name}")

            empties.append(obj)

    ensure_internal_index_group_name(empties)
    return top_empties

def get_group_polls(context):
    active_group = active if (active := context.active_object) and active.M3.is_group_empty and active.select_get() else None
    active_child = active if (active := context.active_object) and active.parent and active.M3.is_group_object and active.select_get() else None

    has_group_empties = bool([obj for obj in context.view_layer.objects if obj.M3.is_group_empty])
    has_visible_group_empties = bool([obj for obj in context.visible_objects if obj.M3.is_group_empty])

    is_groupable = bool([obj for obj in context.selected_objects if (obj.parent and obj.parent.M3.is_group_empty) or not obj.parent])
    is_ungroupable = bool([obj for obj in context.selected_objects if obj.M3.is_group_empty]) if has_group_empties else False

    is_addable = bool([obj for obj in context.selected_objects if obj != (active_group if active_group else active_child.parent) \
        and obj not in (active_group.children if active_group else active_child.parent.children) \
        and (not obj.parent or (obj.parent and obj.parent.M3.is_group_empty and not obj.parent.select_get()))]) if active_group or active_child else False

    is_removable = bool([obj for obj in context.selected_objects if obj.M3.is_group_object])
    is_selectable = bool([obj for obj in context.selected_objects if obj.M3.is_group_empty or obj.M3.is_group_object])
    is_duplicatable = bool([obj for obj in context.selected_objects if obj.M3.is_group_empty])
    is_groupifyable = bool([obj for obj in context.selected_objects if obj.type == 'EMPTY' and not obj.M3.is_group_empty and obj.children])

    is_batchposable = False

    return bool(active_group), bool(active_child), has_group_empties, has_visible_group_empties, is_groupable, is_ungroupable, is_addable, is_removable, is_selectable, is_duplicatable, is_groupifyable, is_batchposable

def get_group_collection(context, sel):
    collections = set(col for obj in sel for col in obj.users_collection)

    if len(collections) == 1:
        return collections.pop()

    else:
        return context.scene.collection

def get_group_matrix(context, objects, location_type='AVERAGE', rotation_type='WORLD'):

    if location_type == 'AVERAGE':
        location = average_locations([obj.matrix_world.to_translation() for obj in objects])

    elif location_type == 'ACTIVE':
        if context.active_object:
            location = context.active_object.matrix_world.to_translation()

        else:
            location = average_locations([obj.matrix_world.to_translation() for obj in objects])

    elif location_type == 'CURSOR':
        location = context.scene.cursor.location

    elif location_type == 'WORLD':
        location = Vector()

    if rotation_type == 'AVERAGE':
        rotation = Quaternion(average_locations([obj.matrix_world.to_quaternion().to_exponential_map() for obj in objects]))

    elif rotation_type == 'ACTIVE':
        if context.active_object:
            rotation = context.active_object.matrix_world.to_quaternion()

        else:
            rotation = Quaternion(average_locations([obj.matrix_world.to_quaternion().to_exponential_map() for obj in objects]))

    elif rotation_type == 'CURSOR':
        rotation = context.scene.cursor.matrix.to_quaternion()

    elif rotation_type == 'WORLD':
        rotation = Quaternion()

    return get_loc_matrix(location) @ get_rot_matrix(rotation)

def select_group_children(view_layer, empty, recursive=False):
    children = [c for c in empty.children if c.M3.is_group_object and c.name in view_layer.objects]

    if empty.hide_get():
        empty.hide_set(False)

        if empty.visible_get(view_layer=view_layer) and not empty.select_get(view_layer=view_layer):
            empty.select_set(True)

    for obj in children:
        if obj.visible_get(view_layer=view_layer) and not obj.select_get(view_layer=view_layer):
            obj.select_set(True)

        if obj.M3.is_group_empty and recursive:
            select_group_children(view_layer, obj, recursive=True)

def get_child_depth(self, children, depth=0, init=False):
    if init or depth > self.depth:
        self.depth = depth

    for child in children:
        if child.children:
            get_child_depth(self, child.children, depth + 1, init=False)

    return self.depth

def fade_group_sizes(context, size=None, groups=[], init=False):
    if init:
        groups = [obj for obj in context.scene.objects if obj.M3.is_group_empty and not obj.parent]

    for group in groups:
        if size:
            factor = r.get_prefs().group_tools_fade_factor

            group.empty_display_size = factor * size
            group.M3.group_size = group.empty_display_size

        sub_groups = [c for c in group.children if c.M3.is_group_empty]

        if sub_groups:
            fade_group_sizes(context, size=group.M3.group_size, groups=sub_groups, init=False)

def get_group_default_name():
    p = r.get_prefs()

    basename = p.group_tools_basename

    if r.get_prefs().group_tools_auto_name:
        name = f"{p.group_tools_prefix}{basename}{p.group_tools_suffix}"

        c = 0

        while bpy.data.objects.get(name):
            c += 1
            name = f"{p.group_tools_prefix}{basename}.{str(c).zfill(3)}{p.group_tools_suffix}"
        return name

    else:
        return basename

def get_group_base_name(name, remove_index=True, debug=False):

    basename = name

    if remove_index:
        indexRegex = re.compile(r"\.[\d]{3}")
        matches = indexRegex.findall(name)

        basename = name

        if matches:
            for match in matches:
                basename = basename.replace(match, '')

    if debug:
        if basename == name:
            print(" passed in name is basename:", basename)
        else:
            print(" re-constructed basename:", basename)

    p = r.get_prefs()

    if r.get_prefs().group_tools_auto_name:
        if (prefix := p.group_tools_prefix) and basename.startswith(prefix):
            basename = basename[len(prefix):]

        else:
            prefix = None

        if (suffix := p.group_tools_suffix) and basename.endswith(suffix):
            basename = basename[:-len(suffix)]
        else:
            suffix = None

        if debug:
            print()
            print("name:", name)
            print("prefix:", prefix)
            print("basename:", basename)
            print("suffix:", suffix)

        return prefix, basename, suffix
    else:
        return None, name, None

def set_unique_group_name(group):
    _, basename, _ = get_group_base_name(group.name, debug=False)

    p = r.get_prefs()

    if p.group_tools_auto_name:
        name = f"{p.group_tools_prefix}{basename}{p.group_tools_suffix}"

        if group.name != name:

            c = 0

            while obj := bpy.data.objects.get(name):
                if obj == group:
                    return

                c += 1
                name = f"{p.group_tools_prefix}{basename}.{str(c).zfill(3)}{p.group_tools_suffix}"

            group.name = name

    elif group.name != basename:
        group.name = basename

def ensure_internal_index_group_name(group:Union[bpy.types.Object, list[bpy.types.Object], set[bpy.types.Object]]):
    p = r.get_prefs()

    if p.group_tools_auto_name and p.group_tools_suffix:
        groups = [group] if type(group) is bpy.types.Object else group

        indexRegex = re.compile(r".*(\.[\d]{3})$")

        for group in groups:
            if o.is_valid_object(group):
                mo = indexRegex.match(group.name)

                if mo:
                    set_unique_group_name(group)

            else:
                print(f"WARNING: Encountered Invalid Object Reference '{str(group)}' when trying to set unique object name")

def init_group_origin_adjustment(context):
    m3 = context.scene.M3

    m3['group_origin_mode_toggle'] = {
        'group_select': m3.group_select,
        'group_recursive_select': m3.group_recursive_select,
        'group_hide': m3.group_hide,

        'draw_group_relations': m3.draw_group_relations,
        'draw_group_relations_objects': m3.draw_group_relations_objects
    }

    context.scene.tool_settings.use_transform_skip_children = True

    m3.group_select = False
    m3.group_recursive_select = False
    m3.group_hide = False

    m3.draw_group_relations = True
    m3.draw_group_relations_objects = True

def finish_group_origin_adjustment(context):
    m3 = context.scene.M3

    context.scene.tool_settings.use_transform_skip_children = False

    if init_state := m3.get('group_origin_mode_toggle'):
        for name, prop in init_state.items():
            setattr(m3, name, prop)

        del m3['group_origin_mode_toggle']

    else:
        m3.group_select = True
        m3.group_recursive_select = True
        m3.group_hide = True

        m3.draw_group_relations = False
        m3.draw_group_relations_objects = False

def get_group_relation_coords(context, active, others):
    is_draw_objects = context.scene.M3.draw_group_relations_objects

    active_coords = {
        'co': None,
        'vectors': [],
        'origins': []
    }

    other_coords = {
        'coords_visible': [],
        'coords_hidden': [],

        'group_lines': []
    }

    object_coords = {

        'vectors': [],
        'origins': [],

        'coords': []
    }

    group_objects = []

    if active:
        co = active.matrix_world.to_translation()
        active_coords['co'] = co

        children = {obj for obj in active.children if is_obj_on_viewlayer(obj)}
        groups = {obj for obj in children if obj.M3.is_group_empty}

        active_coords['vectors'] = [obj.matrix_world.to_translation() - co for obj in groups]
        active_coords['origins'] = [co for obj in groups]

        if is_draw_objects:
            group_objects.append((co, children - groups))

    if others:
        other_coords['coords'] = [obj.matrix_world.to_translation() for obj in others]

        for obj in others:
            co = obj.matrix_world.to_translation()

            if obj.visible_get():
                other_coords['coords_visible'].append(co)
            else:
                other_coords['coords_hidden'].append(co)

            children = {ob for ob in obj.children if is_obj_on_viewlayer(ob)}
            groups = {ob for ob in children if ob.M3.is_group_empty}

            other_coords['group_lines'].extend([coord for ob in groups for coord in [co, ob.matrix_world.to_translation()]])

            if is_draw_objects:
                group_objects.append((co, children - groups))

        if active:
            for vector in active_coords['vectors']:
                other_coords['group_lines'].extend([active_coords['co'], active_coords['co'] + vector])

    if context.scene.M3.draw_group_relations_objects:
        for co, objects in group_objects:
            for obj in objects:
                if obj.visible_get():

                    obj_co = obj.matrix_world.to_translation()

                    object_coords['vectors'].append(obj_co - co)
                    object_coords['origins'].append(co)

                    object_coords['coords'].append(obj_co)

    return active_coords, other_coords, object_coords
