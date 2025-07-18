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

# Copyright 2023, Valeriy Yatsenko

""" Zen Checker Files Pocessor """

from struct import unpack
import imghdr
import os
from shutil import copy
from json import dumps
import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator
from bpy.props import StringProperty

from .zen_checker_labels import ZCheckerLabels as label
from .get_prefs import get_prefs

from ZenUV.utils.messages import zen_message
from ZenUV.utils.vlog import Log
from ZenUV.utils.register_util import RegisterUtils


_checker_previews = None


def get_checker_previews():
    global _checker_previews
    if _checker_previews is None:
        import bpy.utils.previews
        _checker_previews = bpy.utils.previews.new()
    return _checker_previews


def load_checker_image(context, _image):

    addon_prefs = get_prefs().uv_checker_props
    image_file = os.path.join(addon_prefs.checker_assets_path, _image)
    current_image = bpy.data.images.get(_image)
    if current_image and not current_image.has_data:
        bpy.data.images.remove(current_image, do_unlink=True)
    if os.path.exists(image_file):
        try:
            p_image = bpy.data.images.load(image_file, check_existing=True)
            return p_image
        except Exception as e:
            print(e)

            Log.debug('TexChecker', f'image is {_image}. Error In "load_checker_image')
            bpy.ops.wm.call_menu(name="ZUV_MT_ZenChecker_Popup")

            return None
    else:
        if _image != "None":
            print("Zen Checker: file not exist ", image_file)
            zen_message(context, message="File not exist:" + image_file, title="Zen Checker")
        return None


def get_image_size(fname):
    '''Determine the image type of fhandle and return its size.
    from draco'''
    with open(fname, 'rb') as fhandle:
        head = fhandle.read(24)
        if len(head) != 24:
            return
        if imghdr.what(fname) == 'png':
            check = unpack('>i', head[4:8])[0]
            if check != 0x0d0a1a0a:
                return
            width, height = unpack('>ii', head[16:24])
        # elif imghdr.what(fname) == 'gif':
        #     width, height = unpack('<HH', head[6:10])
        elif imghdr.what(fname) == 'jpeg':
            try:
                fhandle.seek(0)  # Read 0xff next
                size = 2
                ftype = 0
                while not 0xc0 <= ftype <= 0xcf:
                    fhandle.seek(size, 1)
                    byte = fhandle.read(1)
                    while ord(byte) == 0xff:
                        byte = fhandle.read(1)
                    ftype = ord(byte)
                    size = unpack('>H', fhandle.read(2))[0] - 2
                # We are at a SOFn block
                fhandle.seek(1, 1)  # Skip `precision' byte.
                height, width = unpack('>HH', fhandle.read(4))
            except Exception:  # IGNORE:W0703
                return
        else:
            return
        return width, height


def collect_image_names(path):
    """ Read files from Zen Checker .images directory """
    checker_images = []
    if os.path.exists(path):
        for _file in os.listdir(path=path):
            if _file.endswith(".png") or _file.endswith(".jpg"):
                checker_images.append(_file)
    else:
        print("Zen UV: Folder ../Images not exist")
    return checker_images


def update_files_info(path):
    """ Update info of files from Zen Checker .images directory """
    files_dict = dict()
    files = collect_image_names(path)
    if files:
        p_previews = get_checker_previews()
        p_previews.clear()

        for _file in files:
            # print("Update File Info:", _file)
            files_dict[_file] = dict()
            p_path = os.path.join(path, _file)
            files_dict[_file]["res_x"], files_dict[_file]["res_y"] = get_image_size(p_path)

            try:
                p_previews.load(_file, p_path, 'IMAGE')
            except Exception as e:
                print(str(e))

    # print(files_dict)
    return files_dict


class ZUVChecker_OT_CollectImages(Operator):
    """ Zen UV Checker Collect files data """
    bl_idname = "view3d.zenuv_checker_collect_images"
    bl_label = label.OT_COLLECT_IMAGES_LABEL
    bl_description = label.OT_COLLECT_IMAGES_DESC
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        addon_prefs = get_prefs().uv_checker_props
        path = addon_prefs.checker_assets_path
        addon_prefs.files_dict = dumps(update_files_info(path))
        return {'FINISHED'}


class ZUVChecker_OT_AppendFile(Operator, ImportHelper):
    bl_idname = "view3d.zenuv_checker_append_checker_file"
    bl_label = label.OT_APPEND_CHECKER_LABEL
    bl_description = label.OT_APPEND_CHECKER_DESC

    filter_glob: StringProperty(
        default='*.jpg;*.png',
        options={'HIDDEN'}
    )

    def execute(self, context):
        addon_prefs = get_prefs().uv_checker_props
        path = addon_prefs.checker_assets_path
        # Copy User Image to
        copy(self.filepath, path)
        print("ZChecker: File ", self.filepath)
        print("          Copied to: ", path)
        addon_prefs.files_dict = dumps(update_files_info(path))
        return {'FINISHED'}


class ZUVChecker_OT_GetCheckerOverrideImage(bpy.types.Operator):
    bl_idname = 'wm.zenuv_get_checker_override_image'
    bl_label = 'Get Override Image'
    bl_description = 'Get texture checker override image'
    bl_options = {'REGISTER'}

    def get_items(self, context: bpy.types.Context):
        p_items = []
        for k, v in bpy.data.images.items():
            p_items.append((k, k, ""))

        s_id = "ZUVChecker_OT_GetCheckerOverrideImage_ITEMS"
        p_was_items = bpy.app.driver_namespace.get(s_id, [])

        if p_was_items != p_items:
            bpy.app.driver_namespace[s_id] = p_items

        return bpy.app.driver_namespace.get(s_id, [])

    image_name: bpy.props.EnumProperty(
        name='Image Name',
        description='Source image name, which will be used for checker image',
        items=get_items
    )

    def get_image_size(self):
        p_image = bpy.data.images.get(self.image_name, None)
        if p_image:
            return p_image.size
        return (0, 0)

    @classmethod
    def getActiveImage(cls, context):
        from ZenUV.ops.trimsheets.trimsheet_utils import ZuvTrimsheetUtils
        p_image = ZuvTrimsheetUtils.getSpaceDataImage(context)
        if p_image is not None:
            return p_image

        if hasattr(context, 'area') and context.area is not None and context.area.type != 'IMAGE_EDITOR':
            if context.active_object is not None:
                p_act_mat = context.active_object.active_material
                if p_act_mat is not None:
                    if p_act_mat.use_nodes:
                        # Priority for Base Color Texture
                        try:
                            principled = next(n for n in p_act_mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
                            base_color = principled.inputs['Base Color']
                            link = base_color.links[0]
                            link_node = link.from_node
                            return link_node.image
                        except Exception:
                            pass

        return None

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        p_image = self.getActiveImage(context)
        if p_image:
            try:
                self.image_name = p_image.name
            except Exception as e:
                Log.error('DETECT IMAGE:', e)

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        from .checker import zen_checker_image_update, get_zen_checker_image

        context.scene.zen_uv_checker.override_image_name = self.image_name
        image = get_zen_checker_image(context)
        if image is not None:
            zen_checker_image_update(context, image)
            return {'FINISHED'}
        return {'CANCELLED'}


classes = [
    ZUVChecker_OT_CollectImages,
    ZUVChecker_OT_AppendFile,
    ZUVChecker_OT_GetCheckerOverrideImage
]


def register():
    RegisterUtils.register(classes)


def unregister():
    RegisterUtils.unregister(classes)
