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

"""Zen UV Transform utils """
import bpy
import bmesh
import numpy as np
from functools import reduce
from math import sin, cos, pi
from mathutils import Vector, Matrix, Quaternion
from ZenUV.utils.generic import (
    resort_objects_by_selection,
    verify_uv_layer
)
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils import get_uv_islands as island_util
# from ZenUV.utils.vlog import Log
from ZenUV.utils.constants import UV_AREA_BBOX


def ZenLocRotScale(location: Vector = None, rotation: Quaternion = None, scale: Vector = None) -> Matrix:
    """
        Create a matrix combining translation, rotation and scale, acting as the inverse of the decompose() method.
        Any of the inputs may be replaced with None if not needed.
        :param loc: (Vector or None) The translation component.
        :param rot: (Quaternion or None) The rotation component.
        :param sca: (Vector or None) The scale component.
        Returns: Combined transformation matrix.
        Return type: Matrix(4x4)
    """
    if bpy.app.version >= (3, 0, 0):
        return Matrix.LocRotScale(location, rotation, scale)
    else:
        mtx_array = []
        if location is not None:
            mtx_array.append(Matrix.Translation(location))
        if rotation is not None:
            mtx_array.append(rotation.normalized().to_matrix().to_4x4())
        if scale is not None:
            mtx_array.append(Matrix.Diagonal(scale).to_4x4())

        if len(mtx_array) == 0:
            return Matrix()

        return reduce(lambda x, y: x @ y, mtx_array)


def align_vertical(points, increment_angle=0, base_direction="tl"):
    from ZenUV.ops.transform_sys.transform_utils.transform_uvs import TransformUVS

    angle = zen_box_fit_2d(points)

    rotated_points = TransformUVS.rotate_uvs(points, angle, (0.0, 0.0))

    bbox = BoundingBox2d(points=rotated_points)
    if bbox.len_x > bbox.len_y:
        angle += pi / 2
    return angle


def align_horizontal(points, increment_angle=0, base_direction="tl"):
    return align_vertical(points) + pi / 2


def calculate_fit_scale(pp_pos, padding, bbox, keep_proportion=True, bounds=Vector((1.0, 1.0))):

    if isinstance(bbox, dict):
        bbox_len_x = bbox['len_x'] if bbox['len_x'] != 0.0 else 1.0
        bbox_len_y = bbox['len_y'] if bbox['len_y'] != 0.0 else 1.0

    else:
        bbox_len_x = bbox.len_x if bbox.len_x != 0.0 else 1.0
        bbox_len_y = bbox.len_y if bbox.len_y != 0.0 else 1.0

    factor_u = (bounds.x - padding * 2) / bbox_len_x
    factor_v = (bounds.y - padding * 2) / bbox_len_y

    # Check fit proportions
    if keep_proportion:
        # Scale to fit bounds
        min_factor = min(factor_u, factor_v)
        scale = (min_factor, min_factor)

        # Scale to fit one side
        if pp_pos in ("lc", "rc"):
            scale = (factor_v, factor_v)
        elif pp_pos in ("tc", "bc"):
            scale = (factor_u, factor_u)
    else:
        scale = (factor_u, factor_v)
    return scale


def get_bbox(context, from_selection=False):
    objs = resort_objects_by_selection(context, context.objects_in_mode)
    bb = []
    for obj in objs:
        bm = bmesh.from_edit_mesh(obj.data)
        uv_layer = verify_uv_layer(bm)
        if from_selection:
            islands = island_util.get_islands_selected_only(bm, [f for f in bm.faces if f.select])
        else:
            islands = island_util.get_island(context, bm, uv_layer)
        if islands:
            cbbox = bound_box(islands=islands, uv_layer=uv_layer)
            bb.extend((cbbox["bl"], cbbox["tr"]))
    gbb = bound_box(points=bb)
    if gbb["len_x"] + gbb["len_y"] == 0:
        gbb = UV_AREA_BBOX.get_as_dict()

    return gbb


def centroid_legacy(vertexes):
    """ Calculate Centroid of the given vertices set """
    # vertexes = zen_convex_hull_2d(vertexes)
    x_list = [vertex[0] for vertex in vertexes]
    y_list = [vertex[1] for vertex in vertexes]
    length = len(vertexes)
    if length == 0:
        length = 1
    x = sum(x_list) / length
    y = sum(y_list) / length
    return Vector((x, y))


def centroid(arr):
    if not len(arr):
        return Vector.Fill(2, 0)
    return Vector((sum(v[0] for v in arr) / len(arr), sum(v[1] for v in arr) / len(arr)))


def centroid_3d(vertexes):
    """ Calculate Centroid of the given vertices set """
    # vertexes = zen_convex_hull_2d(vertexes)
    x_list = [vertex[0] for vertex in vertexes]
    y_list = [vertex[1] for vertex in vertexes]
    z_list = [vertex[2] for vertex in vertexes]
    length = len(vertexes)
    if length == 0:
        length = 1
    x = sum(x_list) / length
    y = sum(y_list) / length
    z = sum(z_list) / length
    return Vector((x, y, z))


def bound_box(islands=None, points=None, uv_layer=None):
    """ Return Dict with bbox parameters as Vectors
    bl: bottom left
    tl: top left
    tr: top right
    br: bottom right
    cen: center
    len_x: length by X
    len_y: length by Y
"""
    minX = +1000
    minY = +1000
    maxX = -1000
    maxY = -1000
    if islands and uv_layer:
        points = []
        for island in islands:
            points.extend([loop[uv_layer].uv for face in island for loop in face.loops])
    if points:
        points = zen_convex_hull_2d(points)
        for point in points:
            u, v = point
            minX = min(u, minX)
            minY = min(v, minY)
            maxX = max(u, maxX)
            maxY = max(v, maxY)
    if minX == +1000 and minY == +1000 and maxX == -1000 and maxY == -1000:
        minX = minY = maxX = maxY = 0
    bbox = {
        "bl": Vector((minX, minY)),
        "tl": Vector((minX, maxY)),
        "tr": Vector((maxX, maxY)),
        "br": Vector((maxX, minY)),
        "cen": (Vector((minX, minY)) + Vector((maxX, maxY))) / 2,
        "tc": (Vector((minX, maxY)) + Vector((maxX, maxY))) / 2,
        "rc": (Vector((maxX, maxY)) + Vector((maxX, minY))) / 2,
        "bc": (Vector((maxX, minY)) + Vector((minX, minY))) / 2,
        "lc": (Vector((minX, minY)) + Vector((minX, maxY))) / 2,
        "len_x": (Vector((maxX, maxY)) - Vector((minX, maxY))).length,
        "len_y": (Vector((minX, minY)) - Vector((minX, maxY))).length
    }
    return bbox


def scale2d(v, s, p):
    """ v - coordinates; s - scale by axis [x,y]; p - anchor point """
    return (p[0] + s[0] * (v[0] - p[0]), p[1] + s[1] * (v[1] - p[1]))


def make_rotation_transformation(angle, origin=(0, 0)):
    """ Calculate rotation transformation by the angle and origin """
    cos_theta, sin_theta = cos(angle), sin(angle)
    x0, y0 = origin

    def xform(point):
        x, y = point[0] - x0, point[1] - y0
        return (x * cos_theta - y * sin_theta + x0,
                x * sin_theta + y * cos_theta + y0)
    return xform


def rotate_island(island, uv_layer, angle, anchor):
    """ Perform rotation of the given island """
    rotated = make_rotation_transformation(angle, anchor)
    loops = [lp for face in island for lp in face.loops]
    for loop in loops:
        loop[uv_layer].uv = rotated(loop[uv_layer].uv)


def rotate_loops(loops, uv_layer, angle, anchor):
    """ Perform rotation of the given loops """
    # print("Island turned to :", angle)
    rotated = make_rotation_transformation(angle, anchor)
    for loop in loops:
        loop[uv_layer].uv = rotated(loop[uv_layer].uv)


def move_island(island: list, uv_layer, offset: Vector = Vector((0, 0))) -> None:
    """ Move the island by defined offset """
    loops = {loop[uv_layer]: loop[uv_layer].uv for f in island for loop in f.loops}
    for loop, uv in zip(loops.keys(), np.array(list(loops.values()), dtype=Vector) + offset):
        loop.uv = uv


def zen_convex_hull_2d(points: list) -> list:
    from mathutils.geometry import convex_hull_2d

    if len(points) > 2:
        return [points[i] for i in convex_hull_2d(points)]
    return points


def zen_box_fit_2d(points) -> float:
    ''' Returns an angle that best fits the points to an axis aligned rectangle.
        Fix Blender box_fit_2d issue with 2 points convex hull. '''
    from mathutils.geometry import box_fit_2d
    if len(points) <= 2:
        bbox = BoundingBox2d(points=points)
        if bbox.len_x != 0.0:
            return box_fit_2d(points)
        else:
            return 0.0
    else:
        return box_fit_2d(points)


def matrix_by_image_aspect(image_aspect):
    if image_aspect > 1.0:
        return Matrix.Diagonal((1, 1 / image_aspect))
    elif image_aspect < 1.0:
        return Matrix.Diagonal((image_aspect, 1))
    else:
        return Matrix.Diagonal((1, 1))


def vector_by_image_aspect(image_aspect):
    if image_aspect > 1.0:
        return Vector((1, 1 / image_aspect))
    elif image_aspect < 1.0:
        return Vector((image_aspect, 1))
    else:
        return Vector((1, 1))


class LoopsOriginVector:
    ''' Loops Origin Vector used in UvTransformUtils._get_origin_vector_from_loops() '''

    def __init__(self, head_loop: Vector, tail_loop: Vector, uv_layer) -> None:
        self.head_loop_index = head_loop.index
        self.tail_loop_index = tail_loop.index
        self.edge_index = head_loop.edge.index

        self.pivot_location = head_loop[uv_layer].uv.copy()
        self.tail_location = tail_loop[uv_layer].uv.copy()
        self.direction = (self.tail_location - self.pivot_location)


class UvTransformUtils:

    @classmethod
    def _get_origin_vector_from_loops(self):

        near_dict = {abs((self.bbox.center - lp[self.uv_layer].uv).magnitude): lp for lp in self.loops.values()}
        origin_loop = near_dict[min(near_dict.keys())]

        near_loops = [lp for lp in origin_loop.vert.link_loops if lp.face in self.island]

        angled_loops = {}
        for loop in near_loops:
            for _next in (loop.link_loop_next, loop.link_loop_prev):
                for axis in (Vector((1.0, 0.0)), Vector((-1.0, 0.0)), Vector((0.0, 1.0)), Vector((0.0, -1.0))):
                    angled_loops.update({axis.angle(_next[self.uv_layer].uv - loop[self.uv_layer].uv): _next})

        min_angle_loop = angled_loops[min(angled_loops.keys())]

        # min_angle_loop[self.uv_layer].pin_uv = True
        # origin_loop[self.uv_layer].pin_uv = True

        return LoopsOriginVector(origin_loop, min_angle_loop, self.uv_layer)

    @classmethod
    def rotate_island(
        cls,
        island: list,
        uv_layer,
        angle: float,
        pivot: Vector = Vector((0.0, 0.0)),
        image_aspect: float = 1.0,
        angle_in_radians: bool = True
    ) -> None:
        """
        # image_aspect - aspect ratio
        # image_aspect = image.y / image.x
        """
        from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops

        if not angle_in_radians:
            angle = np.radians(angle)

        TransformLoops.rotate_loops(
            loops=(lp for f in island for lp in f.loops),
            uv_layer=uv_layer,
            angle=angle,
            pivot=pivot,
            image_aspect=image_aspect,
            angle_in_radians=angle_in_radians)

    @classmethod
    def scale_island(
        cls,
        island: list,
        uv_layer,
        scale: Vector = Vector((0.0, 0.0)),
        pivot: Vector = Vector((0.0, 0.0))
    ) -> None:

        loops, uvs = cls._collect_loops(island, uv_layer)
        S = Matrix.Diagonal(scale)
        uvs = np.dot(np.array(uvs).reshape((-1, 2)) - pivot, S) + pivot
        cls._set_uvs(uv_layer, loops, uvs)

    @classmethod
    def move_island(
        cls,
        island: list,
        uv_layer,
        delta: Vector = Vector((0.0, 0.0))
    ) -> None:

        loops, uvs = cls._collect_loops(island, uv_layer)
        uvs = np.array(uvs).reshape((-1, 2)) + delta
        cls._set_uvs(uv_layer, loops, uvs)

    @classmethod
    def move_island_to_position(
        cls,
        island: list,
        uv_layer,
        position: Vector,
        offset: Vector = Vector((0.0, 0.0)),
        pivot: Vector = None,
        axis: Vector = Vector((1.0, 1.0))
    ) -> None:

        if pivot is None:
            pivot = BoundingBox2d(islands=[island, ], uv_layer=uv_layer).center
        delta = (position + offset - pivot) * axis
        loops, uvs = cls._collect_loops(island, uv_layer)
        uvs = (np.array(uvs).reshape((-1, 2)) + delta)
        cls._set_uvs(uv_layer, loops, uvs)

        return delta

    @classmethod
    def fit_island(
        cls,
        island: list,
        uv_layer: bmesh.types.BMLayerItem,
        fit_bbox: BoundingBox2d,
        fit_axis_name: str = 'U',
        single_axis: bool = False,
        keep_proportion: bool = True,
        pivot: Vector = Vector((0.0, 0.0)),
        padding: float = 0.0
    ) -> None:

        i_bbox = BoundingBox2d(islands=[island, ], uv_layer=uv_layer)

        loops, uvs = cls._collect_loops(island, uv_layer)

        S = Matrix.Diagonal(cls._get_scale_vec(fit_axis_name, single_axis, keep_proportion, i_bbox, fit_bbox, padding=padding))
        i_center = (i_bbox.center - pivot) @ S + pivot

        uvs = (np.dot(np.array(uvs).reshape((-1, 2)) - pivot, S) + pivot) + fit_bbox.center - i_center

        cls._set_uvs(uv_layer, loops, uvs)

    @classmethod
    def _get_scale_vec(cls, fit_axis_name: str, single_axis: bool, keep_proportion: bool, i_bbox: BoundingBox2d, fit_bbox: BoundingBox2d, padding: float = 0):
        # TODO If the method has changed, need to check the Unwrap Constraint operator.

        if fit_axis_name in {'MIN', 'MAX'}:
            fit_axis_name = {
                'MAX': 'U' if fit_bbox.len_x > fit_bbox.len_y else 'V',
                'MIN': 'U' if fit_bbox.len_x < fit_bbox.len_y else 'V'
            }[fit_axis_name]

        len_x = i_bbox.len_x if i_bbox.len_x > 0 else 1
        len_y = i_bbox.len_y if i_bbox.len_y > 0 else 1

        ratio = Vector(((fit_bbox.len_x - padding) / len_x, (fit_bbox.len_y - padding) / len_y))
        if keep_proportion:
            if ratio.length == 0:
                ratio = Vector((1.0, 1.0))
            return {
                'U': Vector([ratio.x] * 2),
                'V': Vector([ratio.y] * 2)
            }[fit_axis_name]
        else:
            if single_axis:
                return {
                    'U': Vector((ratio.x, 1.0)),
                    'V': Vector((1.0, ratio.y)),
                }[fit_axis_name]
            return {
                    'U': ratio,
                    'V': ratio,
                }[fit_axis_name]

    @classmethod
    def _collect_loops(
        cls,
        island: list,
        uv_layer: bmesh.types.BMLayerItem,
    ):
        data = {lp: lp[uv_layer].uv for f in island for lp in f.loops}
        return data.keys(), list(data.values())

    @classmethod
    def _set_uvs(
        cls,
        uv_layer: bmesh.types.BMLayerItem,
        loops: list,
        uvs: list
    ):
        for lp, uv in zip(loops, uvs):
            lp[uv_layer].uv = uv

    @classmethod
    def fit_uvs(
        cls,
        uvs: list,
        fit_bbox: BoundingBox2d,
        fit_axis_name: str = 'U',
        single_axis: bool = False,
        keep_proportion: bool = True,
        pivot: Vector = Vector((0.0, 0.0))
    ) -> None:
        ''' Recalculate a scope (list) of coordinates to fit it in the fit_bbox '''
        i_bbox = BoundingBox2d(points=uvs)

        S = Matrix.Diagonal(cls._get_scale_vec(fit_axis_name, single_axis, keep_proportion, i_bbox, fit_bbox))
        i_center = (i_bbox.center - pivot) @ S + pivot

        return (np.dot(np.array(uvs).reshape((-1, 2)) - pivot, S) + pivot) + fit_bbox.center - i_center

    @classmethod
    def match_islands_by_vectors(
        cls,
        matched_island: list,
        uv_layer: bmesh.types.BMLayerItem,
        origin_pivot: Vector,
        origin_vec: Vector,
        matched_pivot: Vector,
        matched_vec: Vector,
        image_ratio: float,
        adv_offset: Vector = Vector((0.0, 0.0)),
        adv_rotate: float = 0.0,
        adv_scale: float = 1.0,
        matching: list = [True, True, True],  # Position, Rotation, Scale
        is_cycled: bool = False
    ) -> None:

        from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops
        from ZenUV.utils.transform import matrix_by_image_aspect

        # loops, _ = cls._collect_loops(matched_island, uv_layer)
        if is_cycled is False:
            pivot = origin_pivot if matching == [True, True, True] or matching == [True, True, False] or matching == [True, False, True] else matched_pivot
        else:
            pivot = origin_pivot if matching == [True, True, True] or matching == [True, True, False] or matching == [True, False, False] else matched_pivot

        delta = origin_pivot - matched_pivot if matching[0] else Vector((0.0, 0.0))

        offset_vec = (origin_pivot - matched_pivot).normalized() * adv_offset
        delta += offset_vec

        S1 = matrix_by_image_aspect(image_ratio)

        angle = adv_rotate + (S1 @ origin_vec).angle_signed(S1 @ matched_vec, 0.0) if matching[1] else 0.0

        R = TransformLoops._get_rotation_matrix(angle, image_ratio)

        matched_vec_magnitude = (S1 @ matched_vec).magnitude if (S1 @ matched_vec).magnitude != 0 else 1
        S = Matrix.Diagonal(Vector([(S1 @ origin_vec).magnitude / matched_vec_magnitude] * 2)) if matching[2] else Matrix.Diagonal(Vector((1.0, 1.0)))
        if adv_scale != 1.0:
            S @= Matrix.Diagonal([adv_scale] * 2)

        for loop in (lp for f in matched_island for lp in f.loops):
            loop[uv_layer].uv = (R @ S @ (loop[uv_layer].uv + delta - pivot)) + pivot
