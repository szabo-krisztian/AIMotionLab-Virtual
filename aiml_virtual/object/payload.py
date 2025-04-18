from aiml_virtual.object.moving_object import MocapObject, MovingObject
from aiml_virtual.util import mujoco_helper
import aiml_virtual.object.mesh_utility_functions as mutil
from enum import Enum
from stl import mesh
import numpy as np
import math
import time
import os

class PAYLOAD_TYPES(Enum):
    Box = "Box"
    Teardrop = "Teardrop"


class PayloadMocap(MocapObject):

    def __init__(self, model, data, mocapid, name_in_xml, name_in_motive) -> None:
        super().__init__(model, data, mocapid, name_in_xml, name_in_motive)

        self.data = data
        self.mocapid = mocapid
    
    
    def update(self, pos, quat):

        #quat_rot = quat.copy()
        #quat_rot = mujoco_helper.quaternion_multiply(quat, np.array((.71, 0.0, 0.0, .71)))

        self.data.mocap_pos[self.mocapid] = pos
        self.data.mocap_quat[self.mocapid] = quat
    
    def get_qpos(self):
        return np.append(self.data.mocap_pos[self.mocapid], self.data.mocap_quat[self.mocapid])


import mujoco
class Payload(MovingObject):

    def __init__(self, model, data, name_in_xml) -> None:
        super().__init__(model, name_in_xml)

        self.data = data

        # supporting only rectangular objects for now
        self.geom = self.model.geom(name_in_xml)
        
        free_joints = mujoco_helper.get_freejoint_name_list(model)
        if self.name_in_xml in free_joints:
            # payload is defined as a separate object with own free joint
            self.payload_cog = self.data.joint(self.name_in_xml)
            self.applied_force = self.payload_cog.qfrc_applied
            self.sensor_posimeter = self.data.sensor(self.name_in_xml + "_posimeter").data
            self.sensor_orimeter = self.data.sensor(self.name_in_xml + "_orimeter").data
            self.sensor_velocimeter = self.data.sensor(self.name_in_xml + "_velocimeter").data
        else:
            # payload is a part of a complex multi-body object (e.g. Bumblebee + payload is defined together)
            self.payload_cog = self.data.body(self.name_in_xml)
            self.applied_force = self.payload_cog.xfrc_applied
            for i in range(self.model.nsensor):
                if 'payload_pos' in self.data.sensor(i).name:
                    self.sensor_posimeter = self.data.sensor(i).data
                elif 'payload_vel' in self.data.sensor(i).name:
                    self.sensor_velocimeter = self.data.sensor(i).data
                elif 'payload_quat' in self.data.sensor(i).name:
                    self.sensor_orimeter = self.data.sensor(i).data
            if not (hasattr(self, 'sensor_posimeter') and hasattr(self, 'sensor_velocimeter') and hasattr(self, 'sensor_orimeter')):
                raise ValueError("Payload 'pos', 'vel', and 'quat' sensors have been defined with wrong naming convention!")


        self._airflow_samplers = []


    def create_surface_mesh(self, surface_division_area: float):
        raise NotImplementedError("[Payload] Subclasses need to implement this method.")
    
    def update(self, i, control_step):
        
        if len(self._airflow_samplers) > 0:
            force = np.array([0.0, 0.0, 0.0])
            torque = np.array([0.0, 0.0, 0.0])
            for airflow_sampler in self._airflow_samplers:
                f, t = airflow_sampler.generate_forces_opt(self)
                force += f
                torque += t
            self.set_force_torque(force, torque)
    
    def add_airflow_sampler(self, airflow_sampler):
        from aiml_virtual.airflow import AirflowSampler
        if isinstance(airflow_sampler, AirflowSampler):
            self._airflow_samplers += [airflow_sampler]
        else:
            raise Exception("[Payload] The received object is not of type AirflowSampler.")
    
    def get_qpos(self):
        return np.append(self.sensor_posimeter, self.sensor_orimeter)
 
    def set_force_torque(self, force, torque):

        self.applied_force[0] = force[0]
        self.applied_force[1] = force[1]
        self.applied_force[2] = force[2]
        self.applied_force[3] = torque[0]
        self.applied_force[4] = torque[1]
        self.applied_force[5] = torque[2]


class BoxPayload(Payload):

    def __init__(self, model, data, name_in_xml) -> None:
        super().__init__(model, data, name_in_xml)

        
        if self.geom.type == mujoco.mjtGeom.mjGEOM_BOX:

            self.size = self.geom.size # this is half size on each axis
            self.top_bottom_surface_area = 2 * self.size[0] * 2 * self.size[1]
            self.side_surface_area_xz = 2 * self.size[0] * 2 * self.size[2]
            self.side_surface_area_yz = 2 * self.size[1] * 2 * self.size[2]
            self.create_surface_mesh(0.0001)
        
        else:
            raise Exception("[BoxPayload __init__] Payload is not box shaped.")


    def create_surface_mesh(self, surface_division_area: float):
        """
        inputs:
          * surface_division_area: the area of the small surface squares in m^2
        """
        
        a = surface_division_area

        square_side = math.sqrt(a)

        subdiv_x = int(round(self.size[0] / square_side))
        subdiv_y = int(round(self.size[1] / square_side))
        subdiv_z = int(round(self.size[2] / square_side))

        self._set_top_and_bottom_mesh(subdiv_x, subdiv_y)
        self._set_side_mesh(subdiv_x, subdiv_y, subdiv_z)

    def _set_top_and_bottom_mesh(self, top_bottom_subdivision_x, top_bottom_subdivision_y):
        self._top_bottom_subdivision_x = top_bottom_subdivision_x
        self._top_bottom_subdivision_y = top_bottom_subdivision_y
        self.top_bottom_miniractangle_area = self.top_bottom_surface_area / (top_bottom_subdivision_x * top_bottom_subdivision_y)
        self._calc_top_rectangle_positions()
        self._calc_bottom_rectangle_positions()

    def _set_side_mesh(self, subdivision_x, subdivision_y, subdivision_z):
            
        self._side_subdivision_x = subdivision_x
        self._side_subdivision_y = subdivision_y
        self._side_subdivision_z = subdivision_z
        self.side_miniractangle_area_xz = self.side_surface_area_xz / (subdivision_x * subdivision_z)
        self.side_miniractangle_area_yz = self.side_surface_area_yz / (subdivision_y * subdivision_z)
        self._calc_side_rectangle_positions()
    
    def _get_top_position_at(self, i, j):
        """ get the center in world coordinates of a small rectangle on the top of the box """
        return self._top_rectangle_positions[i, j]
    
    #def get_top_surface_normal(self):

        # rotate (0, 0, 1) vector by rotation quaternion
        #rot_matrix = Rotation.from_quat(self.sensor_orimeter)
        #return rot_matrix.apply(np.array((0, 0, 1)))
        #return np.array((0, 0, 1))
    
    def get_top_rectangle_data_at(self, i, j):

        """
        returns:
        - position (in world coordinates) of the center of the small rectangle,
        - position in payload frame of the center of the small rectangle
        - normal vector of the surface
        - and area of the surface
        at index i, j
        """

        # rotate position with respect to the center of the box
        position_in_own_frame = mujoco_helper.qv_mult(self.sensor_orimeter, self._get_top_position_at(i, j))
        # add position of the center
        position = self.sensor_posimeter + position_in_own_frame
        normal = mujoco_helper.qv_mult(self.sensor_orimeter, np.array((0, 0, 1)))
        return position, position_in_own_frame, normal, self.top_bottom_miniractangle_area
    
    def get_top_rectangle_data(self):
        pos_in_own_frame = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._top_rectangle_positions_raw)
        normal = mujoco_helper.qv_mult(self.sensor_orimeter, np.array((0, 0, 1)))
        return pos_in_own_frame + self.sensor_posimeter, pos_in_own_frame, normal, self.top_bottom_miniractangle_area

    def get_bottom_rectangle_data(self):
        pos_in_own_frame = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._bottom_rectangle_positions_raw)
        normal = mujoco_helper.qv_mult(self.sensor_orimeter, np.array((0, 0, -1)))
        return pos_in_own_frame + self.sensor_posimeter, pos_in_own_frame, normal, self.top_bottom_miniractangle_area

    def get_side_xz_rectangle_data(self):
        pos_in_own_frame_negative = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._side_rectangle_positions_xz_neg_raw)
        pos_in_own_frame_positive = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._side_rectangle_positions_xz_pos_raw)
        normal_negative = mujoco_helper.qv_mult(self.sensor_orimeter, np.array((0, -1, 0)))
        normal_positive = mujoco_helper.qv_mult(self.sensor_orimeter, np.array((0, 1, 0)))

        pos_world_negative = pos_in_own_frame_negative + self.sensor_posimeter
        pos_world_positive = pos_in_own_frame_positive + self.sensor_posimeter

        return pos_world_negative, pos_world_positive, pos_in_own_frame_negative, pos_in_own_frame_positive,\
            normal_negative, normal_positive, self.side_miniractangle_area_xz

    def get_side_yz_rectangle_data(self):
        pos_in_own_frame_negative = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._side_rectangle_positions_yz_neg_raw)
        pos_in_own_frame_positive = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._side_rectangle_positions_yz_pos_raw)
        normal_negative = mujoco_helper.qv_mult(self.sensor_orimeter, np.array((-1, 0, 0)))
        normal_positive = mujoco_helper.qv_mult(self.sensor_orimeter, np.array((1, 0, 0)))

        pos_world_negative = pos_in_own_frame_negative + self.sensor_posimeter
        pos_world_positive = pos_in_own_frame_positive + self.sensor_posimeter

        return pos_world_negative, pos_world_positive, pos_in_own_frame_negative, pos_in_own_frame_positive,\
            normal_negative, normal_positive, self.side_miniractangle_area_yz
        
    def get_top_subdiv(self):
        return self._top_bottom_subdivision_x, self._top_bottom_subdivision_y

    def _calc_top_rectangle_positions(self):
        """ 3D vectors pointing from the center of the box, to the center of the small top rectangles """

        self._top_rectangle_positions = np.zeros((self._top_bottom_subdivision_x, self._top_bottom_subdivision_y, 3))


        pos_z = self.size[2] # no need to divide by 2, because it's half
        division_size_x = (2 * self.size[0]) / self._top_bottom_subdivision_x
        division_size_y = (2 * self.size[1]) / self._top_bottom_subdivision_y

        self._top_rectangle_positions_raw = np.zeros((self._top_bottom_subdivision_x * self._top_bottom_subdivision_y, 3))

        for i in range(self._top_bottom_subdivision_x):
            distance_x = i * division_size_x + (division_size_x / 2.0)
            pos_x = distance_x - self.size[0]

            for j in range(self._top_bottom_subdivision_y):
                
                distance_y = j * division_size_y + (division_size_y / 2.0)
                pos_y = distance_y - self.size[1]
                self._top_rectangle_positions[i, j] = np.array((pos_x, pos_y, pos_z))
                self._top_rectangle_positions_raw[(i * self._top_bottom_subdivision_y) + j] = np.array((pos_x, pos_y, pos_z)) # store the same data in a 1D array

    def _calc_bottom_rectangle_positions(self):
        """ 3D vectors pointing from the center of the box, to the center of the small bottom rectangles """

        self._bottom_rectangle_positions = np.zeros((self._top_bottom_subdivision_x, self._top_bottom_subdivision_y, 3))
        self._bottom_rectangle_positions_raw = np.zeros((self._top_bottom_subdivision_x * self._top_bottom_subdivision_y, 3))

        pos_z_offset = (-1) * self.size[2]

        for i in range(self._top_bottom_subdivision_x):
            for j in range(self._top_bottom_subdivision_y):
                self._bottom_rectangle_positions[i, j] = self._top_rectangle_positions[i, j] + pos_z_offset
                self._bottom_rectangle_positions_raw[(i * self._top_bottom_subdivision_y + j)] = self._top_rectangle_positions_raw[(i * self._top_bottom_subdivision_y) + j] + pos_z_offset

    def _calc_side_rectangle_positions(self):
        """ 3D vectors pointing from the center of the box, to the center of the small rectangles on the sides """

        self._side_rectangle_positions_xz_neg_raw = np.zeros((self._side_subdivision_x * self._side_subdivision_z, 3))
        self._side_rectangle_positions_xz_pos_raw = np.zeros((self._side_subdivision_x * self._side_subdivision_z, 3))
        self._side_rectangle_positions_yz_neg_raw = np.zeros((self._side_subdivision_y * self._side_subdivision_z, 3))
        self._side_rectangle_positions_yz_pos_raw = np.zeros((self._side_subdivision_y * self._side_subdivision_z, 3))

        # xz plane negative and positive side
        pos_y = self.size[1]
        div_size_x = (2 * self.size[0]) / self._side_subdivision_x
        div_size_z = (2 * self.size[2]) / self._side_subdivision_z
        
        for i in range(self._side_subdivision_x):
            distance_x = i * div_size_x + (div_size_x / 2.0)
            pos_x = distance_x - self.size[0]

            for j in range(self._side_subdivision_z):
                
                distance_z = j * div_size_z + (div_size_z / 2.0)
                pos_z = distance_z - self.size[2]

                self._side_rectangle_positions_xz_neg_raw[(i * self._side_subdivision_z) + j] = np.array((pos_x, -pos_y, pos_z))
                self._side_rectangle_positions_xz_pos_raw[(i * self._side_subdivision_z) + j] = np.array((pos_x, pos_y, pos_z))
        
        
        # yz plane negative and positive side
        pos_x = self.size[0]
        div_size_y = (2 * self.size[1]) / self._side_subdivision_y
        div_size_z = (2 * self.size[2]) / self._side_subdivision_z
        
        for i in range(self._side_subdivision_y):
            distance_y = i * div_size_y + (div_size_y / 2.0)
            pos_y = distance_y - self.size[1]

            for j in range(self._side_subdivision_z):
                
                distance_z = j * div_size_z + (div_size_z / 2.0)
                pos_z = distance_z - self.size[2]

                self._side_rectangle_positions_yz_neg_raw[(i * self._side_subdivision_z) + j] = np.array((-pos_x, pos_y, pos_z))
                self._side_rectangle_positions_yz_pos_raw[(i * self._side_subdivision_z) + j] = np.array((pos_x, pos_y, pos_z))

class MeshPart(Enum):
    TOP = 1
    BOTTOM = 2

class TeardropPayload(Payload):
    def __init__(self, model, data, name_in_xml) -> None:
        super().__init__(model, data, name_in_xml)

        self._triangles = None
        self._center_positions = None
        self._normals = None
        self._areas = None

        self._MIN_Z = None
        self._MAX_Z = None
        self._TOP_BOTTOM_RATIO = 0.005

        abs_path = os.path.dirname(os.path.abspath(__file__))
        payload_stl_path = os.path.join(abs_path, "..", "..", "xml_models", "meshes", "payload", name_in_xml + ".stl")
        self._init_default_values(payload_stl_path)
        self._bottom_triangles, self._bottom_center_positions, self._bottom_normals, self._bottom_areas = self._init_bottom_data()
        self._top_triangles, self._top_center_positions, self._top_normals, self._top_areas = self._init_top_data()

    def _init_default_values(self, path):
        meter = 1000.0
        self._loaded_mesh = mesh.Mesh.from_file(path)
        self._loaded_mesh.vectors[:, :, [1, 2]] = self._loaded_mesh.vectors[:, :, [2, 1]]
        self._loaded_mesh.vectors /= meter

        self._triangles = self._loaded_mesh.vectors
        self._center_positions = mutil.get_center_positions(self._triangles)
        self._normals = mutil.get_triangle_normals(self._triangles)
        self._areas = (self._loaded_mesh.areas / (meter ** 2)).flatten()
        self._MIN_Z = np.min(self._triangles[:, :, 2])
        self._MAX_Z = np.max(self._triangles[:, :, 2])
        
        mutil.set_normals_pointing_outward(self._normals, self._center_positions)

    def get_data(self):
        pos_in_own_frame = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._center_positions)
        normals = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._normals)
        return pos_in_own_frame + self.sensor_posimeter, pos_in_own_frame, normals, self._areas

    def get_bottom_data(self):
        pos_in_own_frame = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._bottom_center_positions)
        normals = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._bottom_normals)
        return pos_in_own_frame + self.sensor_posimeter, pos_in_own_frame, normals, self._bottom_areas

    def get_top_data(self):
        pos_in_own_frame = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._top_center_positions)
        normals = mujoco_helper.quat_vect_array_mult(self.sensor_orimeter, self._top_normals)
        return pos_in_own_frame + self.sensor_posimeter, pos_in_own_frame, normals, self._top_areas

    def _init_top_data(self):
        mesh_height = self._MAX_Z - self._MIN_Z
        mask = np.any(self._triangles[:, :, 2] > self._MIN_Z + (mesh_height) * self._TOP_BOTTOM_RATIO, axis=1)
        return self._triangles[mask], self._center_positions[mask], self._normals[mask], self._areas[mask]

    def _init_bottom_data(self):
        mesh_height = self._MAX_Z - self._MIN_Z
        mask = np.any(self._triangles[:, :, 2] > (self._MIN_Z + (mesh_height) * self._TOP_BOTTOM_RATIO), axis=1)
        return self._triangles[~mask], self._center_positions[~mask], self._normals[~mask], self._areas[~mask]

    def create_surface_mesh(self, which_part, threshold_in_meters):
        if which_part == MeshPart.TOP:
            triangles = self._top_triangles
            normals = self._top_normals
            areas = self._top_areas
            center_positions = self._top_center_positions

        elif which_part == MeshPart.BOTTOM:
            triangles = self._bottom_triangles
            normals = self._bottom_normals
            areas = self._bottom_areas
            center_positions = self._bottom_center_positions

        else:
            raise ValueError("Invalid value for 'which_set'. Use 'top' or 'bottom'.")

        area_threshold = threshold_in_meters / 1000.0
        mask = areas > area_threshold

        triangles_to_divide = triangles[mask]
        normals_to_divide = normals[mask]
        areas_to_divide = areas[mask]

        triangles_kept = triangles[~mask]
        normals_kept = normals[~mask]
        areas_kept = areas[~mask]

        if len(triangles_to_divide) == 0:
            self._triangles = np.concatenate([self._bottom_triangles, self._top_triangles])
            self._center_positions = np.concatenate([self._bottom_center_positions, self._top_center_positions])
            self._normals = np.concatenate([self._bottom_normals, self._top_normals])
            self._areas = np.concatenate([self._bottom_areas, self._top_areas])
            return

        new_triangles = []
        midpoints = self._get_midpoints(triangles_to_divide)
        for i in range(len(triangles_to_divide)):
            new_triangles.extend(np.array([
                    [triangles_to_divide[i][0], midpoints[i][0], midpoints[i][2]],
                    [midpoints[i][0], triangles_to_divide[i][1], midpoints[i][1]],
                    [midpoints[i][1], triangles_to_divide[i][2], midpoints[i][2]],
                    [midpoints[i][0], midpoints[i][1], midpoints[i][2]]
                ])
            )

        new_normals = np.repeat(normals_to_divide, 4, axis=0)
        new_areas = np.repeat(areas_to_divide, 4, axis=0) / 4
        new_triangles = np.array(new_triangles)
        
        if which_part == MeshPart.TOP:
            self._top_triangles = np.concatenate([triangles_kept, new_triangles])
            self._top_normals = np.concatenate([normals_kept, new_normals])
            self._top_areas = np.concatenate([areas_kept, new_areas])
            self._top_center_positions = mutil.get_center_positions(self._top_triangles)

        elif which_part == MeshPart.BOTTOM:
            self._bottom_triangles = np.concatenate([triangles_kept, new_triangles])
            self._bottom_normals = np.concatenate([normals_kept, new_normals])
            self._bottom_areas = np.concatenate([areas_kept, new_areas])
            self._bottom_center_positions = mutil.get_center_positions(self._bottom_triangles)

        self.create_surface_mesh(which_part, threshold_in_meters)

    def _get_midpoints(self, triangles):
        return (triangles[:, [0, 1, 2], :] + triangles[:, [1, 2, 0], :]) / 2