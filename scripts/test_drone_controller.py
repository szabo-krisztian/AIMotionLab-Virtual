import os
from aiml_virtual.simulator import ActiveSimulator
from aiml_virtual.xml_generator import SceneXmlGenerator
from aiml_virtual.object.drone import Drone, DRONE_TYPES
from aiml_virtual.object.payload import Payload
from aiml_virtual.trajectory.hooked_drone_trajectory import HookedDroneTrajectory
from aiml_virtual.controller import GeomControl
from aiml_virtual.controller import LtvLqrLoadControl
import numpy as np
import matplotlib.pyplot as plt
from aiml_virtual.airflow import AirflowSampler
from aiml_virtual.object import parseMovingObjects


def update_controller_type(state, setpoint, time, i):
    # return the index of the controller in the list?
    return 0


if __name__ == '__main__':

    RED_COLOR = "0.85 0.2 0.2 1.0"
    BLUE_COLOR = "0.2 0.2 0.85 1.0"

    abs_path = os.path.dirname(os.path.abspath(__file__))
    xml_path = os.path.join(abs_path, "..", "xml_models")
    xmlBaseFileName = "scene_base.xml"
    save_filename = "built_scene.xml"

    # Set scenario parameters
    drone_init_pos = np.array([-0.76, 1.13, 1, 0])  # initial drone position and yaw angle
    load_init_pos = np.array([0, -1, 0.75-0.15])  # np.array([0, -1, 0.77])  # TODO: Do some transformations in z direction
    load_target_pos = np.array([0.76, 1.13, 0.75-0.15])  # np.array([0.76, 1.13, 0.75])
    load_mass = 0.02

    # create xml with a drone and a car
    scene = SceneXmlGenerator(xmlBaseFileName)
    drone0_name = scene.add_drone(np.array2string(drone_init_pos[0:3] + np.array([0, 0, 0.4]))[1:-2], "1 0 0 0", RED_COLOR, DRONE_TYPES.BUMBLEBEE_HOOKED, 2)
    payload0_name = scene.add_payload(np.array2string(load_init_pos)[1:-2], ".05 .05 .025", str(load_mass), "1 0 0 0", BLUE_COLOR)

    # saving the scene as xml so that the simulator can load it
    scene.save_xml(os.path.join(xml_path, save_filename))

    # create list of parsers
    virt_parsers = [parseMovingObjects]

    control_step, graphics_step = 0.01, 0.02
    xml_filename = os.path.join(xml_path, save_filename)

    # initializing simulator
    simulator = ActiveSimulator(xml_filename, None, control_step, graphics_step, virt_parsers, mocap_parsers=None,
                                connect_to_optitrack=False)

    # grabbing the drone and the car
    drone0 = simulator.get_MovingObject_by_name_in_xml(drone0_name)
    payload0 = simulator.get_MovingObject_by_name_in_xml(payload0_name)

    # creating trajectory and controller for drone0
    drone0_trajectory = HookedDroneTrajectory()
    drone0_trajectory.set_control_step(control_step)
    drone0_trajectory.set_rod_length(drone0.rod_length)
    # drone0_controller = LtvLqrLoadControl(drone0.mass, drone0.inertia, simulator.gravity)
    drone0_controller = GeomControl(drone0.mass, drone0.inertia, simulator.gravity)

    drone0_controllers = [drone0_controller]

    # setting update_controller_type method, trajectory and controller for drone0
    drone0.set_update_controller_type_function(update_controller_type)
    drone0.set_trajectory(drone0_trajectory)
    drone0.set_controllers(drone0_controllers)

    # start simulation
    sensor_data = []
    q_data = []
    drone0.qvel[0] = 0
    drone0.qvel[1] = 0

    airflow_sampl = AirflowSampler(os.path.join(abs_path, "..", "airflow_data", "airflow_luts", "flow_pressure_shifted.txt"), drone0)
    payload0.create_surface_mesh(0.00001)

    # Plan trajectory
    drone0_trajectory.construct(drone_init_pos, load_init_pos, load_target_pos, load_mass)
    # drone0_controller.compute_ltv_lqr(drone0_trajectory.states, drone0_trajectory.inputs,
    #                                   drone0_trajectory.payload_mass, control_step)

    while not simulator.glfw_window_should_close():
        simulator.update()

        force, torque = airflow_sampl.generate_forces_opt(payload0)
        payload0.set_force_torque(force, torque)

        # state = drone0.get_state()
        # setpoint = drone0_trajectory.evaluate(state, i, i*control_step, control_step)
        # ctrl = drone0_controller.compute_control(state, setpoint, i*control_step)
        # drone0.set_ctrl(ctrl)
        # if i % 5 == 0:
        #     hook_roll, hook_pitch, hook_yaw = mujoco_helper.euler_from_quaternion(*drone0.sensor_hook_orimeter)

            # sensor_data += [hook_pitch]
            # sensor_data += [[drone0.get_state()["joint_ang"][0]]]
            # q_data += [drone0.get_hook_qpos()]

            # print(mujoco_helper.euler_from_quaternion(*drone0.sensor_hook_orimeter))
            # sensor_data += [[drone0.sensor_hook_gyro[0], drone0.sensor_hook_gyro[1]]]
            # hook_qvel = drone0.get_hook_qvel()
            # q_data += [[hook_qvel[0], hook_qvel[1]]]
            # pass

    simulator.close()

    # plt.plot(sensor_data)
    # plt.plot(q_data)
    # plt.legend(["sensor_joint_ang", "q_joint_ang"])
    # plt.show()