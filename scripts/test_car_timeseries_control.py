import os

from classes.active_simulation import ActiveSimulator

from util import xml_generator

from classes.car import Car

from classes.car_classes.trajectories import DummyTrajectory as CarTrajectory
from classes.car_classes.controllers import InputTimeSeriesController as CarController
from util import mujoco_helper, carHeading2quaternion

import numpy as np
import matplotlib.pyplot as plt


RED_COLOR = "0.85 0.2 0.2 1.0"
BLUE_COLOR = "0.2 0.2 0.85 1.0"


abs_path = os.path.dirname(os.path.abspath(__file__))
xml_path = os.path.join(abs_path, "..", "xml_models")
xml_base_filename = "car_obstackle_scene.xml"
save_filename = "built_scene.xml"

# create xml with a car
scene = xml_generator.SceneXmlGenerator(xml_base_filename)
car0_name = scene.add_car(pos="0 0 0.052", quat=carHeading2quaternion(0.64424), color=RED_COLOR, is_virtual=True, has_rod=False)
 

# saving the scene as xml so that the simulator can load it
scene.save_xml(os.path.join(xml_path, save_filename))

# create list of parsers 
virt_parsers = [Car.parse]



control_step, graphics_step = 0.025, 0.025 # the car controller operates in 40 Hz
xml_filename = os.path.join(xml_path, save_filename)

# recording interval for automatic video capture
#rec_interval=[1,25]
rec_interval = None # no video capture

# initializing simulator
simulator = ActiveSimulator(xml_filename, rec_interval, control_step, graphics_step, virt_parsers, mocap_parsers=None, connect_to_optitrack=False)

# ONLY for recording
#simulator.activeCam
#simulator.activeCam.distance=9
#simulator.activeCam.azimuth=230

# grabbing the drone and the car
car0 = simulator.get_MovingObject_by_name_in_xml(car0_name)


# create a trajectory
car0_trajectory=CarTrajectory() # dummy trajectory object

car0_controller = CarController(0.07*np.ones(100), 0.5*np.ones(100)) # kiszedtem a gravitációt, az a kocsit nem érdekli

car0_controllers = [car0_controller]

def update_controller_type(state, setpoint, time, i):
    # ha csak 1 controller van ez akkor is kell?
    return 0



# setting update_controller_type method, trajectory and controller for car0
car0.set_update_controller_type_method(update_controller_type)
car0.set_trajectory(car0_trajectory)
car0.set_controllers(car0_controllers)


# start simulation
i = 0
x=[]
y=[]
while not simulator.glfw_window_should_close():
    simulator.update(i)
    st=car0.get_state()
    x.append(st["pos_x"])
    y.append(st["pos_y"])
    i += 1
simulator.close()

plt.plot(x,y)
plt.axis('equal')
plt.show()