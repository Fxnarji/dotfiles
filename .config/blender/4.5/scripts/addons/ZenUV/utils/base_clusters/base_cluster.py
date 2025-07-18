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

import bmesh
import math
import numpy as np
from mathutils import Vector, Matrix

from ZenUV.utils.transform import (
    calculate_fit_scale,
    UvTransformUtils
)
from ZenUV.utils.bounding_box import BoundingBox3d
from ZenUV.utils.bounding_box import BoundingBox2d
from ZenUV.utils import get_uv_islands as island_util
from ZenUV.utils.constants import Planes
from ZenUV.utils.projection import Projection, pVector

# Debugging Purposes
from ZenUV.utils.generic import Scope, verify_uv_layer
# from ZenUV.utils.generic import MeshBuilder
from ZenUV.utils.blender_zen_utils import ZenPolls
from ZenUV.ops.transform_sys.transform_utils.tr_utils import ActiveUvImage
from ZenUV.ops.transform_sys.transform_utils.transform_loops import TransformLoops


class BaseCluster():
    def __init__(self, context, obj, island, bm=None, index=-1) -> None:
        self.index = index
        self.island = self._island_container(island)
        self.context = context
        self.obj = self._object_container(obj)
        self.bm = self._get_bm() if bm is None else bm
        # self.bm.faces.ensure_lookup_table()
        self.destroy_bm = False
        self.transform_ma = self.obj.matrix_world
        self.loops = {loop.index: loop for face in self.island for loop in face.loops}
        self.uv_layer = verify_uv_layer(self.bm)
        self.init_co = [loop[self.uv_layer].uv.copy().freeze() for loop in self.loops.values()]
        self.uv_layer_name = self.uv_layer.name

        self.bbox: BoundingBox2d = BoundingBox2d(islands=[self.island, ], uv_layer=self.uv_layer)

        self.bound_uv_edges = self._cluster_bound_edges()

    def select(self, context, state=True):
        C = context
        uv_layer = self.uv_layer
        # self.mesh_edge.select = True
        sync_uv = C.scene.tool_settings.use_uv_select_sync
        if C.space_data.type == 'IMAGE_EDITOR' and not sync_uv:
            for loop in self.loops.values():
                loop[uv_layer].select = state
            if ZenPolls.version_since_3_2_0:
                for loop in self.loops.values():
                    loop[uv_layer].select_edge = state
        else:
            for f in self.island:
                f.select = state

    def reset(self):
        for loop, co in zip(self.loops.values(), self.init_co):
            loop[self.uv_layer].uv = co

    def update_bounds(self):
        self.bound_uv_edges = self._cluster_bound_edges()

    def update_mesh(self):
        bmesh.update_edit_mesh(self.obj.data, loop_triangles=False)

    def _object_container(self, obj):
        if isinstance(obj, str):
            return self.context.scene.objects[obj]
        else:
            return obj

    def _check_zeroarea(self):
        zeroarea = [f for f in self.island if f.calc_area() == 0]
        return zeroarea

    def _island_container_worked(self, island):
        if not isinstance(island, list):
            island = list(island)
        if not isinstance(island[0], int):
            return island
        else:
            self.bm.faces.ensure_lookup_table()
            return [self.bm.faces[index] for index in island]

    def _island_container(self, island):
        if not isinstance(island, list):
            island = list(island)
        if not isinstance(island[0], int):
            return island
            # Fixed #371
            # return [f for f in island if f.calc_area() != 0]
        else:
            self.bm.faces.ensure_lookup_table()
            # Fixed #371
            # return [f for f in [self.bm.faces[index] for index in island] if f.calc_area() != 0]
            return [f for f in [self.bm.faces[index] for index in island]]

    def _get_bm(self):
        if self.obj.mode == "EDIT":
            return bmesh.from_edit_mesh(self.obj.data)
        else:
            bm = bmesh.new()
            bm.from_mesh(self.obj.data)
            self.destroy_bm = True
            return bm

    def _cluster_bound_edges(self):
        edge_indexes = island_util.get_uv_bound_edges_indexes(self.island, self.uv_layer)
        edges = [e for f in self.island for e in f.edges if e.index in edge_indexes]
        loops = [loop for edge in edges for loop in edge.link_loops if loop in self.loops.values()]
        ex = []
        for loop in loops:
            ex.append(loop.link_loop_next)
        return loops + ex

    # Deleting (Calling destructor)
    def __del__(self):
        if self.destroy_bm:
            self.bm.free


class ProjectionPlane:
    i = 1
    j = 1
    direction = Vector((-1.0, 0.0, 0.0))
    transform = Matrix.Rotation(math.radians(45.0), 4, 'Z') @ Matrix.Rotation(math.radians(-20.0), 4, 'X')
    # transform = Matrix()
    s = transform @ Vector((0.0, 0.0, 0.0))
    x = transform @ Vector((1.0, 0.0, 0.0)) * i
    y = transform @ Vector((0.0, 0.0, 1.0)) * j
    s_uv = Vector((0.0, 0.0))
    x_uv = Vector((1.0, 0.0))
    y_uv = Vector((0.0, 1.0))


# class ProjectCluster(BaseCluster):
class ProjectCluster():

    def set_fit_to_uv(self, fit=False):
        self.fit_to_uv_area = fit

    def set_object(self, obj):
        self.obj = obj

    def set_transform(self, ma):
        self.ma = ma

    def project_hybrid_cluster(self):
        """ Creates a projection based on BaseCluster and ZenCluster data """
        self.project()

        edges = [edge for edge in self.uv_edges if edge.is_border()]
        distortion = (np.random.rand(len(edges), 2) * 0.001).tolist()
        verts = [[edge.vert, edge.other_vert] for edge in edges]
        for v_edge, dist in zip(verts, distortion):
            vec = Vector(dist)
            v_edge[0].move_by(vec)
            v_edge[1].move_by(vec)

    def project_face_loops(self, loops, uv_layer, input_plane=None, s_factor=1.0):
        plane = self.check_input_plane(input_plane, rough_fit=True)

        base_co, base_uv, to_uv = self._project(plane)

        for lp in loops:
            lp[uv_layer].uv = base_uv + (self.ma @ lp.vert.co - base_co) @ to_uv * s_factor

    def project(self, input_plane=None, s_factor=1.0):
        """ plane - Vectors list size 3
        Sample  [Vector((0.0, 0.0, 0.0)), Vector((1.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0))]
        Mapping [zero, x, y]
        """
        if not hasattr(self, "ma"):
            self.ma = Matrix()

        plane = self.check_input_plane(input_plane, rough_fit=True)

        base_co, base_uv, to_uv = self._project(plane)

        for lp in self.loops.values():
            lp[self.uv_layer].uv = base_uv + (self.ma @ lp.vert.co - base_co) @ to_uv * s_factor

        # Fit to UV Area
        if hasattr(self, "fit_to_uv_area") and self.fit_to_uv_area:
            points = [lp[self.uv_layer].uv for lp in self.loops.values()]
            points = np.array(points)
            points = self._fit_to_uv_area(points)
            points *= s_factor

            for lp, co in zip(self.loops.values(), points):
                lp[self.uv_layer].uv = co

    def _project(self, plane):
        base_co = plane.s
        x = plane.x - base_co
        y = plane.y - base_co
        normal = x.cross(y)

        base_uv = plane.s_uv

        u = plane.x_uv - base_uv
        v = plane.y_uv - base_uv

        to_uv = Matrix([x, y, normal]).inverted(Matrix([x, y, normal])) @ Matrix([u, v, [0, 0]])
        return base_co, base_uv, to_uv

    def check_input_plane(self, input_plane, rough_fit=True):
        if not input_plane:
            plane = ProjectionPlane()

            # Try to fit Plane to Object bbox.
            if rough_fit:
                bbox = BoundingBox3d(self.obj)
                plane.s = bbox.lo_point * Vector((1, 0, 1))
                factor = bbox.max_dim
                plane.x = plane.s + plane.x * factor
                plane.y = plane.s + plane.y * factor

        else:
            plane = ProjectionPlane()
            plane.s = input_plane[0]
            plane.x = input_plane[1]
            plane.y = input_plane[2]
        return plane

    def project_zen_cluster(self, input_plane=None, s_factor=1.0):
        """ Create projection only for ZenCluster. """
        plane = self.check_input_plane(input_plane, rough_fit=True)

        base_co, base_uv, to_uv = self._project(plane)

        for edge in self.uv_edges:
            distortion = np.random.rand(1, 2)[0] * 0.001 if edge.is_border() else [0, 0]
            for v in (edge.vert, edge.other_vert):
                v.set_position(Vector(distortion) + base_uv + (v.mesh_vert.co - base_co) @ to_uv * s_factor)

    def preproject(self):
        """ Create simple preprojection in general purposes.
            Main goal is to avoid zero uv coordinates. """
        coo = np.random.rand(len(self.loops), 2)
        for lp, co in zip(self.loops.values(), coo):
            lp[self.uv_layer].uv = co

    def project_obj_mode(self, input_plane=None, s_factor=1.0):
        """ Create projection in OBJECT MODE.
        self.obj need to be specified. self.set_object(obj)."""

        if not hasattr(self, "ma"):
            self.ma = Matrix()

        plane = self.check_input_plane(input_plane, rough_fit=True)
        base_co, base_uv, to_uv = self._project(plane)

        me = self.obj.data
        uv_layer = me.uv_layers.active.data

        for lp in me.loops:
            vertex_co = self.ma @ me.vertices[lp.vertex_index].co
            uv_layer[lp.index].uv = base_uv + (vertex_co - base_co) @ to_uv * s_factor

        # Fit to UV Area
        if hasattr(self, "fit_to_uv_area") and self.fit_to_uv_area:
            loops = {uv_layer[lp.index]: uv_layer[lp.index].uv for lp in me.loops}
            points = np.array(list(loops.values()))

            points = self._fit_to_uv_area(points)
            points *= s_factor

            for loop, coo in zip(loops.keys(), points):
                loop.uv = coo

    def _fit_to_uv_area(self, points):
        factor = self._get_factor(points=points.tolist())
        points *= factor
        shift = self._get_shift(points=points.tolist())
        points += shift
        return points

    def _get_shift(self, points):
        bbox = BoundingBox2d(points=points)
        return bbox.shift_to_uv_area

    def _get_factor(self, points):
        bbox = BoundingBox2d(points=points)
        return bbox.factor_to_uv_area


# class TransformCluster(ZenCluster):
class TransformCluster():

    # def __init__(self, context, obj, island, bm=None) -> None:
    #     super().__init__(context, obj, island, bm)

    def rotate(
        self,
        angle=1.5708,
        anchor: Vector = None
    ) -> None:
        """ angle in radians """
        if anchor is None:
            anchor = self.bbox.center
        UvTransformUtils.rotate_island(self.island, self.uv_layer, angle, anchor, angle_in_radians=True)

    def fit(self, fit_mode="cen", keep_proportion=True, bounds=Vector((1.0, 1.0))):
        scale = calculate_fit_scale(fit_mode, 0.0, self.bbox, keep_proportion, bounds=bounds)
        UvTransformUtils.scale(self.island, self.uv_layer, scale, pivot=self.bbox.center)

    def move_to_pos(self, pos):
        loops = [loop[self.uv_layer] for loop in self.loops.values()]
        # np.array(uvs).reshape((-1, 2)) + delta
        uvs = np.array([loop.uv for loop in loops]).reshape((-1, 2)) + pos
        self._set_uvs(loops, uvs)

    def scale(self, scale: float, pivot: Vector):
        loops = [loop[self.uv_layer] for loop in self.loops.values()]
        uvs = np.array([loop.uv for loop in loops]).reshape((-1, 2))

        S = Matrix.Diagonal(Vector([scale] * 2))
        uvs = np.dot(np.array(uvs).reshape((-1, 2)) - pivot, S) + pivot
        self._set_uvs(loops, uvs)

    def _collect_loops(self):
        data = {lp[self.uv_layer]: lp[self.uv_layer].uv for lp in self.loops.values()}
        return data.keys(), list(data.values())

    def _set_uvs(self, loops, uvs):
        for lp, uv in zip(loops, uvs):
            lp.uv = uv


class OrientCluster():

    def __init__(self):
        self.f_orient = False
        self.axis_direction = {
                "x": 0.0,
                "-x": 0.0,
                "y": 0.0,
                "-y": 0.0,
                "z": 0.0,
                "-z": 0.0,
            }
        # self.show_info = False
        self.compensate_transform = False
        self.primary_edges = None
        self.cluster_normal_axis = None

        self.transform_ma = Matrix()
        self.cluster_normal = None

        self._cluster_parametrization()

        self.edge_anchor = None
        self.uv_angle = 0
        self.mesh_angle = 0
        self.master_edge = None
        self.select_master_edge = False
        self.type = 'ORGANIC'

    def set_direction(self, direction):
        rev_values = {True: math.pi, False: 0.0}
        for axis, _dir in direction.items():
            self.axis_direction[axis] = rev_values[_dir]

    def do_orient_to_world(self):
        if self.type == 'ORGANIC':
            self._orient_organic()
        elif self.type == 'HARD':
            self._orient_hard()
        else:
            print("The Cluster TYPE is not defined. Define the TYPE first.(HARD, ORGANIC)")

    def show_data(self):
        # self.show_info = True
        print("\nOrient Cluster Data: ")
        print("Master Edge Index ->", self.master_edge.mesh_edge.index)
        print("UV Angle: ", math.degrees(self.uv_angle))
        print("Mesh Angle: ", math.degrees(self.mesh_angle))

    def _find_min_vertical(self, edge):
        return min([(self.transform_ma @ vert.co).z for vert in edge.mesh_verts])

    def _find_min_horizontal(self, edge):
        return min([(self.transform_ma @ vert.co).y for vert in edge.mesh_verts])

    def _cluster_parametrization(self):

        self.primary_edges = self._find_primary_edges()
        normal = self.get_cluster_overall_normal()
        if normal.magnitude < 1:
            normal = self.get_cluster_simple_normal()

        normal.normalize()

        self.cluster_normal = normal
        self.cluster_normal_axis = self._get_cluster_normal_axis()

        if "z" in self.cluster_normal_axis:
            self.primary_edges = self._find_primary_edges(vertical=False)

    def get_cluster_simple_normal(self):
        edge = self.primary_edges[0]
        normals = [loop.face.normal for loop in edge.loops]
        normal = Vector()
        for n in normals:
            normal += n
        normal = self.transform_ma @ normal
        return normal

    def get_cluster_overall_normal(self):
        normal = Vector()
        for face in self.island:
            normal = normal + face.normal
        normal = self.transform_ma @ normal
        return normal

    # def build_vector(self, normal):
    #     builder = MeshBuilder(self.bm)
    #     coords = (Vector(), normal)
    #     builder.create_edge(coords)

    def _test_for_z(self, normal, axis):

        if round(normal.x, 4) == round(Planes.z3_negative.x, 4) and \
           round(normal.y, 4) == round(Planes.z3_negative.y, 4) and \
           round(normal.z, 4) == round(Planes.z3_negative.z, 4):
            return "-z"

        if round(normal.x, 4) == round(Planes.z3.x, 4) and \
           round(normal.y, 4) == round(Planes.z3.y, 4) and \
           round(normal.z, 4) == round(Planes.z3.z, 4):
            return "z"

        return axis

    def _orient_hard(self):
        image_aspect = ActiveUvImage(self.context).aspect
        axis = self.cluster_normal_axis
        self.master_edge = self.primary_edges[0]

        prj = Projection(self.transform_ma, self.bm, self.master_edge)
        proj = prj.uni_project(axis)
        self.mesh_angle = proj.angle_to_y_2d()
        self.uv_angle = pVector((
            self.master_edge.vert.uv_co,
            self.master_edge.other_vert.uv_co)).angle_to_y_2d() * -1

        if axis == "-x":
            dif_angle = self.uv_angle - self.mesh_angle
        if axis == "x":
            dif_angle = self.uv_angle + self.mesh_angle
        if axis == "y":
            dif_angle = self.uv_angle - self.mesh_angle
        if axis == "-y":
            dif_angle = self.uv_angle + self.mesh_angle
        if axis == "-z":
            dif_angle = self.uv_angle - self.mesh_angle
            dif_angle += math.pi
        if axis == "z":
            dif_angle = self.uv_angle + self.mesh_angle

        dif_angle += self.axis_direction[axis]

        if self.select_master_edge:
            self.master_edge.mesh_edge.select = True

        TransformLoops.rotate_loops(
            loops=[lp for f in self.island for lp in f.loops],
            uv_layer=self.uv_layer,
            angle=dif_angle,
            pivot=self.bbox.center,
            image_aspect=image_aspect,
            angle_in_radians=True)

        for vert in self.uv_verts:
            vert.update_uv_co()

        if self.f_orient:
            dif_angle = 0.0 if self.bbox.is_circle() else self.bbox.get_orient_angle(image_aspect)

            if axis == "-z":
                dif_angle += math.pi

            dif_angle += self.axis_direction[axis]

            TransformLoops.rotate_loops(
                loops=[lp for f in self.island for lp in f.loops],
                uv_layer=self.uv_layer,
                angle=dif_angle,
                pivot=self.bbox.center,
                image_aspect=image_aspect,
                angle_in_radians=True)

    def _get_cluster_normal_axis(self):
        dot = -100
        axis = 0

        for ax, plane in Planes.pool_3d_orient_dict.items():
            current_dot = self.cluster_normal.dot(plane)
            if current_dot > dot:
                dot = current_dot
                axis = ax
        axis = self._test_for_z(self.cluster_normal, axis)
        return axis

    def print_r_points(self, r_points):
        print("r_points -->")
        for p in r_points:
            print(p)
        print("r_points <--")

    def _orient_organic(self):
        image_aspect = ActiveUvImage(self.context).aspect
        edge = self._find_base_vector()

        dot = -100
        axis = 0

        for ax, plane in Planes.pool_3d_orient_dict.items():
            current_dot = self.cluster_normal.dot(plane)
            if current_dot > dot:
                dot = current_dot
                axis = ax
        axis = self._test_for_z(self.cluster_normal, axis)
        self.master_edge = None
        prj = Projection(self.transform_ma, self.bm, edge)
        proj = prj.uni_project(axis)
        self.mesh_angle = proj.angle_to_y_2d()
        self.uv_angle = pVector((
            edge.vert.uv_co,
            edge.other_vert.uv_co)).angle_to_y_2d()

        dif_angle = - self.uv_angle + self.mesh_angle

        if axis == "-x":
            dif_angle = - self.uv_angle - self.mesh_angle
        if axis == "x":
            dif_angle = - self.uv_angle + self.mesh_angle
        if axis == "y":
            dif_angle = - self.uv_angle - self.mesh_angle
        if axis == "-y":
            dif_angle = - self.uv_angle + self.mesh_angle
        if axis == "-z":
            dif_angle += math.pi
        if axis == "-z":
            dif_angle = - self.uv_angle + self.mesh_angle

        dif_angle += self.axis_direction[axis]

        TransformLoops.rotate_loops(
            loops=[lp for f in self.island for lp in f.loops],
            uv_layer=self.uv_layer,
            angle=dif_angle,
            pivot=self.bbox.center,
            image_aspect=image_aspect,
            angle_in_radians=True)

    def _find_base_vector(self):
        fake_edge = self.primary_edges[0]

        scp = Scope()
        for vert in self.uv_verts:
            if "z" not in self.cluster_normal_axis:
                co = (self.transform_ma @ vert.mesh_vert.co).z
            else:
                co = (self.transform_ma @ vert.mesh_vert.co).y
            scp.append(co, vert)

        v01 = scp.get_value_with_min_key()[0]
        v02 = scp.get_value_with_max_key()[0]

        fake_edge.vert = v01
        fake_edge.other_vert = v02
        fake_edge.verts_co = [v01.uv_co, v02.uv_co]
        fake_edge.mesh_verts = [v01.mesh_vert, v02.mesh_vert]

        return fake_edge

    def _find_primary_edges(self, vertical=True):
        sorter = {True: self._find_min_vertical, False: self._find_min_horizontal}
        uv_edges = self.uv_edges
        scp = Scope()
        for edge in uv_edges:
            min_value = sorter[vertical](edge)
            scp.append(min_value, edge)

        axis_sorter = {True: self.ax_sorter_vertical, False: self.ax_sorter_horizontal}
        stored_edges = scp.get_value_with_min_key()

        scp.clear()

        for edge in stored_edges:
            vec_edge = self.transform_ma @ (edge.mesh_verts[0].co - edge.mesh_verts[1].co)
            current_dot = axis_sorter[vertical](vec_edge)
            scp.append(current_dot, edge)

        return scp.get_value_with_max_key()

    def ax_sorter_vertical(self, vec_edge):
        return abs(vec_edge.dot(Planes.z3))

    def ax_sorter_horizontal(self, vec_edge):
        return abs(vec_edge.dot(Planes.y3))
